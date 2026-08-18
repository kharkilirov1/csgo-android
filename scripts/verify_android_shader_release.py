#!/usr/bin/env python3
"""Fail-closed Android shader content and APK publication preflight.

The publishable APK must not redistribute VCS bytecode.  A complete shader
tree is supplied separately by its owner (or generated locally) and is
validated against every checked-in DX9 shader helper used by this checkout.
"""

from __future__ import annotations

import argparse
import ast
import bz2
from dataclasses import dataclass
import hashlib
import json
import lzma
from pathlib import Path, PurePosixPath
import re
import struct
import sys
from typing import Any
import zipfile

from vcs_v6 import VcsError, parse_vcs


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_CONTRACT = SCRIPT_DIR / "android_shader_release_contract.json"

DX9_END_TOKEN = 0x0000FFFF
VS_1_1_TOKEN = 0xFFFE0101
VS_2_0_TOKEN = 0xFFFE0200
VS_3_0_TOKEN = 0xFFFE0300
PS_1_1_TOKEN = 0xFFFF0101
PS_1_4_TOKEN = 0xFFFF0104
PS_2_0_TOKEN = 0xFFFF0200
PS_2_B_TOKEN = 0xFFFF0201
PS_3_0_TOKEN = 0xFFFF0300
VERTEX_TOKENS = {VS_1_1_TOKEN, VS_2_0_TOKEN, VS_3_0_TOKEN}
PIXEL_TOKENS = {PS_1_1_TOKEN, PS_1_4_TOKEN, PS_2_0_TOKEN, PS_2_B_TOKEN, PS_3_0_TOKEN}

VPK_SIGNATURE = 0x55AA1234
VPK_V1_HEADER = struct.Struct("<III")
VPK_V2_HEADER = struct.Struct("<IIIIIII")
VPK_ENTRY = struct.Struct("<IHHIIH")

_INDEX_CLASS = r"class\s+\w+_{kind}_Index\s*\{{([\s\S]*?)\n\}};"
_INTEGER_SETTER = re.compile(
    r"void\s+Set(?P<name>\w+)\s*\(\s*int\s+i\s*\)"
    r"[\s\S]*?Assert\s*\(\s*i\s*>=\s*(?P<minimum>-?\d+)"
    r"\s*&&\s*i\s*<=\s*(?P<maximum>-?\d+)\s*\)"
)


class ContractError(ValueError):
    """The checked-in release contract or helper inventory is malformed."""


@dataclass(frozen=True)
class ExpectedAsset:
    path: str
    stage: str
    total_combos: int | None
    dynamic_combos: int | None
    shader_token: int | None
    source: str


