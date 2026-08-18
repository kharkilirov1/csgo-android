#!/usr/bin/env python3
"""Build a release-only bootstrap VPK with shader bytecode removed.

The tracked extras_dir.vpk remains untouched for debug/runtime development.
This tool accepts only the self-contained VPK v2 shape used by that asset,
verifies every indexed payload and VPK checksum, removes .vcs entries and their
data bytes, then regenerates a deterministic VPK v2 with valid self hashes.
"""

from __future__ import annotations

import argparse
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import tempfile
from typing import Iterable
import zlib


VPK_SIGNATURE = 0x55AA1234
VPK_VERSION = 2
VPK_INLINE_ARCHIVE = 0x7FFF
VPK_ENTRY_TERMINATOR = 0xFFFF
VPK_HEADER = struct.Struct("<IIIIIII")
VPK_ENTRY = struct.Struct("<IHHIIH")
VPK_SELF_HASH_SIZE = 48
EXPECTED_SOURCE_SHA256 = "383f5f754272439f668baf66fe34f47a47eccddb1d9f13ad20af3e3956fd777c"
EXPECTED_REMOVED_PATHS = frozenset(
    {
        "shaders/fxc/skin_ps20b.vcs",
        "shaders/fxc/skin_vs20.vcs",
        "shaders/fxc/vertexlit_and_unlit_generic_ps20.vcs",
        "shaders/fxc/vertexlit_and_unlit_generic_ps20b.vcs",
        "shaders/fxc/vertexlit_and_unlit_generic_vs20.vcs",
    }
)


class VpkError(ValueError):
    """The source VPK cannot be sanitized without losing semantics."""


@dataclass(frozen=True)
class VpkEntry:
    extension: str
    directory: str
    stem: str
    crc32: int
    preload: bytes
    archive_index: int
    offset: int
    length: int
    data: bytes

    @property
    def path(self) -> str:
        prefix = "" if self.directory == " " else f"{self.directory}/"
        return f"{prefix}{self.stem}.{self.extension}"

    @property
    def semantic_digest(self) -> str:
        return hashlib.sha256(self.preload + self.data).hexdigest()


@dataclass(frozen=True)
class VpkArchive:
    entries: tuple[VpkEntry, ...]
    tree: bytes
    file_data: bytes


def _read_cstring(data: bytes, position: int, end: int) -> tuple[str, int]:
    terminator = data.find(b"\0", position, end)
    if terminator < 0:
        raise VpkError("unterminated VPK tree string")
    try:
        value = data[position:terminator].decode("utf-8")
    except UnicodeDecodeError as error:
        raise VpkError("VPK tree contains a non-UTF-8 name") from error
    return value, terminator + 1


