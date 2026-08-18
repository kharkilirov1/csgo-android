#!/usr/bin/env python3
"""Build and inspect Source 1 VCS v6 shader containers.

This is a standalone replacement for the container-writing part of
``utils/shadercompile/shadercompile.cpp``.  It consumes the ``filelist.txt``
format emitted by ``devtools/bin/fxc_prep.pl``, invokes Microsoft's DX9
``fxc.exe`` for every non-skipped combo, and writes runtime-compatible v6
``.vcs`` files.

The renderer is not involved.  Only Python's standard library and a working
DX9 fxc.exe are required.
"""

from __future__ import annotations

import argparse
import bz2
import concurrent.futures
import dataclasses
import hashlib
import json
import lzma
import os
import pathlib
import re
import shlex
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from collections.abc import Iterable, Iterator, Mapping


VCS_VERSION = 6
MAX_SHADER_UNPACKED_BLOCK_SIZE = 1 << 17
HEADER = struct.Struct("<7I")
STATIC_RECORD = struct.Struct("<2I")
LZMA_HEADER = struct.Struct("<4sII5s")
U32 = struct.Struct("<I")
U32_PAIR = struct.Struct("<2I")


class VcsError(RuntimeError):
    """Malformed input, failed compilation, or an invalid VCS container."""


@dataclasses.dataclass(frozen=True)
class VcsHeader:
    version: int
    total_combos: int
    dynamic_combos: int
    flags: int
    centroid_mask: int
    dictionary_count: int
    source_crc32: int


@dataclasses.dataclass
class VcsFile:
    header: VcsHeader
    # static combo id -> dynamic combo id -> DX9 bytecode
    combos: dict[int, dict[int, bytes]]
    static_aliases: dict[int, int] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Define:
    name: str
    minimum: int
    maximum: int
    is_static: bool

    @property
    def size(self) -> int:
        return self.maximum - self.minimum + 1


@dataclasses.dataclass(frozen=True)
class WorkSection:
    name: str
    source: str
    defines: tuple[Define, ...]
    skip_expression: str
    command_prefix: str
    command_suffix: str
    skip_parse_error: str | None = None

    @property
    def total_combos(self) -> int:
        answer = 1
        for define in self.defines:
            answer *= define.size
        return answer

    @property
    def dynamic_combos(self) -> int:
        answer = 1
        for define in self.defines:
            if not define.is_static:
                answer *= define.size
        return answer


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise VcsError(message)


def _decode_valve_lzma(payload: bytes) -> bytes:
    _need(len(payload) >= LZMA_HEADER.size, "truncated Valve LZMA header")
    magic, actual_size, compressed_size, properties = LZMA_HEADER.unpack_from(payload)
    _need(magic == b"LZMA", f"bad Valve LZMA magic {magic!r}")
    _need(
        LZMA_HEADER.size + compressed_size == len(payload),
        "Valve LZMA compressed-size field does not match block size",
    )

    prop0 = properties[0]
    lc = prop0 % 9
    remainder = prop0 // 9
    lp = remainder % 5
    pb = remainder // 5
    dictionary_size = struct.unpack_from("<I", properties, 1)[0]
    _need(lc <= 8 and lp <= 4 and pb <= 4, "invalid LZMA properties")
    _need(dictionary_size > 0, "invalid zero LZMA dictionary")

    decoder = lzma.LZMADecompressor(
        format=lzma.FORMAT_RAW,
        filters=[
            {
                "id": lzma.FILTER_LZMA1,
                "dict_size": dictionary_size,
                "lc": lc,
                "lp": lp,
                "pb": pb,
            }
        ],
    )
    # Valve's encoder writes no end marker.  The engine also decodes against the
    # exact uncompressed size, so max_length is the correct independent analogue.
    output = decoder.decompress(payload[LZMA_HEADER.size :], max_length=actual_size)
    _need(len(output) == actual_size, "Valve LZMA block decoded to the wrong size")
    return output


