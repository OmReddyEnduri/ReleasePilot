"""Unit tests for release hygiene validator."""

import json
import tempfile
import unittest
from pathlib import Path
from releasepilot.changelog import Changelog
from releasepilot.config import ReleasePilotConfig
from releasepilot.validator import CheckStatus, ReleaseValidator


class TestValidator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Release config
        self.config = ReleasePilotConfig(project_name="TestApp", version="1.0.0")
        self.config.checks.require_tag_match = False
        self.config.checks.require_clean_git = False
        self.config.save(self.root / "releasepilot.json")

        # pyproject.toml
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "testapp"\nversion = "1.0.0"\n', encoding="utf-8"
        )

        # CHANGELOG.md
        cl_text = Changelog.scaffold("TestApp", version="1.0.0")
        (self.root / "CHANGELOG.md").write_text(cl_text, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_project(self):
        validator = ReleaseValidator(self.root, self.config)
        report = validator.validate()

        self.assertTrue(report.passed)
        self.assertEqual(report.fail_count, 0)

    def test_version_mismatch(self):
        # Change pyproject version
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "testapp"\nversion = "1.2.0"\n', encoding="utf-8"
        )
        validator = ReleaseValidator(self.root, self.config)
        report = validator.validate()

        self.assertFalse(report.passed)
        fail_checks = [r for r in report.results if r.status == CheckStatus.FAIL]
        names = [f.name for f in fail_checks]
        self.assertIn("Version Synchronization", names)

    def test_invalid_semver(self):
        self.config.version = "not-a-semver"
        validator = ReleaseValidator(self.root, self.config)
        report = validator.validate()

        self.assertFalse(report.passed)
        fail_checks = [r for r in report.results if r.status == CheckStatus.FAIL]
        names = [f.name for f in fail_checks]
        self.assertIn("SemVer Conformity", names)

    def test_missing_changelog_entry(self):
        self.config.version = "2.0.0"  # changelog has 1.0.0
        validator = ReleaseValidator(self.root, self.config)
        report = validator.validate()

        self.assertFalse(report.passed)
        fail_checks = [r for r in report.results if r.status == CheckStatus.FAIL]
        names = [f.name for f in fail_checks]
        self.assertIn("CHANGELOG Standards", names)


if __name__ == "__main__":
    unittest.main()
