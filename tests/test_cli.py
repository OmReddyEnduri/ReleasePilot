"""Unit tests for ReleasePilot CLI commands."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from releasepilot.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_init_and_check(self):
        # 1. Test init
        out = io.StringIO()
        with redirect_stdout(out):
            ret = main(["--dir", str(self.root), "init", "--name", "PilotApp", "--version", "1.0.0"])
        self.assertEqual(ret, 0)
        self.assertTrue((self.root / "releasepilot.json").is_file())
        self.assertTrue((self.root / "CHANGELOG.md").is_file())

        # 2. Test check
        out = io.StringIO()
        with redirect_stdout(out):
            ret = main(["--dir", str(self.root), "check"])
        self.assertEqual(ret, 0)
        self.assertIn("READY FOR RELEASE", out.getvalue())

    def test_cli_bump(self):
        main(["--dir", str(self.root), "init", "--name", "PilotApp", "--version", "1.0.0"])
        out = io.StringIO()
        with redirect_stdout(out):
            ret = main(["--dir", str(self.root), "bump", "minor"])
        self.assertEqual(ret, 0)
        self.assertIn("1.0.0 -> 1.1.0", out.getvalue())

        cfg = json.loads((self.root / "releasepilot.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["version"], "1.1.0")

    def test_cli_package(self):
        main(["--dir", str(self.root), "init", "--name", "PilotApp", "--version", "1.0.0"])
        (self.root / "src").mkdir()
        (self.root / "src" / "sample.txt").write_text("content", encoding="utf-8")

        out = io.StringIO()
        with redirect_stdout(out):
            ret = main(["--dir", str(self.root), "package", "dist"])
        self.assertEqual(ret, 0)
        dist_dir = self.root / "dist"
        self.assertTrue((dist_dir / "PilotApp-1.0.0.zip").is_file())
        self.assertTrue((dist_dir / "PilotApp-1.0.0.tar.gz").is_file())
        self.assertTrue((dist_dir / "SHA256SUMS").is_file())

    def test_cli_notes(self):
        main(["--dir", str(self.root), "init", "--name", "PilotApp", "--version", "1.0.0"])
        out = io.StringIO()
        with redirect_stdout(out):
            ret = main(["--dir", str(self.root), "notes", "--version", "1.0.0"])
        self.assertEqual(ret, 0)
        self.assertIn("Release Notes: [1.0.0]", out.getvalue())


if __name__ == "__main__":
    unittest.main()