def _encode_valve_lzma(data: bytes) -> bytes:
    # These are the properties found in Valve-generated VCS v6 files and match
    # LzmaEncProps defaults (lc=3, lp=0, pb=2, normal/BT4, fast-bytes=32).
    dictionary_size = 1 << 18
    lc, lp, pb = 3, 0, 2
    compressed = lzma.compress(
        data,
        format=lzma.FORMAT_RAW,
        filters=[
            {
                "id": lzma.FILTER_LZMA1,
                "dict_size": dictionary_size,
                "lc": lc,
                "lp": lp,
                "pb": pb,
                "mode": lzma.MODE_NORMAL,
                "nice_len": 32,
                "mf": lzma.MF_BT4,
            }
        ],
    )
    prop0 = (pb * 5 + lp) * 9 + lc
    properties = bytes([prop0]) + struct.pack("<I", dictionary_size)
    return LZMA_HEADER.pack(b"LZMA", len(data), len(compressed), properties) + compressed


def _decode_dynamic_payload(payload: bytes) -> dict[int, bytes]:
    position = 0
    bytecodes: dict[int, bytes] = {}
    aliases: dict[int, int] = {}
    while position < len(payload):
        _need(position + U32_PAIR.size <= len(payload), "truncated dynamic combo record")
        combo_or_alias, size_or_source = U32_PAIR.unpack_from(payload, position)
        position += U32_PAIR.size
        if combo_or_alias & 0x80000000:
            combo_id = combo_or_alias & 0x7FFFFFFF
            _need(combo_id not in aliases and combo_id not in bytecodes, "duplicate dynamic combo id")
            aliases[combo_id] = size_or_source
            continue

        combo_id = combo_or_alias
        code_size = size_or_source
        _need(position + code_size <= len(payload), "truncated DX9 bytecode")
        _need(combo_id not in aliases and combo_id not in bytecodes, "duplicate dynamic combo id")
        bytecodes[combo_id] = payload[position : position + code_size]
        position += code_size

    unresolved = dict(aliases)
    while unresolved:
        progress = False
        for combo_id, source_id in list(unresolved.items()):
            if source_id in bytecodes:
                bytecodes[combo_id] = bytecodes[source_id]
                del unresolved[combo_id]
                progress = True
        _need(progress, f"unresolved dynamic aliases: {unresolved}")
    return bytecodes


def parse_vcs(data_or_path: bytes | bytearray | os.PathLike[str] | str) -> VcsFile:
    if isinstance(data_or_path, (str, os.PathLike)):
        data = pathlib.Path(data_or_path).read_bytes()
    else:
        data = bytes(data_or_path)

    _need(len(data) >= HEADER.size, "truncated VCS header")
    raw_header = HEADER.unpack_from(data)
    header = VcsHeader(*raw_header)
    _need(header.version == VCS_VERSION, f"unsupported VCS version {header.version}")
    _need(header.dynamic_combos > 0, "dynamic combo count must be nonzero")
    _need(header.dictionary_count > 0, "static dictionary must contain its sentinel")

    dictionary_end = HEADER.size + header.dictionary_count * STATIC_RECORD.size
    _need(dictionary_end + U32.size <= len(data), "truncated static dictionary")
    records = [
        STATIC_RECORD.unpack_from(data, HEADER.size + index * STATIC_RECORD.size)
        for index in range(header.dictionary_count)
    ]
    ids = [record[0] for record in records]
    _need(ids == sorted(ids), "static dictionary is not sorted")
    _need(ids[-1] == 0xFFFFFFFF, "static dictionary has no sentinel")

    alias_count = U32.unpack_from(data, dictionary_end)[0]
    alias_start = dictionary_end + U32.size
    alias_end = alias_start + alias_count * U32_PAIR.size
    _need(alias_end <= len(data), "truncated static alias table")
    static_aliases: dict[int, int] = {}
    for index in range(alias_count):
        combo_id, source_id = U32_PAIR.unpack_from(data, alias_start + index * U32_PAIR.size)
        _need(combo_id not in static_aliases, "duplicate static alias id")
        static_aliases[combo_id] = source_id
    _need(list(static_aliases) == sorted(static_aliases), "static alias table is not sorted")

    offsets = [record[1] for record in records]
    _need(offsets == sorted(offsets), "static dictionary offsets are not sorted")
    _need(offsets[0] >= alias_end, "first static block overlaps metadata")
    _need(offsets[-1] == len(data), "sentinel does not point at end of file")

    unique_combos: dict[int, dict[int, bytes]] = {}
    for record_index, (static_id, start) in enumerate(records[:-1]):
        end = records[record_index + 1][1]
        _need(start <= end <= len(data), "invalid static block range")
        position = start
        dynamic_combos: dict[int, bytes] = {}
        while True:
            _need(position + U32.size <= end, "static block has no terminator")
            flag_size = U32.unpack_from(data, position)[0]
            position += U32.size
            if flag_size == 0xFFFFFFFF:
                break
            encoding = flag_size >> 30
            payload_size = flag_size & 0x3FFFFFFF
            _need(position + payload_size <= end, "compressed block exceeds static block")
            encoded = data[position : position + payload_size]
            position += payload_size
            if encoding == 2:
                decoded = encoded
            elif encoding == 1:
                decoded = _decode_valve_lzma(encoded)
            elif encoding == 0:
                decoded = bz2.decompress(encoded)
            else:
                raise VcsError("reserved VCS block encoding 3")
            for dynamic_id, bytecode in _decode_dynamic_payload(decoded).items():
                _need(dynamic_id not in dynamic_combos, "dynamic id occurs in multiple blocks")
                _need(dynamic_id < header.dynamic_combos, "dynamic id exceeds header count")
                dynamic_combos[dynamic_id] = bytecode
        _need(position == end, "bytes remain after static block terminator")
        unique_combos[static_id] = dynamic_combos

    combos = {static_id: dict(dynamic) for static_id, dynamic in unique_combos.items()}
    unresolved = dict(static_aliases)
    while unresolved:
        progress = False
        for static_id, source_id in list(unresolved.items()):
            if source_id in combos:
                combos[static_id] = dict(combos[source_id])
                del unresolved[static_id]
                progress = True
        _need(progress, f"unresolved static aliases: {unresolved}")

    for static_id in combos:
        _need(
            static_id * header.dynamic_combos < header.total_combos,
            "static id exceeds total combo count",
        )
    return VcsFile(header=header, combos=combos, static_aliases=static_aliases)


