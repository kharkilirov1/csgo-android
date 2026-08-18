#!/usr/bin/env python3
"""Regression tests for the release-only extras_dir.vpk sanitizer."""

from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

import sanitize_android_release_vpk as sanitizer
import verify_android_shader_release as shader_release


ROOT = Path(__file__).resolve().parents[1]
SOURCE_VPK = ROOT / "android" / "csgo-launcher" / "assets" / "extras_dir.vpk"
SOURCE_SHA256 = "383f5f754272439f668baf66fe34f47a47eccddb1d9f13ad20af3e3956fd777c"
SANITIZED_SHA256 = "d24a4ed62db4c39d9db5f7160bdf9fc889efaeefa7c199e7b799aa14b9a49dbe"
EXPECTED_REMOVED_PATHS = {
    "shaders/fxc/skin_ps20b.vcs",
    "shaders/fxc/skin_vs20.vcs",
    "shaders/fxc/vertexlit_and_unlit_generic_ps20.vcs",
    "shaders/fxc/vertexlit_and_unlit_generic_ps20b.vcs",
    "shaders/fxc/vertexlit_and_unlit_generic_vs20.vcs",
}


class AndroidReleaseVpkSanitizerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_bytes = SOURCE_VPK.read_bytes()
        cls.source = sanitizer.parse_vpk(cls.source_bytes)

    def test_source_inventory_is_pinned_to_the_reviewed_archive(self) -> None:
        self.assertEqual(hashlib.sha256(self.source_bytes).hexdigest(), SOURCE_SHA256)
        self.assertEqual(len(self.source.entries), 65)
        vcs_paths = {entry.path for entry in self.source.entries if entry.extension.casefold() == "vcs"}
        self.assertEqual(vcs_paths, EXPECTED_REMOVED_PATHS)

    def test_sanitization_is_deterministic_and_preserves_retained_semantics(self) -> None:
        first, first_report = sanitizer.build_sanitized_vpk(self.source)
        second, second_report = sanitizer.build_sanitized_vpk(self.source)
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(hashlib.sha256(first).hexdigest(), SANITIZED_SHA256)
        self.assertEqual(first_report["input_entries"], 65)
        self.assertEqual(first_report["kept_entries"], 60)
        self.assertEqual(first_report["removed_entries"], 5)
        self.assertEqual(set(first_report["removed_paths"]), EXPECTED_REMOVED_PATHS)

        rebuilt = sanitizer.parse_vpk(first)
        source_by_path = {entry.path: entry for entry in self.source.entries}
        rebuilt_by_path = {entry.path: entry for entry in rebuilt.entries}
        self.assertFalse(any(path.casefold().endswith(".vcs") for path in rebuilt_by_path))
        self.assertEqual(set(rebuilt_by_path), set(source_by_path) - EXPECTED_REMOVED_PATHS)
        for path, rebuilt_entry in rebuilt_by_path.items():
            source_entry = source_by_path[path]
            self.assertEqual(rebuilt_entry.extension, source_entry.extension, path)
            self.assertEqual(rebuilt_entry.directory, source_entry.directory, path)
            self.assertEqual(rebuilt_entry.stem, source_entry.stem, path)
            self.assertEqual(rebuilt_entry.crc32, source_entry.crc32, path)
            self.assertEqual(rebuilt_entry.preload, source_entry.preload, path)
            self.assertEqual(rebuilt_entry.archive_index, source_entry.archive_index, path)
            self.assertEqual(rebuilt_entry.length, source_entry.length, path)
            self.assertEqual(rebuilt_entry.data, source_entry.data, path)
            self.assertEqual(rebuilt_entry.semantic_digest, source_entry.semantic_digest, path)

    def test_original_artifact_fails_and_sanitized_artifact_passes_shader_gate(self) -> None:
        sanitized, _ = sanitizer.build_sanitized_vpk(self.source)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original_apk = root / "original.apk"
            sanitized_apk = root / "sanitized.apk"
            with zipfile.ZipFile(original_apk, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("assets/extras_dir.vpk", self.source_bytes)
            with zipfile.ZipFile(sanitized_apk, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("assets/extras_dir.vpk", sanitized)

            original_report = shader_release.verify_artifact(original_apk)
            sanitized_report = shader_release.verify_artifact(sanitized_apk)
            self.assertFalse(original_report["ok"])
            self.assertEqual(len(original_report["nested_shader_payloads"]), 5)
            self.assertTrue(sanitized_report["ok"], sanitized_report["failures"])
            self.assertEqual(sanitized_report["inspected_vpk_count"], 1)

    def test_inventory_drift_is_rejected_instead_of_silently_repacked(self) -> None:
        entries_without_one_shader = tuple(
            entry
            for entry in self.source.entries
            if entry.path != "shaders/fxc/skin_vs20.vcs"
        )
        drifted = sanitizer.VpkArchive(
            entries=entries_without_one_shader,
            tree=self.source.tree,
            file_data=self.source.file_data,
        )
        with self.assertRaisesRegex(sanitizer.VpkError, "shader inventory"):
            sanitizer.build_sanitized_vpk(drifted)

    def test_corruption_and_in_place_output_are_rejected_without_overwrite(self) -> None:
        corrupted = bytearray(self.source_bytes)
        corrupted[len(corrupted) // 2] ^= 0x01
        with self.assertRaises(sanitizer.VpkError):
            sanitizer.parse_vpk(bytes(corrupted))

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.vpk"
            output = root / "output.vpk"
            source.write_bytes(self.source_bytes)
            output.write_bytes(b"sentinel")
            with self.assertRaisesRegex(sanitizer.VpkError, "in place"):
                sanitizer.sanitize_file(source, source)

            bad_source = root / "bad.vpk"
            bad_source.write_bytes(corrupted)
            with self.assertRaises(sanitizer.VpkError):
                sanitizer.sanitize_file(bad_source, output)
            self.assertEqual(output.read_bytes(), b"sentinel")
            self.assertEqual(source.read_bytes(), self.source_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
