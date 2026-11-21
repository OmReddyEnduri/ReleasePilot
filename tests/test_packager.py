"""Unit tests for release packaging and SHA256 checksums."""

import os
import tempfile
import unittest
from pathlib import Path
from releasepilot.packager import (
    collect_package_files,
    compute_sha256,
    create_release_bundles,
    verify_checksums,
)


class TestPackager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Create source files
        (self.root / "src").mkdir()
        (self.root / "src" / "main.py").write_text("print('hello')", encoding="utf-8")
        (self.root / "README.md").write_text("# Project", encoding="utf-8")
        (self.root / "dist").mkdir()
        (self.root / "build.log").write_text("log data", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_collect_package_files(self):
        files = collect_package_files(
            source_dir=self.root,
            include_patterns=["src/**", "README.md"],
            exclude_patterns=["dist/**", "*.log"],
        )
        rel_strings = [str(f).replace("\\", "/") for f in files]
        self.assertIn("README.md", rel_strings)
        self.assertIn("src/main.py", rel_strings)
        self.assertNotIn("build.log", rel_strings)

    def test_create_and_verify_bundles(self):
        dist_dir = self.root / "dist"
        archives, sums_file = create_release_bundles(
            source_dir=self.root,
            dist_dir=dist_dir,
            project_name="DemoApp",
            version="1.0.0",
            formats=["zip", "tar.gz"],
            include_patterns=["src/**", "README.md"],
            exclude_patterns=["dist/**"],
            checksum_filename="SHA256SUMS",
        )

        self.assertEqual(len(archives), 2)
        self.assertTrue(sums_file.is_file())

        # Verify checksums
        results = verify_checksums(dist_dir, "SHA256SUMS")
        self.assertEqual(len(results), 2)
        for name, data in results.items():
            self.assertTrue(data["valid"])
            self.assertIsNone(data["error"])

    def test_tampered_checksum(self):
        dist_dir = self.root / "dist"
        archives, sums_file = create_release_bundles(
            source_dir=self.root,
            dist_dir=dist_dir,
            project_name="DemoApp",
            version="1.0.0",
            formats=["zip"],
            include_patterns=["README.md"],
        )
        # Tamper with file
        target = archives[0]
        with open(target, "ab") as f:
            f.write(b"tampered")

        results = verify_checksums(dist_dir, "SHA256SUMS")
        self.assertFalse(results[target.name]["valid"])
        self.assertEqual(results[target.name]["error"], "Checksum mismatch")


if __name__ == "__main__":
    unittest.main()