def _encode_dynamic_blocks(dynamic: Mapping[int, bytes], compression: str) -> bytes:
    output = bytearray()
    pending = bytearray()

    def flush() -> None:
        if not pending:
            return
        raw = bytes(pending)
        if compression == "raw":
            encoded = raw
            flag = 0x80000000
        else:
            candidate = _encode_valve_lzma(raw)
            if compression == "lzma" or len(candidate) < len(raw):
                encoded = candidate
                flag = 0x40000000
            else:
                encoded = raw
                flag = 0x80000000
        _need(len(encoded) < 0x40000000, "VCS block is too large")
        output.extend(U32.pack(flag | len(encoded)))
        output.extend(encoded)
        pending.clear()

    for dynamic_id in sorted(dynamic):
        bytecode = bytes(dynamic[dynamic_id])
        _need(0 <= dynamic_id < 0x80000000, "dynamic combo id is out of range")
        # Match shadercompile.cpp: it leaves 16 bytes of headroom even though a
        # normal record itself uses eight bytes of metadata.
        if len(pending) + len(bytecode) + 16 >= MAX_SHADER_UNPACKED_BLOCK_SIZE:
            flush()
        pending.extend(U32_PAIR.pack(dynamic_id, len(bytecode)))
        pending.extend(bytecode)
    flush()
    return bytes(output)


