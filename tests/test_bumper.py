"""Unit tests for version bumper across multiple files."""

import json
import tempfile
import unittest
from pathlib import Path
from releasepilot.bumper import VersionBumper
from releasepilot.changelog import Changelog
from releasepilot.config import ReleasePilotConfig


class TestBumper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # 1. releasepilot.json
        cfg = ReleasePilotConfig(project_name="TestApp", version="1.0.0")
        cfg.save(self.root / "releasepilot.json")

        # 2. pyproject.toml
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "testapp"\nversion = "1.0.0"\n', encoding="utf-8"
        )

        # 3. package.json
        (self.root / "package.json").write_text(
            json.dumps({"name": "testapp", "version": "1.0.0"}, indent=2), encoding="utf-8"
        )

        # 4. CHANGELOG.md
        changelog_content = Changelog.scaffold("TestApp", version="1.0.0")
        (self.root / "CHANGELOG.md").write_text(changelog_content, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_bump_patch(self):
        bumper = VersionBumper(self.root)
        old_v, new_v, updated = bumper.bump("patch")

        self.assertEqual(old_v, "1.0.0")
        self.assertEqual(new_v, "1.0.1")

        # Verify pyproject.toml
        pyproject = (self.root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "1.0.1"', pyproject)

        # Verify package.json
        pkg = json.loads((self.root / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(pkg["version"], "1.0.1")

        # Verify CHANGELOG.md
        cl = Changelog.from_file(self.root / "CHANGELOG.md")
        self.assertIsNotNone(cl.get_release("1.0.1"))

    def test_bump_minor(self):
        bumper = VersionBumper(self.root)
        old_v, new_v, _ = bumper.bump("minor")
        self.assertEqual(new_v, "1.1.0")

    def test_bump_major(self):
        bumper = VersionBumper(self.root)
        old_v, new_v, _ = bumper.bump("major")
        self.assertEqual(new_v, "2.0.0")

    def test_dry_run(self):
        bumper = VersionBumper(self.root)
        old_v, new_v, updated = bumper.bump("patch", dry_run=True)
        self.assertEqual(new_v, "1.0.1")

        # Files should still contain 1.0.0
        pyproject = (self.root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "1.0.0"', pyproject)


if __name__ == "__main__":
    unittest.main()
