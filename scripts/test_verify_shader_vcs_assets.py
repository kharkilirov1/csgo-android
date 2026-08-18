#!/usr/bin/env python3
"""Regression tests for the Android VCS asset contract."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

import vcs_v6
import verify_shader_vcs_assets as verifier


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
MANIFEST_PATH = SCRIPT_DIR / "shader_vcs_manifest.json"


def expanded_coverage(asset: dict) -> dict[int, set[int]]:
    coverage: dict[int, set[int]] = {}
    for group in asset["coverage"]["groups"]:
        for static_id in group["static_ids"]:
            coverage[static_id] = set(group["dynamic_ids"])
    return coverage


def synthetic_bytecode(shader_model: str, static_id: int, dynamic_id: int) -> bytes:
    token = verifier.SHADER_MODEL_TOKENS[shader_model]
    # A minimal structural token stream for verifier tests. Production assets
    # still need runtime translation/creation as their executable witness.
    return struct.pack("<III", token, static_id ^ dynamic_id, verifier.DX9_END_TOKEN)


def write_synthetic_asset(root: Path, asset: dict, combos: dict[int, set[int]] | None = None) -> Path:
    if combos is None:
        combos = expanded_coverage(asset)
    bytecodes = {
        static_id: {
            dynamic_id: synthetic_bytecode(asset["shader_model"], static_id, dynamic_id)
            for dynamic_id in sorted(dynamic_ids)
        }
        for static_id, dynamic_ids in combos.items()
    }
    data = vcs_v6.pack_vcs_v6(
        total_combos=asset["total_combos"],
        dynamic_combos=asset["dynamic_combos"],
        combos=bytecodes,
        flags=asset["flags"],
        centroid_mask=asset["centroid_mask"],
        source_crc32=asset["source_crc32"],
        compression="raw",
    )
    path = root.joinpath(*asset["path"].split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class ShaderVcsAssetVerifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def run_cli(self, root: Path) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = verifier.main([str(root), "--manifest", str(MANIFEST_PATH), "--json"])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_synthetic_bundle_matching_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vcs-contract-positive-") as temporary:
            root = Path(temporary)
            for asset in self.manifest["required"]:
                write_synthetic_asset(root, asset)

            status, stdout, stderr = self.run_cli(root)
            self.assertEqual(status, 0, stderr)
            report = json.loads(stdout)
            self.assertTrue(report["ok"])
            self.assertEqual(report["manifest_version"], 2)
            self.assertEqual(
                report["coverage_scope"],
                "observed_static_ids_with_worklist_valid_dynamics",
            )
            self.assertFalse(report["full_shader_coverage"])
            self.assertTrue(report["requires_runtime_shader_creation_witness"])
            self.assertEqual(report["failures"], [])

    def test_renamed_valid_vcs_surrogates_fail_contract(self) -> None:
        surrogate_vs = ROOT / "materialsystem/stdshaders/shaders/fxc/customclothing_vs20.vcs"
        surrogate_ps = ROOT / "materialsystem/stdshaders/shaders/fxc/customclothing_ps20b.vcs"
        with tempfile.TemporaryDirectory(prefix="vcs-contract-negative-") as temporary:
            root = Path(temporary)
            for asset in self.manifest["required"]:
                target = root.joinpath(*asset["path"].split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(surrogate_vs if asset["path"].startswith("vsh/") else surrogate_ps, target)

            status, stdout, stderr = self.run_cli(root)
            self.assertEqual(status, 1)
            self.assertNotIn("PASS:", stdout)
            report = json.loads(stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(report["failures"])
            self.assertTrue(
                any("shader_model expected" in failure for failure in report["failures"])
            )
            self.assertIn("contract violation", stderr)

    def test_required_coverage_allows_additional_static_records(self) -> None:
        asset = next(
            asset
            for asset in self.manifest["required"]
            if asset["path"] == "vsh/vertexlit_and_unlit_generic_vs30.vcs"
        )
        combos = expanded_coverage(asset)
        combos[0] = {0}
        with tempfile.TemporaryDirectory(prefix="vcs-contract-superset-") as temporary:
            root = Path(temporary)
            write_synthetic_asset(root, asset, combos)
            _record, errors = verifier.validate_asset(root, asset)
            self.assertEqual(errors, [])

    def test_missing_required_dynamic_id_fails_contract(self) -> None:
        asset = next(
            asset
            for asset in self.manifest["required"]
            if asset["path"] == "psh/vertexlit_and_unlit_generic_ps30.vcs"
        )
        combos = expanded_coverage(asset)
        combos[16343040].remove(26)
        with tempfile.TemporaryDirectory(prefix="vcs-contract-missing-") as temporary:
            root = Path(temporary)
            write_synthetic_asset(root, asset, combos)
            _record, errors = verifier.validate_asset(root, asset)
            self.assertTrue(any("static 16343040 dynamic IDs expected" in error for error in errors))

    def test_required_coverage_allows_additional_dynamic_records(self) -> None:
        asset = next(
            asset
            for asset in self.manifest["required"]
            if asset["path"] == "psh/vertexlit_and_unlit_generic_ps30.vcs"
        )
        combos = expanded_coverage(asset)
        combos[16343040].add(1)
        with tempfile.TemporaryDirectory(prefix="vcs-contract-dynamic-superset-") as temporary:
            root = Path(temporary)
            write_synthetic_asset(root, asset, combos)
            _record, errors = verifier.validate_asset(root, asset)
            self.assertEqual(errors, [])

    def test_bytecode_without_end_token_fails_contract(self) -> None:
        asset = self.manifest["required"][0]
        with tempfile.TemporaryDirectory(prefix="vcs-contract-bytecode-") as temporary:
            root = Path(temporary)
            path = write_synthetic_asset(root, asset)
            parsed = vcs_v6.parse_vcs(path)
            broken = {
                static_id: {
                    dynamic_id: bytecode[:-4] + struct.pack("<I", 0)
                    for dynamic_id, bytecode in dynamic.items()
                }
                for static_id, dynamic in parsed.combos.items()
            }
            path.write_bytes(
                vcs_v6.pack_vcs_v6(
                    total_combos=asset["total_combos"],
                    dynamic_combos=asset["dynamic_combos"],
                    combos=broken,
                    flags=asset["flags"],
                    centroid_mask=asset["centroid_mask"],
                    source_crc32=asset["source_crc32"],
                    compression="raw",
                )
            )
            _record, errors = verifier.validate_asset(root, asset)
            self.assertTrue(any("does not end with D3DSIO_END" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