def pack_vcs_v6(
    *,
    total_combos: int,
    dynamic_combos: int,
    combos: Mapping[int, Mapping[int, bytes]],
    flags: int = 0,
    centroid_mask: int = 0,
    source_crc32: int = 0,
    compression: str = "auto",
) -> bytes:
    _need(compression in {"auto", "lzma", "raw"}, f"unknown compression {compression}")
    _need(0 < dynamic_combos <= total_combos <= 0xFFFFFFFF, "invalid combo counts")
    _need(total_combos % dynamic_combos == 0, "total combos are not divisible by dynamic combos")

    packed_by_static: dict[int, bytes] = {}
    for static_id, dynamic in combos.items():
        _need(0 <= static_id < total_combos // dynamic_combos, "static combo id is out of range")
        _need(dynamic, f"static combo {static_id} has no bytecode")
        for dynamic_id in dynamic:
            _need(0 <= dynamic_id < dynamic_combos, "dynamic combo id is out of range")
        packed_by_static[static_id] = _encode_dynamic_blocks(dynamic, compression)

    # shadercompile.cpp aliases static combos whose complete packed dynamic data
    # is byte-identical.  Insertion in its hash table is nondeterministic; using
    # ascending ids here makes the same semantics deterministic and reproducible.
    blob_owner: dict[bytes, int] = {}
    unique: dict[int, bytes] = {}
    aliases: dict[int, int] = {}
    for static_id in sorted(packed_by_static):
        blob = packed_by_static[static_id]
        owner = blob_owner.get(blob)
        if owner is None:
            blob_owner[blob] = static_id
            unique[static_id] = blob
        else:
            aliases[static_id] = owner

    dictionary_count = len(unique) + 1  # includes the 0xffffffff sentinel
    metadata_size = HEADER.size + dictionary_count * STATIC_RECORD.size + U32.size + len(aliases) * U32_PAIR.size
    offsets: dict[int, int] = {}
    payload = bytearray()
    cursor = metadata_size
    for static_id in sorted(unique):
        offsets[static_id] = cursor
        blob = unique[static_id]
        payload.extend(blob)
        payload.extend(U32.pack(0xFFFFFFFF))
        cursor += len(blob) + U32.size
    sentinel_offset = cursor

    output = bytearray(
        HEADER.pack(
            VCS_VERSION,
            total_combos,
            dynamic_combos,
            flags & 0xFFFFFFFF,
            centroid_mask & 0xFFFFFFFF,
            dictionary_count,
            source_crc32 & 0xFFFFFFFF,
        )
    )
    for static_id in sorted(unique):
        output.extend(STATIC_RECORD.pack(static_id, offsets[static_id]))
    output.extend(STATIC_RECORD.pack(0xFFFFFFFF, sentinel_offset))
    output.extend(U32.pack(len(aliases)))
    for static_id in sorted(aliases):
        output.extend(U32_PAIR.pack(static_id, aliases[static_id]))
    output.extend(payload)
    _need(len(output) == sentinel_offset, "internal VCS offset calculation error")
    return bytes(output)


_TOKEN = re.compile(
    r"\s*(?:(defined)|([0-9]+)|(\$[A-Za-z0-9_]+)|(&&|\|\||>=|<=|==|!=|[!><()]))"
)


class _ExpressionParser:
    def __init__(self, expression: str, defined_names: set[str]):
        self.expression = expression
        self.defined_names = defined_names
        self.tokens: list[tuple[str, str]] = []
        position = 0
        while position < len(expression):
            match = _TOKEN.match(expression, position)
            if not match:
                raise VcsError(f"unsupported skip-expression syntax at {expression[position:]!r}")
            kind = ("defined", "number", "variable", "operator")[next(i for i, value in enumerate(match.groups()) if value is not None)]
            value = next(value for value in match.groups() if value is not None)
            self.tokens.append((kind, value))
            position = match.end()
        self.position = 0

    def _peek(self, value: str | None = None) -> bool:
        if self.position >= len(self.tokens):
            return False
        return value is None or self.tokens[self.position][1] == value

    def _take(self, value: str | None = None) -> tuple[str, str]:
        _need(self._peek(value), f"expected {value!r} in {self.expression!r}")
        token = self.tokens[self.position]
        self.position += 1
        return token

    def parse(self):
        node = self._or()
        _need(self.position == len(self.tokens), f"trailing skip-expression tokens in {self.expression!r}")
        return node

    def _or(self):
        node = self._and()
        while self._peek("||"):
            self._take()
            node = ("||", node, self._and())
        return node

    def _and(self):
        node = self._comparison()
        while self._peek("&&"):
            self._take()
            node = ("&&", node, self._comparison())
        return node

    def _comparison(self):
        node = self._unary()
        if self._peek() and self.tokens[self.position][1] in {">=", "<=", "==", "!=", ">", "<"}:
            operator = self._take()[1]
            node = (operator, node, self._unary())
        return node

    def _unary(self):
        if self._peek("!"):
            self._take()
            return ("!", self._unary())
        if self._peek() and self.tokens[self.position][0] == "defined":
            self._take()
            if self._peek("("):
                self._take()
                token = self._take()
                self._take(")")
            else:
                token = self._take()
            _need(token[0] == "variable", "defined must be followed by a $variable")
            return ("constant", int(token[1][1:] in self.defined_names))
        return self._primary()

    def _primary(self):
        if self._peek("("):
            self._take()
            node = self._or()
            self._take(")")
            return node
        kind, value = self._take()
        if kind == "number":
            return ("constant", int(value))
        if kind == "variable":
            return ("variable", value[1:])
        raise VcsError(f"unexpected token {value!r} in {self.expression!r}")


def _parse_skip_expression(
    expression: str,
    defined_names: set[str],
    *,
    strict: bool = False,
    section_name: str | None = None,
):
    """Parse a SKIP expression with shadercompile's malformed-input semantics.

    ``CfgProcessor::ParseCondition`` discards the complete expression and uses
    false after ``AbortedParse``.  Legacy worklists rely on that behavior for a
    few bare (non-``$``) identifiers, so compatibility mode must not reject the
    whole filelist.  Strict mode is available for auditing those inputs.
    """
    try:
        return _ExpressionParser(expression, defined_names).parse(), None
    except VcsError as error:
        if strict:
            raise
        message = str(error)
        label = f"section {section_name}: " if section_name else ""
        print(
            f"vcs_v6: warning: {label}malformed SKIP expression; "
            f"matching shadercompile by treating it as false ({message})",
            file=sys.stderr,
        )
        return ("constant", 0), message


def _evaluate_expression(node, values: Mapping[str, int]) -> int:
    operator = node[0]
    if operator == "constant":
        return node[1]
    if operator == "variable":
        return values.get(node[1], 0)
    if operator == "!":
        return int(not _evaluate_expression(node[1], values))
    left = _evaluate_expression(node[1], values)
    if operator == "&&":
        return int(bool(left) and bool(_evaluate_expression(node[2], values)))
    if operator == "||":
        return int(bool(left) or bool(_evaluate_expression(node[2], values)))
    right = _evaluate_expression(node[2], values)
    return int(
        {
            "==": left == right,
            "!=": left != right,
            ">": left > right,
            ">=": left >= right,
            "<": left < right,
            "<=": left <= right,
        }[operator]
    )


def parse_worklist(
    path: os.PathLike[str] | str, *, strict_skips: bool = False
) -> list[WorkSection]:
    lines = pathlib.Path(path).read_text(encoding="utf-8-sig", errors="strict").splitlines()
    sections: list[WorkSection] = []
    names: set[str] = set()
    position = 0
    while position < len(lines):
        if not lines[position].startswith("#BEGIN "):
            position += 1
            continue
        name = lines[position][7:]
        position += 1
        _need(position < len(lines), f"section {name}: source line is missing")
        source = lines[position].strip()
        position += 1

        while position < len(lines) and not lines[position].startswith("#DEFINES-"):
            position += 1
        _need(position < len(lines), f"section {name}: #DEFINES is missing")
        is_static = lines[position].startswith("#DEFINES-S")
        position += 1
        defines: list[Define] = []
        while position < len(lines) and not lines[position].startswith("#SKIP"):
            line = lines[position].strip()
            position += 1
            if line.startswith("#DEFINES-"):
                is_static = line.startswith("#DEFINES-S")
                continue
            match = re.fullmatch(r"([A-Za-z0-9_]+)\s*=\s*(-?\d+)\.\.(-?\d+)", line)
            if not match:
                continue
            minimum, maximum = int(match.group(2)), int(match.group(3))
            _need(maximum >= minimum, f"section {name}: reversed define range {line!r}")
            defines.append(Define(match.group(1), minimum, maximum, is_static))

        _need(position < len(lines), f"section {name}: #SKIP is missing")
        position += 1
        _need(position < len(lines), f"section {name}: skip expression is missing")
        skip_expression = lines[position].strip()
        position += 1
        while position < len(lines) and not lines[position].startswith("#COMMAND"):
            position += 1
        _need(position + 2 < len(lines), f"section {name}: #COMMAND is incomplete")
        position += 1
        command_prefix = lines[position].strip()
        command_suffix = lines[position + 1].strip()
        position += 2
        while position < len(lines) and not lines[position].startswith("#END"):
            position += 1
        _need(position < len(lines), f"section {name}: #END is missing")
        position += 1

        if name in names:
            continue  # matches shadercompile.cpp's first unique section behavior
        names.add(name)
        _skip_ast, skip_parse_error = _parse_skip_expression(
            skip_expression,
            {define.name for define in defines},
            strict=strict_skips,
            section_name=name,
        )
        section = WorkSection(
            name=name,
            source=source,
            defines=tuple(defines),
            skip_expression=skip_expression,
            command_prefix=command_prefix,
            command_suffix=command_suffix,
            skip_parse_error=skip_parse_error,
        )
        sections.append(section)
    _need(sections, f"no #BEGIN sections found in {path}")
    return sections


def _combo_values(section: WorkSection, combo_id: int) -> dict[str, int]:
    values: dict[str, int] = {}
    quotient = combo_id
    for define in section.defines:
        values[define.name] = define.minimum + quotient % define.size
        quotient //= define.size
    _need(quotient == 0, "combo id exceeds define product")
    return values


def _macro_value(command: str, name: str, *, required: bool = True) -> int:
    match = re.search(rf"/D{re.escape(name)}=(0x[0-9A-Fa-f]+|[0-9]+)(?:\s|$)", command)
    if not match:
        if required:
            raise VcsError(f"required /D{name}= macro is absent")
        return 0
    return int(match.group(1), 0)


def _source_crc32(shader_dir: pathlib.Path, source: str) -> int:
    def expand(path: pathlib.Path, stack: tuple[pathlib.Path, ...]) -> str:
        path = path.resolve()
        _need(path not in stack, f"recursive shader include at {path}")
        _need(path.is_file(), f"shader source/include does not exist: {path}")
        text = path.read_text(encoding="latin-1")
        output: list[str] = []
        for line in text.splitlines(keepends=True):
            match = re.search(r'#include\s+"(.*)"', line, re.IGNORECASE)
            if not match:
                output.append(line)
                continue
            relative = match.group(1).replace("\\", os.sep)
            # copyshaders.pl opens every recursively named include from the
            # shader build working directory; it does not chdir to the including
            # file's directory.  Keep that behavior so header CRCs are identical.
            include = shader_dir / relative
            output.append(expand(include, stack + (path,)))
        return "".join(output)

    source_path = shader_dir / source.replace("\\", os.sep)
    return zlib.crc32(expand(source_path, ()).encode("latin-1")) & 0xFFFFFFFF


def _compile_one(
    section: WorkSection,
    combo_id: int,
    values: Mapping[str, int],
    *,
    shader_dir: pathlib.Path,
    fxc: pathlib.Path,
    temporary_dir: pathlib.Path,
) -> bytes:
    defines = " ".join(f"/D{name}={value}" for name, value in values.items())
    command = f"{section.command_prefix} /DSHADERCOMBO={combo_id} {defines} {section.command_suffix}"
    command = re.sub(r">\s*output\.txt\s+2>&1\s*$", "", command, flags=re.IGNORECASE)
    argv = shlex.split(command, posix=False)
    _need(argv, f"section {section.name}: empty fxc command")
    argv = [token[1:-1] if len(token) >= 2 and token[0] == token[-1] == '"' else token for token in argv]
    argv[0] = str(fxc)
    object_path = temporary_dir / f"{section.name}-{combo_id}.o"
    replaced_output = False
    for index, argument in enumerate(argv):
        if argument.lower().startswith("/fo"):
            argv[index] = "/Fo" + str(object_path)
            replaced_output = True
    _need(replaced_output, f"section {section.name}: fxc command has no /Fo output")
    completed = subprocess.run(
        argv,
        cwd=shader_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode or not object_path.is_file():
        raise VcsError(
            f"{section.name} combo {combo_id}: fxc failed with {completed.returncode}\n"
            f"command: {subprocess.list2cmdline(argv)}\n{completed.stdout}"
        )
    bytecode = object_path.read_bytes()
    object_path.unlink()
    _need(bytecode, f"{section.name} combo {combo_id}: fxc emitted empty bytecode")
    return bytecode


def compile_section(
    section: WorkSection,
    *,
    shader_dir: pathlib.Path,
    fxc: pathlib.Path,
    jobs: int = 1,
    compression: str = "auto",
    source_crc: bool = True,
    strict_skips: bool = False,
    static_ids: Iterable[int] | None = None,
) -> bytes:
    _need(shader_dir.is_dir(), f"shader directory does not exist: {shader_dir}")
    _need(fxc.is_file(), f"fxc executable does not exist: {fxc}")
    command = section.command_prefix + " " + section.command_suffix
    macro_total = _macro_value(command, "TOTALSHADERCOMBOS")
    macro_dynamic = _macro_value(command, "NUMDYNAMICCOMBOS")
    _need(macro_total == section.total_combos, f"{section.name}: TOTALSHADERCOMBOS mismatch")
    _need(macro_dynamic == section.dynamic_combos, f"{section.name}: NUMDYNAMICCOMBOS mismatch")
    flags = _macro_value(command, "FLAGS")
    centroid_mask = _macro_value(command, "CENTROIDMASK")
    expression, _skip_parse_error = _parse_skip_expression(
        section.skip_expression,
        {define.name for define in section.defines},
        strict=strict_skips,
        section_name=section.name,
    )

    static_combo_count = section.total_combos // section.dynamic_combos
    if static_ids is None:
        requested_static_ids = range(static_combo_count - 1, -1, -1)
    else:
        requested_static_ids = sorted(set(static_ids), reverse=True)
        _need(requested_static_ids, f"{section.name}: --static-id selected no static combos")
        for static_id in requested_static_ids:
            _need(
                0 <= static_id < static_combo_count,
                f"{section.name}: static id {static_id} is outside 0..{static_combo_count - 1}",
            )

    enabled: list[tuple[int, dict[str, int]]] = []
    requested_combo_count = len(requested_static_ids) * section.dynamic_combos
    for static_id in requested_static_ids:
        first_combo = static_id * section.dynamic_combos
        for dynamic_id in range(section.dynamic_combos - 1, -1, -1):
            combo_id = first_combo + dynamic_id
            values = _combo_values(section, combo_id)
            if not _evaluate_expression(expression, values):
                enabled.append((combo_id, values))
    _need(enabled, f"{section.name}: every combo is skipped")

    combos: dict[int, dict[int, bytes]] = {}
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="vcs-v6-") as temporary:
        temporary_dir = pathlib.Path(temporary)

        def compile_item(item: tuple[int, dict[str, int]]):
            combo_id, values = item
            return combo_id, _compile_one(
                section,
                combo_id,
                values,
                shader_dir=shader_dir,
                fxc=fxc,
                temporary_dir=temporary_dir,
            )

        if jobs <= 1:
            results: Iterable[tuple[int, bytes]] = map(compile_item, enabled)
            for completed_count, (combo_id, bytecode) in enumerate(results, 1):
                static_id, dynamic_id = divmod(combo_id, section.dynamic_combos)
                combos.setdefault(static_id, {})[dynamic_id] = bytecode
                if completed_count == len(enabled) or completed_count % 250 == 0:
                    print(f"{section.name}: compiled {completed_count}/{len(enabled)}", file=sys.stderr)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
                iterator = iter(enabled)
                pending: dict[concurrent.futures.Future, int] = {}
                for _ in range(min(jobs * 2, len(enabled))):
                    item = next(iterator, None)
                    if item is not None:
                        pending[executor.submit(compile_item, item)] = item[0]
                completed_count = 0
                while pending:
                    done, _ = concurrent.futures.wait(
                        pending, return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    for future in done:
                        pending.pop(future)
                        combo_id, bytecode = future.result()
                        static_id, dynamic_id = divmod(combo_id, section.dynamic_combos)
                        combos.setdefault(static_id, {})[dynamic_id] = bytecode
                        completed_count += 1
                        item = next(iterator, None)
                        if item is not None:
                            pending[executor.submit(compile_item, item)] = item[0]
                        if completed_count == len(enabled) or completed_count % 250 == 0:
                            print(f"{section.name}: compiled {completed_count}/{len(enabled)}", file=sys.stderr)

    elapsed = time.monotonic() - started
    print(
        f"{section.name}: {len(enabled)}/{requested_combo_count} selected combos "
        f"({section.total_combos} total address space) in {elapsed:.2f}s",
        file=sys.stderr,
    )
    crc = _source_crc32(shader_dir, section.source) if source_crc else 0
    return pack_vcs_v6(
        total_combos=section.total_combos,
        dynamic_combos=section.dynamic_combos,
        combos=combos,
        flags=flags,
        centroid_mask=centroid_mask,
        source_crc32=crc,
        compression=compression,
    )


def _summary(path: pathlib.Path, vcs: VcsFile) -> dict:
    unique_static = len(vcs.combos) - len(vcs.static_aliases)
    bytecodes = [code for dynamic in vcs.combos.values() for code in dynamic.values()]
    return {
        "path": str(path),
        "size": path.stat().st_size,
        **dataclasses.asdict(vcs.header),
        "materialized_static_combos": len(vcs.combos),
        "unique_static_combos": unique_static,
        "static_aliases": len(vcs.static_aliases),
        "materialized_dynamic_bytecodes": len(bytecodes),
        "bytecode_sha256": hashlib.sha256(b"".join(sorted(bytecodes))).hexdigest(),
    }


def _atomic_write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="validate and summarize VCS v6 files")
    inspect_parser.add_argument("paths", nargs="+", type=pathlib.Path)

    repack_parser = subparsers.add_parser("repack", help="semantically repack an existing VCS v6 file")
    repack_parser.add_argument("input", type=pathlib.Path)
    repack_parser.add_argument("output", type=pathlib.Path)
    repack_parser.add_argument("--compression", choices=("auto", "lzma", "raw"), default="auto")

    compile_parser = subparsers.add_parser("compile", help="compile every section in a filelistgen worklist")
    compile_parser.add_argument("worklist", type=pathlib.Path)
    compile_parser.add_argument("--shader-dir", required=True, type=pathlib.Path)
    compile_parser.add_argument("--fxc", required=True, type=pathlib.Path)
    compile_parser.add_argument("--out-dir", required=True, type=pathlib.Path)
    compile_parser.add_argument("--jobs", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    compile_parser.add_argument("--section", action="append", default=[])
    compile_parser.add_argument(
        "--static-id",
        type=lambda value: int(value, 0),
        action="append",
        default=[],
        help="compile only this static combo id (repeatable; requires exactly one --section)",
    )
    compile_parser.add_argument("--compression", choices=("auto", "lzma", "raw"), default="auto")
    compile_parser.add_argument("--zero-source-crc", action="store_true")
    compile_parser.add_argument(
        "--strict-skips",
        action="store_true",
        help="fail instead of emulating shadercompile's malformed-SKIP => false fallback",
    )

    arguments = parser.parse_args(argv)
    if arguments.command == "inspect":
        summaries = [_summary(path, parse_vcs(path)) for path in arguments.paths]
        print(json.dumps(summaries, indent=2))
        return 0

    if arguments.command == "repack":
        source = parse_vcs(arguments.input)
        packed = pack_vcs_v6(
            total_combos=source.header.total_combos,
            dynamic_combos=source.header.dynamic_combos,
            combos=source.combos,
            flags=source.header.flags,
            centroid_mask=source.header.centroid_mask,
            source_crc32=source.header.source_crc32,
            compression=arguments.compression,
        )
        _atomic_write(arguments.output, packed)
        # Parse the exact bytes just written; a successful write is not itself a witness.
        reparsed = parse_vcs(arguments.output)
        _need(reparsed.combos == source.combos, "semantic mismatch after repack")
        print(json.dumps(_summary(arguments.output, reparsed), indent=2))
        return 0

    sections = parse_worklist(arguments.worklist, strict_skips=arguments.strict_skips)
    selected = set(arguments.section)
    if selected:
        sections = [section for section in sections if section.name in selected]
        missing = selected - {section.name for section in sections}
        _need(not missing, f"worklist sections not found: {sorted(missing)}")
    if arguments.static_id:
        _need(len(sections) == 1, "--static-id requires exactly one selected section")
    for section in sections:
        packed = compile_section(
            section,
            shader_dir=arguments.shader_dir.resolve(),
            fxc=arguments.fxc.resolve(),
            jobs=max(1, arguments.jobs),
            compression=arguments.compression,
            source_crc=not arguments.zero_source_crc,
            strict_skips=arguments.strict_skips,
            static_ids=arguments.static_id or None,
        )
        output = arguments.out_dir / f"{section.name}.vcs"
        _atomic_write(output, packed)
        parsed = parse_vcs(output)
        print(json.dumps(_summary(output, parsed), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VcsError as error:
        print(f"vcs_v6: error: {error}", file=sys.stderr)
        raise SystemExit(2)