def _validate_component(value: str, label: str, *, allow_space_root: bool = False) -> None:
    if allow_space_root and value == " ":
        return
    if not value or "\0" in value or "\\" in value:
        raise VpkError(f"invalid {label}: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise VpkError(f"unsafe {label}: {value!r}")
    if label != "directory" and "/" in value:
        raise VpkError(f"invalid {label}: {value!r}")


def _validate_self_hashes(
    raw: bytes,
    tree: bytes,
    archive_md5: bytes,
    self_hash_offset: int,
    self_hashes: bytes,
) -> None:
    if len(self_hashes) != VPK_SELF_HASH_SIZE:
        raise VpkError(
            f"VPK self-hash section must be {VPK_SELF_HASH_SIZE} bytes "
            f"(found {len(self_hashes)})"
        )
    expected_tree = hashlib.md5(tree).digest()
    expected_archive = hashlib.md5(archive_md5).digest()
    expected_total = hashlib.md5(raw[: self_hash_offset + 32]).digest()
    actual_tree, actual_archive, actual_total = (
        self_hashes[:16],
        self_hashes[16:32],
        self_hashes[32:48],
    )
    if actual_tree != expected_tree:
        raise VpkError("VPK directory MD5 does not match its tree")
    if actual_archive != expected_archive:
        raise VpkError("VPK archive-MD5 checksum does not match its section")
    if actual_total != expected_total:
        raise VpkError("VPK whole-file MD5 does not match signed metadata")


def parse_vpk(raw: bytes) -> VpkArchive:
    if len(raw) < VPK_HEADER.size:
        raise VpkError("VPK is smaller than its v2 header")
    (
        signature,
        version,
        tree_size,
        file_data_size,
        archive_md5_size,
        self_hash_size,
        signature_size,
    ) = VPK_HEADER.unpack_from(raw)
    if signature != VPK_SIGNATURE:
        raise VpkError(f"wrong VPK signature: 0x{signature:08x}")
    if version != VPK_VERSION:
        raise VpkError(f"release sanitizer requires VPK v{VPK_VERSION} (found v{version})")
    if archive_md5_size != 0:
        raise VpkError("release sanitizer does not rewrite archive chunk hashes")
    if signature_size != 0:
        raise VpkError("release sanitizer refuses to invalidate a signed VPK")

    tree_start = VPK_HEADER.size
    tree_end = tree_start + tree_size
    data_end = tree_end + file_data_size
    archive_md5_end = data_end + archive_md5_size
    self_hash_end = archive_md5_end + self_hash_size
    file_end = self_hash_end + signature_size
    if file_end != len(raw):
        raise VpkError(f"VPK section sizes describe {file_end} bytes, file has {len(raw)}")

    tree = raw[tree_start:tree_end]
    file_data = raw[tree_end:data_end]
    archive_md5 = raw[data_end:archive_md5_end]
    self_hashes = raw[archive_md5_end:self_hash_end]
    _validate_self_hashes(raw, tree, archive_md5, archive_md5_end, self_hashes)

    entries: list[VpkEntry] = []
    position = tree_start
    seen: set[str] = set()
    while True:
        extension, position = _read_cstring(raw, position, tree_end)
        if not extension:
            break
        _validate_component(extension, "extension")
        while True:
            directory, position = _read_cstring(raw, position, tree_end)
            if not directory:
                break
            _validate_component(directory, "directory", allow_space_root=True)
            while True:
                stem, position = _read_cstring(raw, position, tree_end)
                if not stem:
                    break
                _validate_component(stem, "filename")
                if position + VPK_ENTRY.size > tree_end:
                    raise VpkError("truncated VPK entry metadata")
                crc32, preload_size, archive_index, offset, length, terminator = (
                    VPK_ENTRY.unpack_from(raw, position)
                )
                position += VPK_ENTRY.size
                if terminator != VPK_ENTRY_TERMINATOR:
                    raise VpkError(f"wrong VPK entry terminator for {stem}.{extension}")
                if position + preload_size > tree_end:
                    raise VpkError("VPK preload bytes exceed the directory tree")
                preload = raw[position : position + preload_size]
                position += preload_size
                if archive_index != VPK_INLINE_ARCHIVE:
                    raise VpkError(
                        f"external archive entry cannot be sanitized safely: {stem}.{extension}"
                    )
                if offset + length > len(file_data):
                    raise VpkError(f"VPK data range exceeds file-data section: {stem}.{extension}")
                data = file_data[offset : offset + length]
                entry = VpkEntry(
                    extension=extension,
                    directory=directory,
                    stem=stem,
                    crc32=crc32,
                    preload=preload,
                    archive_index=archive_index,
                    offset=offset,
                    length=length,
                    data=data,
                )
                folded = entry.path.casefold()
                if folded in seen:
                    raise VpkError(f"duplicate or case-colliding VPK path: {entry.path}")
                seen.add(folded)
                actual_crc32 = zlib.crc32(preload + data) & 0xFFFFFFFF
                if actual_crc32 != crc32:
                    raise VpkError(
                        f"CRC32 mismatch for {entry.path}: "
                        f"expected {crc32:08x}, got {actual_crc32:08x}"
                    )
                entries.append(entry)
    if position != tree_end:
        raise VpkError("unexpected bytes after VPK directory-tree terminator")

    cursor = 0
    for entry in sorted(entries, key=lambda item: (item.offset, item.path.casefold())):
        if entry.offset != cursor:
            relation = "overlap" if entry.offset < cursor else "unindexed gap"
            raise VpkError(
                f"VPK file-data section contains an {relation} before {entry.path}: "
                f"expected offset {cursor}, found {entry.offset}"
            )
        cursor += entry.length
    if cursor != len(file_data):
        raise VpkError(
            f"VPK file-data section has {len(file_data) - cursor} unindexed trailing bytes"
        )

    return VpkArchive(entries=tuple(entries), tree=tree, file_data=file_data)


def _group_entries(
    entries: Iterable[VpkEntry],
) -> OrderedDict[str, OrderedDict[str, list[VpkEntry]]]:
    grouped: OrderedDict[str, OrderedDict[str, list[VpkEntry]]] = OrderedDict()
    for entry in entries:
        grouped.setdefault(entry.extension, OrderedDict()).setdefault(entry.directory, []).append(
            entry
        )
    return grouped


def build_sanitized_vpk(source: VpkArchive) -> tuple[bytes, dict[str, object]]:
    kept = tuple(entry for entry in source.entries if entry.extension.casefold() != "vcs")
    removed = tuple(entry for entry in source.entries if entry.extension.casefold() == "vcs")
    removed_paths = frozenset(entry.path for entry in removed)
    if removed_paths != EXPECTED_REMOVED_PATHS:
        missing = sorted(EXPECTED_REMOVED_PATHS - removed_paths)
        unexpected = sorted(removed_paths - EXPECTED_REMOVED_PATHS)
        raise VpkError(
            "release VPK shader inventory differs from the reviewed five entries: "
            f"missing={missing} unexpected={unexpected}"
        )

    new_offsets: dict[str, int] = {}
    data_parts: list[bytes] = []
    cursor = 0
    for entry in sorted(kept, key=lambda item: (item.offset, item.path.casefold())):
        new_offsets[entry.path] = cursor
        data_parts.append(entry.data)
        cursor += entry.length
    file_data = b"".join(data_parts)

    tree = bytearray()
    for extension, directories in _group_entries(kept).items():
        tree += extension.encode("utf-8") + b"\0"
        for directory, entries in directories.items():
            tree += directory.encode("utf-8") + b"\0"
            for entry in entries:
                tree += entry.stem.encode("utf-8") + b"\0"
                tree += VPK_ENTRY.pack(
                    entry.crc32,
                    len(entry.preload),
                    entry.archive_index,
                    new_offsets[entry.path],
                    entry.length,
                    VPK_ENTRY_TERMINATOR,
                )
                tree += entry.preload
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"

    header = VPK_HEADER.pack(
        VPK_SIGNATURE,
        VPK_VERSION,
        len(tree),
        len(file_data),
        0,
        VPK_SELF_HASH_SIZE,
        0,
    )
    directory_md5 = hashlib.md5(tree).digest()
    archive_md5 = hashlib.md5(b"").digest()
    before_total = header + tree + file_data + directory_md5 + archive_md5
    total_md5 = hashlib.md5(before_total).digest()
    output = before_total + total_md5

    rebuilt = parse_vpk(output)
    source_by_path = {entry.path: entry for entry in source.entries}
    rebuilt_by_path = {entry.path: entry for entry in rebuilt.entries}
    if set(rebuilt_by_path) != {entry.path for entry in kept}:
        raise VpkError("rebuilt VPK path set differs from the kept source entries")
    for path, rebuilt_entry in rebuilt_by_path.items():
        original = source_by_path[path]
        if (
            rebuilt_entry.crc32,
            rebuilt_entry.preload,
            rebuilt_entry.archive_index,
            rebuilt_entry.length,
            rebuilt_entry.data,
        ) != (
            original.crc32,
            original.preload,
            original.archive_index,
            original.length,
            original.data,
        ):
            raise VpkError(f"rebuilt VPK changed retained entry semantics: {path}")

    report: dict[str, object] = {
        "input_entries": len(source.entries),
        "kept_entries": len(kept),
        "removed_entries": len(removed),
        "removed_paths": [entry.path for entry in removed],
        "output_size": len(output),
        "output_sha256": hashlib.sha256(output).hexdigest(),
    }
    return output, report


def sanitize_file(source_path: Path, output_path: Path) -> dict[str, object]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise VpkError("refusing to modify the source VPK in place")
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise VpkError(
            "release VPK source differs from the reviewed archive: "
            f"expected sha256={EXPECTED_SOURCE_SHA256}, got {source_sha256}"
        )
    output_bytes, report = build_sanitized_vpk(parse_vpk(source_bytes))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(output_bytes)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, output_path)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = sanitize_file(args.source, args.output)
    except (OSError, VpkError) as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(
            "Sanitized release VPK: "
            f"kept={report['kept_entries']} removed={report['removed_entries']} "
            f"sha256={report['output_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
