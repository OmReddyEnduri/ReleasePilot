"""Unit tests for Keep a Changelog parser and validator."""

import tempfile
import unittest
from pathlib import Path
from releasepilot.changelog import Changelog


SAMPLE_VALID_CHANGELOG = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Upcoming CLI command

## [1.0.0] - 2026-11-20
### Added
- Initial project release
- Feature Alpha

### Fixed
- Fixed critical bug in parser
"""


class TestChangelog(unittest.TestCase):
    def test_parse_and_validate_valid(self):
        cl = Changelog(SAMPLE_VALID_CHANGELOG)
        errors = cl.validate()
        hard_errors = [e for e in errors if e.severity == "error"]
        self.assertEqual(len(hard_errors), 0)
        self.assertEqual(len(cl.releases), 2)
        self.assertTrue(cl.releases[0].is_unreleased)
        self.assertEqual(cl.releases[1].version, "1.0.0")
        self.assertEqual(cl.releases[1].date, "2026-11-20")

    def test_extract_notes(self):
        cl = Changelog(SAMPLE_VALID_CHANGELOG)
        notes = cl.get_release_notes("1.0.0")
        self.assertIsNotNone(notes)
        self.assertIn("Initial project release", notes)
        self.assertIn("Fixed critical bug", notes)

        unreleased = cl.get_release_notes("Unreleased")
        self.assertIsNotNone(unreleased)
        self.assertIn("Upcoming CLI command", unreleased)

    def test_bump_unreleased(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "CHANGELOG.md"
            file_path.write_text(SAMPLE_VALID_CHANGELOG, encoding="utf-8")

            cl = Changelog.from_file(file_path)
            cl.bump_unreleased("1.1.0", release_date="2026-11-21")

            updated = file_path.read_text(encoding="utf-8")
            self.assertIn("## [Unreleased]", updated)
            self.assertIn("## [1.1.0] - 2026-11-21", updated)
            self.assertIn("Upcoming CLI command", updated)

            reloaded = Changelog.from_file(file_path)
            self.assertEqual(len(reloaded.releases), 3)
            self.assertEqual(reloaded.releases[1].version, "1.1.0")

    def test_validate_invalid(self):
        invalid_cl = Changelog("# Changelog\n\n## [invalid_ver] - bad-date\n")
        errors = invalid_cl.validate()
        hard_errors = [e for e in errors if e.severity == "error"]
        self.assertTrue(len(hard_errors) >= 1)


if __name__ == "__main__":
    unittest.main()