def load_contract(path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read contract {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError("contract root must be an object")
    return value


def _safe_relative(value: str, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{label} must be a non-empty string")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ContractError(f"{label} must be a normalized relative path: {value!r}")
    return path


def _combo_product(text: str, kind: str, source: str) -> int:
    match = re.search(_INDEX_CLASS.format(kind=kind), text)
    if match is None:
        raise ContractError(f"{source}: missing {kind} index class")
    product = 1
    names: set[str] = set()
    for setter in _INTEGER_SETTER.finditer(match.group(1)):
        name = setter.group("name")
        minimum = int(setter.group("minimum"))
        maximum = int(setter.group("maximum"))
        if name in names:
            raise ContractError(f"{source}: duplicate {kind} combo setter {name}")
        if minimum < 0 or maximum < minimum:
            raise ContractError(f"{source}: invalid {kind} range for {name}")
        names.add(name)
        product *= maximum - minimum + 1
    if not 0 < product <= 0xFFFFFFFF:
        raise ContractError(f"{source}: {kind} combo product is out of uint32 range")
    return product


def _token_for_name(path: str) -> tuple[str, int | None]:
    stem = PurePosixPath(path).stem.lower()
    suffixes = (
        (r"_vs11$", "vertex", VS_1_1_TOKEN),
        (r"_vs(?:20|20b)$", "vertex", VS_2_0_TOKEN),
        (r"_vs30$", "vertex", VS_3_0_TOKEN),
        (r"_ps11$", "pixel", PS_1_1_TOKEN),
        (r"_ps14$", "pixel", PS_1_4_TOKEN),
        (r"_ps20$", "pixel", PS_2_0_TOKEN),
        (r"_ps20b$", "pixel", PS_2_B_TOKEN),
        (r"_ps(?:30|30b)$", "pixel", PS_3_0_TOKEN),
    )
    for pattern, stage, token in suffixes:
        if re.search(pattern, stem):
            return stage, token
    return "unknown", None


def _insert_expected(result: dict[str, ExpectedAsset], asset: ExpectedAsset) -> None:
    normalized = _safe_relative(asset.path, "asset path").as_posix().lower()
    if not normalized.endswith(".vcs"):
        raise ContractError(f"asset path must end in .vcs: {asset.path}")
    normalized_asset = ExpectedAsset(
        path=normalized,
        stage=asset.stage,
        total_combos=asset.total_combos,
        dynamic_combos=asset.dynamic_combos,
        shader_token=asset.shader_token,
        source=asset.source,
    )
    existing = result.get(normalized)
    if existing is not None:
        if (
            existing.stage != normalized_asset.stage
            or existing.total_combos != normalized_asset.total_combos
            or existing.dynamic_combos != normalized_asset.dynamic_combos
            or existing.shader_token != normalized_asset.shader_token
        ):
            raise ContractError(f"conflicting expected asset path: {normalized}")
        return
    result[normalized] = normalized_asset


def _active_source_files(repo_root: Path, inventory: dict[str, Any]) -> tuple[Path, list[Path]]:
    spec = inventory.get("active_sources")
    if not isinstance(spec, dict):
        raise ContractError("inventory.active_sources must be an object")
    wscript_relative = _safe_relative(spec.get("wscript"), "inventory.active_sources.wscript")
    shader_root_relative = _safe_relative(
        spec.get("shader_root"), "inventory.active_sources.shader_root"
    )
    wscript = repo_root.joinpath(*wscript_relative.parts)
    shader_root = repo_root.joinpath(*shader_root_relative.parts).resolve()
    try:
        syntax = ast.parse(wscript.read_text(encoding="utf-8"), filename=str(wscript))
    except (OSError, UnicodeError, SyntaxError) as error:
        raise ContractError(f"cannot parse active shader wscript: {error}") from error
    source_lists: list[list[str]] = []
    for node in ast.walk(syntax):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "source" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            raise ContractError("stdshader wscript source must be a literal list")
        values: list[str] = []
        for item in node.value.elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                raise ContractError("stdshader wscript source entries must be literal strings")
            values.append(item.value)
        source_lists.append(values)
    if len(source_lists) != 1:
        raise ContractError(f"expected one stdshader source list, found {len(source_lists)}")
    sources = source_lists[0]
    expected_count = spec.get("expected_source_count")
    if expected_count != len(sources):
        raise ContractError(
            f"active shader source count mismatch: contract={expected_count} derived={len(sources)}"
        )
    source_payload = ("\n".join(sources) + "\n").encode("utf-8")
    source_digest = hashlib.sha256(source_payload).hexdigest()
    if spec.get("source_list_sha256") != source_digest:
        raise ContractError(
            "active shader source digest mismatch: "
            f"contract={spec.get('source_list_sha256')} derived={source_digest}"
        )
    resolved: list[Path] = []
    for source in sources:
        candidate = (shader_root / source).resolve()
        if not candidate.is_file():
            raise ContractError(f"active shader source does not exist: {source}")
        resolved.append(candidate)
    return shader_root, resolved


def _helper_asset(helper: Path, target_dir: str, repo_root: Path) -> ExpectedAsset:
    text = helper.read_text(encoding="utf-8", errors="strict")
    static_combos = _combo_product(text, "Static", helper.relative_to(repo_root).as_posix())
    dynamic_combos = _combo_product(text, "Dynamic", helper.relative_to(repo_root).as_posix())
    total_combos = static_combos * dynamic_combos
    if total_combos > 0xFFFFFFFF:
        raise ContractError(f"{helper}: total combo product exceeds uint32")
    relative = f"{target_dir}/{helper.stem}.vcs".lower()
    stage, token = _token_for_name(relative)
    if target_dir == "vsh":
        stage = "vertex"
    elif target_dir == "psh":
        stage = "pixel"
    if stage not in {"vertex", "pixel"}:
        raise ContractError(f"{helper}: cannot derive DX9 shader stage from helper name")
    return ExpectedAsset(relative, stage, total_combos, dynamic_combos, token, helper.as_posix())


def derive_expected_assets(repo_root: Path, contract: dict[str, Any]) -> dict[str, ExpectedAsset]:
    repo_root = repo_root.resolve()
    inventory = contract.get("inventory")
    if not isinstance(inventory, dict):
        raise ContractError("inventory must be an object")
    helper_roots = inventory.get("helper_roots")
    if not isinstance(helper_roots, list) or not helper_roots:
        raise ContractError("inventory.helper_roots must be a non-empty list")
    helper_by_name: dict[str, tuple[Path, str]] = {}
    include_search: list[Path] = []
    for index, helper_root in enumerate(helper_roots):
        label = f"inventory.helper_roots[{index}]"
        if not isinstance(helper_root, dict):
            raise ContractError(f"{label} must be an object")
        source_dir = _safe_relative(helper_root.get("source_dir"), f"{label}.source_dir")
        target_dir = _safe_relative(helper_root.get("target_dir"), f"{label}.target_dir").as_posix()
        if "/" in target_dir or target_dir not in {"fxc", "vsh", "psh"}:
            raise ContractError(f"{label}.target_dir must be fxc, vsh, or psh")
        if helper_root.get("source_suffix") != ".inc":
            raise ContractError(f"{label}.source_suffix must be .inc")
        directory = repo_root.joinpath(*source_dir.parts).resolve()
        if not directory.is_dir():
            raise ContractError(f"{label}.source_dir does not exist: {source_dir}")
        include_search.append(directory)
        for helper in directory.glob("*.inc"):
            key = helper.name.lower()
            if key in helper_by_name:
                raise ContractError(f"helper filename collides across roots: {helper.name}")
            helper_by_name[key] = (helper.resolve(), target_dir)

    shader_root, entry_sources = _active_source_files(repo_root, inventory)
    include_search.insert(0, shader_root)
    visited: set[Path] = set()
    active_helpers: dict[str, tuple[Path, str]] = {}
    source_texts: dict[Path, str] = {}

    def resolve_include(parent: Path, include: str) -> Path | None:
        normalized = Path(include.replace("\\", "/"))
        candidates = [parent.parent / normalized, *(directory / normalized for directory in include_search)]
        return next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)

    def walk_source(path: Path) -> None:
        path = path.resolve()
        if path in visited:
            return
        visited.add(path)
        try:
            # Source SDK-era files are a mix of UTF-8 and Windows-1252.  The
            # include/literal grammar inspected here is ASCII-compatible.
            text = path.read_text(encoding="latin-1")
        except (OSError, UnicodeError) as error:
            raise ContractError(f"cannot read active shader source {path}: {error}") from error
        source_texts[path] = text
        for match in re.finditer(r'^\s*#include\s+"([^"]+)"', text, re.MULTILINE):
            include = match.group(1)
            resolved = resolve_include(path, include)
            if include.lower().endswith(".inc"):
                if resolved is not None:
                    helper_info = helper_by_name.get(resolved.name.lower())
                    if helper_info is not None:
                        active_helpers[resolved.name.lower()] = helper_info
                continue
            if resolved is not None and (
                resolved == shader_root or shader_root in resolved.parents
            ):
                walk_source(resolved)

    for source in entry_sources:
        walk_source(source)

    result: dict[str, ExpectedAsset] = {}
    for helper, target_dir in active_helpers.values():
        _insert_expected(result, _helper_asset(helper, target_dir, repo_root))

    # A few legacy passes name their VCS directly instead of including the
    # generated index helper in that translation unit. Resolve those literals
    # back to a helper when one exists; legacy assembly names remain vsh/psh.
    direct_pattern = re.compile(r'\bSet(Vertex|Pixel)Shader\s*\(\s*"([^"]+)"')
    for source, text in source_texts.items():
        for match in direct_pattern.finditer(text):
            stage = "vertex" if match.group(1) == "Vertex" else "pixel"
            name = match.group(2).lower()
            helper_info = helper_by_name.get(f"{name}.inc")
            if helper_info is not None:
                _insert_expected(result, _helper_asset(helper_info[0], helper_info[1], repo_root))
            else:
                target = "vsh" if stage == "vertex" else "psh"
                _insert_expected(
                    result,
                    ExpectedAsset(f"{target}/{name}.vcs", stage, None, None, None, source.as_posix()),
                )

    extras = inventory.get("extra_helper_assets")
    if not isinstance(extras, list):
        raise ContractError("inventory.extra_helper_assets must be a list")
    for index, extra in enumerate(extras):
        label = f"inventory.extra_helper_assets[{index}]"
        if not isinstance(extra, dict):
            raise ContractError(f"{label} must be an object")
        helper_relative = _safe_relative(extra.get("helper"), f"{label}.helper")
        target_dir = _safe_relative(extra.get("target_dir"), f"{label}.target_dir").as_posix()
        helper = repo_root.joinpath(*helper_relative.parts)
        if not helper.is_file() or helper.name.lower() not in helper_by_name:
            raise ContractError(f"{label}.helper is not in a declared helper root")
        _insert_expected(result, _helper_asset(helper, target_dir, repo_root))
    return dict(sorted(result.items()))


def _inventory_digest(expected: dict[str, ExpectedAsset], geometry: bool) -> str:
    lines = []
    for path, asset in sorted(expected.items()):
        if geometry:
            total = "*" if asset.total_combos is None else str(asset.total_combos)
            dynamic = "*" if asset.dynamic_combos is None else str(asset.dynamic_combos)
            lines.append(f"{path}\t{total}\t{dynamic}")
        else:
            lines.append(path)
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_contract(repo_root: Path, contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("version") != 1:
        failures.append("contract version must be 1")
    if contract.get("contract") != "android_external_shader_content":
        failures.append("contract name must be android_external_shader_content")
    if contract.get("runtime_path_id") != "PLATFORM" or contract.get("runtime_root") != "shaders":
        failures.append("runtime root must be PLATFORM/shaders")
    if contract.get("distribution_model") != "external_user_owned_or_locally_generated":
        failures.append("distribution_model must keep shader content external")
    if contract.get("bundle_vcs_in_apk") is not False:
        failures.append("bundle_vcs_in_apk must be false")
    if contract.get("provenance_is_human_gate") is not True:
        failures.append("provenance_is_human_gate must be true")
    if contract.get("runtime_shader_creation_witness_required") is not True:
        failures.append("runtime_shader_creation_witness_required must be true")

    try:
        expected = derive_expected_assets(repo_root, contract)
    except (ContractError, OSError, UnicodeError) as error:
        failures.append(str(error))
        return failures
    inventory = contract.get("inventory", {})
    if inventory.get("coverage") != "all_android_linked_dx9_shader_paths":
        failures.append("inventory.coverage must be all_android_linked_dx9_shader_paths")
    if inventory.get("expected_count") != len(expected):
        failures.append(
            f"inventory.expected_count mismatch: manifest={inventory.get('expected_count')} derived={len(expected)}"
        )
    path_digest = _inventory_digest(expected, geometry=False)
    if inventory.get("path_set_sha256") != path_digest:
        failures.append(
            f"inventory.path_set_sha256 mismatch: manifest={inventory.get('path_set_sha256')} derived={path_digest}"
        )
    geometry_digest = _inventory_digest(expected, geometry=True)
    if inventory.get("geometry_sha256") != geometry_digest:
        failures.append(
            f"inventory.geometry_sha256 mismatch: manifest={inventory.get('geometry_sha256')} derived={geometry_digest}"
        )

    sparse_spec = contract.get("sparse_probe_manifest")
    if not isinstance(sparse_spec, dict):
        failures.append("sparse_probe_manifest must be an object")
        return failures
    try:
        sparse_path = _safe_relative(sparse_spec.get("path"), "sparse_probe_manifest.path")
        sparse = json.loads(repo_root.joinpath(*sparse_path.parts).read_text(encoding="utf-8"))
    except (ContractError, OSError, UnicodeError, json.JSONDecodeError) as error:
        failures.append(f"cannot validate sparse probe manifest: {error}")
        return failures
    required = sparse.get("required")
    if sparse_spec.get("release_qualifying") is not False or sparse.get("release_qualifying") is not False:
        failures.append("sparse probe manifest must be explicitly non-release-qualifying")
    if sparse.get("purpose") != "runtime_probe_only":
        failures.append("sparse probe manifest purpose must be runtime_probe_only")
    if sparse.get("full_shader_coverage") is not False:
        failures.append("sparse probe manifest must keep full_shader_coverage=false")
    if not isinstance(required, list) or len(required) != sparse_spec.get("expected_count"):
        failures.append("sparse probe manifest required count changed")
    return failures


def _bytecode_tokens(parsed: Any) -> set[int]:
    tokens: set[int] = set()
    for dynamic in parsed.combos.values():
        for bytecode in dynamic.values():
            if len(bytecode) < 8 or len(bytecode) % 4:
                raise VcsError("DX9 bytecode is not a complete DWORD token stream")
            token = struct.unpack_from("<I", bytecode)[0]
            if struct.unpack_from("<I", bytecode, len(bytecode) - 4)[0] != DX9_END_TOKEN:
                raise VcsError("DX9 bytecode does not end with D3DSIO_END")
            tokens.add(token)
    if not tokens:
        raise VcsError("VCS contains no materialized shader bytecode")
    return tokens


def verify_content(root: Path, expected: dict[str, ExpectedAsset]) -> dict[str, Any]:
    failures: list[str] = []
    actual: dict[str, Path] = {}
    case_collisions: set[str] = set()
    if root.is_dir():
        for path in root.rglob("*"):
            if not (path.is_file() or path.is_symlink()) or path.suffix.lower() != ".vcs":
                continue
            relative = path.relative_to(root).as_posix()
            normalized = relative.lower()
            if normalized in actual:
                case_collisions.add(normalized)
            else:
                actual[normalized] = path
    else:
        failures.append(f"shader root is not a directory: {root}")

    expected_paths = set(expected)
    actual_paths = set(actual)
    missing = sorted(expected_paths - actual_paths)
    unexpected = sorted(actual_paths - expected_paths)
    failures.extend(f"missing: {path}" for path in missing)
    failures.extend(f"unexpected VCS: {path}" for path in unexpected)
    failures.extend(f"case-colliding VCS path: {path}" for path in sorted(case_collisions))

    validated = 0
    assets: list[dict[str, Any]] = []
    for relative in sorted(expected_paths & actual_paths):
        path = actual[relative]
        asset = expected[relative]
        asset_errors: list[str] = []
        record: dict[str, Any] = {"path": relative}
        if path.is_symlink():
            asset_errors.append(f"{relative}: symbolic links are not accepted")
        else:
            try:
                data = path.read_bytes()
                parsed = parse_vcs(data)
                tokens = _bytecode_tokens(parsed)
                record.update(
                    {
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "total_combos": parsed.header.total_combos,
                        "dynamic_combos": parsed.header.dynamic_combos,
                        "materialized_static_combos": len(parsed.combos),
                    }
                )
                if asset.total_combos is not None and (
                    parsed.header.total_combos != asset.total_combos
                    or parsed.header.dynamic_combos != asset.dynamic_combos
                ):
                    asset_errors.append(
                        f"{relative}: combo geometry expected "
                        f"{asset.total_combos}/{asset.dynamic_combos}, got "
                        f"{parsed.header.total_combos}/{parsed.header.dynamic_combos}"
                    )
                if parsed.header.source_crc32 == 0:
                    asset_errors.append(f"{relative}: source CRC32 must be nonzero")
                allowed = {asset.shader_token} if asset.shader_token is not None else (
                    PIXEL_TOKENS if asset.stage == "pixel" else VERTEX_TOKENS
                )
                if not tokens <= allowed:
                    formatted = ", ".join(f"0x{token:08x}" for token in sorted(tokens))
                    asset_errors.append(f"{relative}: wrong DX9 shader model token(s): {formatted}")
            except (OSError, ValueError, VcsError) as error:
                asset_errors.append(f"{relative}: invalid VCS: {error}")
        if asset_errors:
            failures.extend(asset_errors)
            record["validation_errors"] = asset_errors
        else:
            validated += 1
        assets.append(record)

    return {
        "ok": not failures,
        "root": str(root),
        "expected_count": len(expected),
        "actual_count": len(actual),
        "validated_count": validated,
        "missing_count": len(missing),
        "unexpected_count": len(unexpected),
        "failures": failures,
        "assets": assets,
        "runtime_shader_creation_witness_required": True,
        "provenance_is_human_gate": True,
    }


def _read_cstring(data: bytes, position: int, end: int) -> tuple[str, int]:
    terminator = data.find(b"\0", position, end)
    if terminator < 0:
        raise ValueError("unterminated VPK tree string")
    try:
        value = data[position:terminator].decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("VPK tree contains a non-UTF-8 name") from error
    return value, terminator + 1


def list_vpk_entries(data: bytes) -> list[str]:
    if len(data) < VPK_V1_HEADER.size:
        raise ValueError("truncated VPK header")
    signature, version, tree_size = VPK_V1_HEADER.unpack_from(data)
    if signature != VPK_SIGNATURE:
        raise ValueError("bad VPK signature")
    if version == 1:
        header_size = VPK_V1_HEADER.size
    elif version == 2:
        if len(data) < VPK_V2_HEADER.size:
            raise ValueError("truncated VPK v2 header")
        header_size = VPK_V2_HEADER.size
    else:
        raise ValueError(f"unsupported VPK version {version}")
    tree_end = header_size + tree_size
    if tree_end > len(data):
        raise ValueError("VPK directory tree exceeds file size")

    position = header_size
    entries: list[str] = []
    while True:
        extension, position = _read_cstring(data, position, tree_end)
        if not extension:
            break
        while True:
            directory, position = _read_cstring(data, position, tree_end)
            if not directory:
                break
            while True:
                filename, position = _read_cstring(data, position, tree_end)
                if not filename:
                    break
                if position + VPK_ENTRY.size > tree_end:
                    raise ValueError("truncated VPK directory entry")
                _, preload_size, _, _, _, terminator = VPK_ENTRY.unpack_from(data, position)
                position += VPK_ENTRY.size
                if terminator != 0xFFFF:
                    raise ValueError("bad VPK directory entry terminator")
                if position + preload_size > tree_end:
                    raise ValueError("VPK preload data exceeds directory tree")
                position += preload_size
                leaf = filename if extension == " " else f"{filename}.{extension}"
                entries.append(leaf if directory == " " else f"{directory}/{leaf}")
    if any(byte != 0 for byte in data[position:tree_end]):
        raise ValueError("unexpected bytes after VPK directory tree terminator")
    return entries


def _is_shader_payload(name: str) -> bool:
    normalized = name.replace("\\", "/").strip("/").lower()
    return (
        normalized.endswith(".vcs")
        or normalized.startswith("platform/shaders/")
        or "/platform/shaders/" in f"/{normalized}"
        or re.search(r"(?:^|/)shaders/(?:fxc|vsh|psh)(?:/|$)", normalized) is not None
    )


def verify_artifact(artifact: Path) -> dict[str, Any]:
    failures: list[str] = []
    direct: list[str] = []
    nested: list[str] = []
    inspected_vpks = 0
    if not artifact.is_file() or not zipfile.is_zipfile(artifact):
        failures.append(f"artifact is not a readable ZIP/APK: {artifact}")
        return {"ok": False, "artifact": str(artifact), "failures": failures}
    try:
        with zipfile.ZipFile(artifact) as archive:
            seen: set[str] = set()
            for info in archive.infolist():
                normalized = info.filename.replace("\\", "/").strip("/").lower()
                parts = PurePosixPath(normalized).parts
                if not normalized or any(part in {".", ".."} for part in parts):
                    failures.append(f"unsafe APK entry path: {info.filename}")
                    continue
                if normalized in seen:
                    failures.append(f"duplicate APK entry path: {info.filename}")
                seen.add(normalized)
                if _is_shader_payload(normalized):
                    direct.append(info.filename)
                if normalized.endswith(".vpk"):
                    inspected_vpks += 1
                    try:
                        entries = list_vpk_entries(archive.read(info))
                    except (KeyError, OSError, ValueError, RuntimeError) as error:
                        failures.append(f"cannot inspect nested VPK {info.filename}: {error}")
                        continue
                    nested.extend(f"{info.filename}!/{entry}" for entry in entries if _is_shader_payload(entry))
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        failures.append(f"cannot inspect artifact {artifact}: {error}")
    failures.extend(f"bundled shader payload: {name}" for name in direct)
    failures.extend(f"nested VPK shader payload: {name}" for name in nested)
    return {
        "ok": not failures,
        "artifact": str(artifact),
        "inspected_vpk_count": inspected_vpks,
        "direct_shader_payloads": direct,
        "nested_shader_payloads": nested,
        "failures": failures,
    }


def _print_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    if report.get("ok"):
        if "validated_count" in report:
            print(
                f"PASS: {report['validated_count']}/{report['expected_count']} external VCS assets "
                "match the pinned DX9 helper inventory; content remains external; "
                "runtime shader-creation witness still required"
            )
        elif "path_set_sha256" in report:
            print(
                f"PASS: external shader contract pins {report['expected_count']} DX9 assets "
                f"(paths={report['path_set_sha256']} geometry={report['geometry_sha256']})"
            )
        else:
            print(
                f"PASS: artifact contains no direct or nested VCS shader payload "
                f"({report.get('inspected_vpk_count', 0)} VPK inspected)"
            )
        return
    for failure in report.get("failures", []):
        print(f"FAIL: {failure}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--json", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("contract", help="validate the pinned helper-derived inventory")
    content_parser = subparsers.add_parser("content", help="validate an external PLATFORM/shaders root")
    content_parser.add_argument("root", type=Path)
    artifact_parser = subparsers.add_parser("artifact", help="prove an APK/ZIP contains no VCS payload")
    artifact_parser.add_argument("artifact", type=Path)
    inventory_parser = subparsers.add_parser("inventory", help="print the expected external asset inventory")
    inventory_parser.add_argument("--paths", action="store_true", help="include all expected paths")
    args = parser.parse_args(argv)

    try:
        contract = load_contract(args.contract)
        contract_failures = validate_contract(REPO_ROOT, contract)
        expected = derive_expected_assets(REPO_ROOT, contract)
    except ContractError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    if contract_failures:
        _print_report({"ok": False, "failures": contract_failures}, args.json)
        return 2

    if args.command == "contract":
        report = {
            "ok": True,
            "expected_count": len(expected),
            "path_set_sha256": _inventory_digest(expected, geometry=False),
            "geometry_sha256": _inventory_digest(expected, geometry=True),
        }
    elif args.command == "content":
        report = verify_content(args.root, expected)
    elif args.command == "artifact":
        report = verify_artifact(args.artifact)
    else:
        counts = {target: 0 for target in ("fxc", "vsh", "psh")}
        for path in expected:
            counts[path.split("/", 1)[0]] += 1
        report = {
            "ok": True,
            "expected_count": len(expected),
            "counts": counts,
            "path_set_sha256": _inventory_digest(expected, geometry=False),
            "geometry_sha256": _inventory_digest(expected, geometry=True),
        }
        if args.paths:
            report["paths"] = list(expected)
    _print_report(report, args.json)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
