#!/usr/bin/env python3
"""Validate the exact VCS asset contract required by the Android startup trace."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
from typing import Any

from vcs_v6 import VcsError, VcsFile, parse_vcs


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = SCRIPT_DIR / "shader_vcs_manifest.json"
MANIFEST_VERSION = 2

# DWORD shader-version tokens emitted by fxc at the start of DX9 bytecode.
SHADER_MODEL_TOKENS = {
    "vs_2_0": 0xFFFE0200,
    "vs_3_0": 0xFFFE0300,
    "ps_2_b": 0xFFFF0201,
    "ps_3_0": 0xFFFF0300,
}
DX9_END_TOKEN = 0x0000FFFF


class ManifestError(ValueError):
    """The asset contract itself is incomplete or malformed."""


def _require_int(mapping: dict[str, Any], key: str, label: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ManifestError(f"{label}: {key} must be a non-negative integer")
    return value


def _require_id_list(mapping: dict[str, Any], key: str, label: str) -> list[int]:
    values = mapping.get(key)
    if not isinstance(values, list) or not values:
        raise ManifestError(f"{label}: {key} must be a non-empty integer list")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
        raise ManifestError(f"{label}: {key} must contain only non-negative integers")
    if len(values) != len(set(values)):
        raise ManifestError(f"{label}: {key} contains duplicate IDs")
    return values


def _coverage_contract(asset: dict[str, Any]) -> tuple[str, dict[int, set[int]]]:
    label = asset["path"]
    coverage = asset.get("coverage")
    if not isinstance(coverage, dict):
        raise ManifestError(f"{label}: coverage must be an object")
    mode = coverage.get("mode")
    if mode not in {"exact", "required"}:
        raise ManifestError(f"{label}: coverage.mode must be 'exact' or 'required'")
    groups = coverage.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ManifestError(f"{label}: coverage.groups must be a non-empty list")

    total_combos = _require_int(asset, "total_combos", label)
    dynamic_combos = _require_int(asset, "dynamic_combos", label)
    if dynamic_combos == 0:
        raise ManifestError(f"{label}: dynamic_combos must be nonzero")

    expected: dict[int, set[int]] = {}
    for group_index, group in enumerate(groups):
        group_label = f"{label}: coverage.groups[{group_index}]"
        if not isinstance(group, dict):
            raise ManifestError(f"{group_label} must be an object")
        static_ids = _require_id_list(group, "static_ids", group_label)
        dynamic_ids = _require_id_list(group, "dynamic_ids", group_label)
        if any(dynamic_id >= dynamic_combos for dynamic_id in dynamic_ids):
            raise ManifestError(
                f"{group_label}: dynamic ID exceeds dynamic_combos={dynamic_combos}"
            )
        for static_id in static_ids:
            if static_id * dynamic_combos >= total_combos:
                raise ManifestError(
                    f"{group_label}: static ID {static_id} exceeds total combo address space"
                )
            if static_id in expected:
                raise ManifestError(f"{group_label}: static ID {static_id} is repeated")
            expected[static_id] = set(dynamic_ids)
    return mode, expected


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read manifest {path}: {error}") from error
    if not isinstance(manifest, dict):
        raise ManifestError("manifest root must be an object")
    if manifest.get("version") != MANIFEST_VERSION:
        raise ManifestError(f"manifest version must be {MANIFEST_VERSION}")
    if manifest.get("path_id") != "PLATFORM" or manifest.get("root") != "shaders":
        raise ManifestError("manifest must describe PLATFORM/shaders")
    if manifest.get("coverage_scope") != "observed_static_ids_with_worklist_valid_dynamics":
        raise ManifestError(
            "manifest coverage_scope must be "
            "observed_static_ids_with_worklist_valid_dynamics"
        )
    if manifest.get("full_shader_coverage") is not False:
        raise ManifestError("this sparse manifest must declare full_shader_coverage=false")
    if manifest.get("requires_runtime_shader_creation_witness") is not True:
        raise ManifestError("manifest must require a runtime shader-creation witness")
    required = manifest.get("required")
    if not isinstance(required, list) or not required:
        raise ManifestError("manifest.required must be a non-empty list")

    seen_paths: set[str] = set()
    for index, asset in enumerate(required):
        label = f"required[{index}]"
        if not isinstance(asset, dict):
            raise ManifestError(f"{label} must be an object")
        relative = asset.get("path")
        if not isinstance(relative, str) or not relative:
            raise ManifestError(f"{label}.path must be a non-empty string")
        pure_path = PurePosixPath(relative)
        if pure_path.is_absolute() or ".." in pure_path.parts or "\\" in relative:
            raise ManifestError(f"{relative}: path must be a safe POSIX-relative path")
        if relative in seen_paths:
            raise ManifestError(f"duplicate asset path: {relative}")
        seen_paths.add(relative)

        for key in ("total_combos", "dynamic_combos", "source_crc32", "flags", "centroid_mask"):
            _require_int(asset, key, relative)
        shader_model = asset.get("shader_model")
        if shader_model not in SHADER_MODEL_TOKENS:
            raise ManifestError(
                f"{relative}: shader_model must be one of {sorted(SHADER_MODEL_TOKENS)}"
            )
        _coverage_contract(asset)
    return manifest


def _shader_tokens(vcs: VcsFile) -> set[int]:
    tokens: set[int] = set()
    for dynamic in vcs.combos.values():
        for bytecode in dynamic.values():
            if len(bytecode) < 8 or len(bytecode) % 4:
                raise VcsError(
                    "DX9 shader bytecode must be DWORD-aligned and contain version/instructions/end"
                )
            tokens.add(struct.unpack_from("<I", bytecode)[0])
            if struct.unpack_from("<I", bytecode, len(bytecode) - 4)[0] != DX9_END_TOKEN:
                raise VcsError("DX9 shader bytecode does not end with D3DSIO_END")
    return tokens


def validate_asset(root: Path, asset: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    relative = asset["path"]
    path = root.joinpath(*PurePosixPath(relative).parts)
    record: dict[str, Any] = {"path": relative, "exists": path.is_file()}
    errors: list[str] = []
    if not path.is_file():
        errors.append(f"missing: {relative}")
        record["validation_errors"] = errors
        return record, errors

    try:
        data = path.read_bytes()
        parsed = parse_vcs(data)
        tokens = _shader_tokens(parsed)
    except (VcsError, ValueError, OSError) as error:
        errors.append(f"invalid: {relative}: {error}")
        record["error"] = str(error)
        record["validation_errors"] = errors
        return record, errors

    header = parsed.header
    actual_fields = {
        "total_combos": header.total_combos,
        "dynamic_combos": header.dynamic_combos,
        "source_crc32": header.source_crc32,
        "flags": header.flags,
        "centroid_mask": header.centroid_mask,
    }
    record.update(
        size=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        version=header.version,
        **actual_fields,
        materialized_static_combos=len(parsed.combos),
        materialized_dynamic_bytecodes=sum(len(dynamic) for dynamic in parsed.combos.values()),
        shader_version_tokens=[f"0x{token:08x}" for token in sorted(tokens)],
    )

    for key, actual in actual_fields.items():
        expected = asset[key]
        if actual != expected:
            errors.append(f"{relative}: {key} expected {expected}, got {actual}")

    shader_model = asset["shader_model"]
    expected_token = SHADER_MODEL_TOKENS[shader_model]
    if tokens != {expected_token}:
        rendered = ", ".join(f"0x{token:08x}" for token in sorted(tokens)) or "none"
        errors.append(
            f"{relative}: shader_model expected {shader_model} "
            f"(0x{expected_token:08x}), got {rendered}"
        )

    mode, expected_coverage = _coverage_contract(asset)
    actual_static_ids = set(parsed.combos)
    expected_static_ids = set(expected_coverage)
    if mode == "exact" and actual_static_ids != expected_static_ids:
        errors.append(
            f"{relative}: exact static IDs expected {sorted(expected_static_ids)}, "
            f"got {sorted(actual_static_ids)}"
        )
    for static_id, expected_dynamic_ids in expected_coverage.items():
        actual_dynamic_ids = set(parsed.combos.get(static_id, {}))
        coverage_matches = (
            actual_dynamic_ids == expected_dynamic_ids
            if mode == "exact"
            else actual_dynamic_ids.issuperset(expected_dynamic_ids)
        )
        if not coverage_matches:
            errors.append(
                f"{relative}: static {static_id} dynamic IDs expected "
                f"{'exactly' if mode == 'exact' else 'at least'} "
                f"{sorted(expected_dynamic_ids)}, got {sorted(actual_dynamic_ids)}"
            )

    record["shader_model"] = shader_model
    record["coverage_mode"] = mode
    record["validated_static_ids"] = sorted(expected_static_ids)
    if errors:
        record["validation_errors"] = errors
    return record, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="directory containing vsh/ and psh/")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2

    records = []
    failures = []
    for asset in manifest["required"]:
        record, asset_failures = validate_asset(args.root, asset)
        records.append(record)
        failures.extend(asset_failures)

    if args.json:
        print(
            json.dumps(
                {
                    "manifest_version": manifest["version"],
                    "coverage_scope": manifest["coverage_scope"],
                    "full_shader_coverage": manifest["full_shader_coverage"],
                    "requires_runtime_shader_creation_witness": manifest[
                        "requires_runtime_shader_creation_witness"
                    ],
                    "ok": not failures,
                    "assets": records,
                    "failures": failures,
                },
                indent=2,
            )
        )
    else:
        for record in records:
            if record.get("validation_errors"):
                state = "INVALID (" + "; ".join(record["validation_errors"]) + ")"
            else:
                state = (
                    f"OK v{record['version']} model={record['shader_model']} "
                    f"total={record['total_combos']} dynamic={record['dynamic_combos']} "
                    f"static={record['materialized_static_combos']} size={record['size']}"
                )
            print(f"{record['path']}: {state}")

    if failures:
        print(
            f"FAIL: {len(failures)} contract violation(s) across "
            f"{len(records)} required VCS assets",
            file=sys.stderr,
        )
        return 1
    if not args.json:
        print(
            f"PASS: {len(records)}/{len(records)} required VCS assets match "
            "observed static IDs plus their worklist-valid dynamics; "
            "full_shader_coverage=false; "
            "runtime shader creation still required"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
