#!/usr/bin/env python3
"""Regression tests for the external-only Android shader release contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

import verify_android_shader_release as release
from vcs_v6 import pack_vcs_v6


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
CONTRACT_PATH = SCRIPT_DIR / "android_shader_release_contract.json"


def shader_bytecode(token: int, salt: int) -> bytes:
    return struct.pack("<III", token, salt & 0xFFFFFFFF, release.DX9_END_TOKEN)


def write_synthetic_corpus(root: Path, expected: dict[str, release.ExpectedAsset]) -> None:
    for index, asset in enumerate(expected.values(), start=1):
        token = asset.shader_token
        if token is None:
            token = release.PS_2_B_TOKEN if asset.stage == "pixel" else release.VS_2_0_TOKEN
        total = asset.total_combos or 1
        dynamic = asset.dynamic_combos or 1
        packed = pack_vcs_v6(
            total_combos=total,
            dynamic_combos=dynamic,
            combos={0: {0: shader_bytecode(token, index)}},
            source_crc32=index,
            compression="raw",
        )
        destination = root.joinpath(*asset.path.split("/"))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(packed)


def make_vpk(entries: list[str]) -> bytes:
    tree = bytearray()
    grouped: dict[str, dict[str, list[str]]] = {}
    for entry in entries:
        normalized = entry.replace("\\", "/").strip("/")
        directory, leaf = normalized.rsplit("/", 1) if "/" in normalized else (" ", normalized)
        filename, extension = leaf.rsplit(".", 1)
        grouped.setdefault(extension, {}).setdefault(directory, []).append(filename)
    for extension, directories in grouped.items():
        tree += extension.encode() + b"\0"
        for directory, filenames in directories.items():
            tree += directory.encode() + b"\0"
            for filename in filenames:
                tree += filename.encode() + b"\0"
                tree += struct.pack("<IHHIIH", 0, 0, 0x7FFF, 0, 0, 0xFFFF)
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"
    return struct.pack("<III", release.VPK_SIGNATURE, 1, len(tree)) + tree


class AndroidShaderReleaseContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = release.load_contract(CONTRACT_PATH)
        cls.expected = release.derive_expected_assets(ROOT, cls.contract)

    def test_inventory_is_pinned_to_all_android_linked_dx9_paths(self) -> None:
        self.assertEqual(len(self.expected), 245)
        counts = {stage: 0 for stage in ("fxc", "vsh", "psh")}
        for path in self.expected:
            counts[path.split("/", 1)[0]] += 1
        self.assertEqual(counts, {"fxc": 243, "vsh": 1, "psh": 1})
        self.assertEqual(release.validate_contract(ROOT, self.contract), [])

    def test_contract_digest_and_count_are_fail_closed(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["inventory"]["expected_count"] -= 1
        self.assertTrue(any("expected_count" in item for item in release.validate_contract(ROOT, changed)))
        changed = copy.deepcopy(self.contract)
        changed["inventory"]["geometry_sha256"] = "0" * 64
        self.assertTrue(any("geometry_sha256" in item for item in release.validate_contract(ROOT, changed)))

    def test_sparse_runtime_probe_is_explicitly_not_release_qualifying(self) -> None:
        sparse = json.loads((SCRIPT_DIR / "shader_vcs_manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(sparse["release_qualifying"])
        self.assertEqual(sparse["purpose"], "runtime_probe_only")
        self.assertFalse(sparse["full_shader_coverage"])
        self.assertEqual(len(sparse["required"]), 8)

    def test_empty_and_sparse_content_fail_with_a_quantified_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = release.verify_content(root, self.expected)
            self.assertFalse(empty["ok"])
            self.assertEqual(empty["expected_count"], 245)
            self.assertEqual(empty["missing_count"], 245)

            sparse = json.loads((SCRIPT_DIR / "shader_vcs_manifest.json").read_text(encoding="utf-8"))
            for asset in sparse["required"]:
                destination = root.joinpath(*asset["path"].split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"not-a-vcs")
            report = release.verify_content(root, self.expected)
            self.assertFalse(report["ok"])
            self.assertEqual(report["missing_count"], 245)
            self.assertEqual(report["unexpected_count"], 8)

    def test_exact_structural_corpus_passes_and_surrogate_fails_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_synthetic_corpus(root, self.expected)
            report = release.verify_content(root, self.expected)
            self.assertTrue(report["ok"], report["failures"][:5])
            self.assertEqual(report["validated_count"], 245)

            simple = root / "fxc" / "accumbuff4sample_ps20b.vcs"
            complex_shader = root / "fxc" / "engine_post_ps30.vcs"
            complex_shader.write_bytes(simple.read_bytes())
            report = release.verify_content(root, self.expected)
            self.assertFalse(report["ok"])
            self.assertTrue(any("combo geometry" in item for item in report["failures"]))

    def test_unexpected_vcs_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_synthetic_corpus(root, self.expected)
            extra = root / "fxc" / "uncontracted_ps20b.vcs"
            extra.write_bytes((root / "fxc" / "accumbuff4sample_ps20b.vcs").read_bytes())
            report = release.verify_content(root, self.expected)
            self.assertFalse(report["ok"])
            self.assertEqual(report["unexpected_count"], 1)

    def test_artifact_rejects_direct_and_nested_vpk_shader_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            safe = root / "safe.apk"
            with zipfile.ZipFile(safe, "w") as archive:
                archive.writestr("assets/extras_dir.vpk", make_vpk(["cfg/bootstrap.cfg"]))
            self.assertTrue(release.verify_artifact(safe)["ok"])

            direct = root / "direct.apk"
            with zipfile.ZipFile(direct, "w") as archive:
                archive.writestr("assets/platform/shaders/fxc/hidden_ps20b.vcs", b"x")
            self.assertFalse(release.verify_artifact(direct)["ok"])

            nested = root / "nested.apk"
            with zipfile.ZipFile(nested, "w") as archive:
                archive.writestr(
                    "assets/extras_dir.vpk",
                    make_vpk(["platform/shaders/fxc/hidden_ps20b.vcs"]),
                )
            report = release.verify_artifact(nested)
            self.assertFalse(report["ok"])
            self.assertTrue(any("nested VPK" in item for item in report["failures"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
