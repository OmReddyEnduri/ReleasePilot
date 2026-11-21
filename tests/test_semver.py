"""Unit tests for SemVer parsing, bumping, and comparison."""

import unittest
from releasepilot.semver import SemVer


class TestSemVer(unittest.TestCase):
    def test_parse_valid(self):
        v = SemVer.parse("1.2.3")
        self.assertEqual(v.major, 1)
        self.assertEqual(v.minor, 2)
        self.assertEqual(v.patch, 3)
        self.assertIsNone(v.prerelease)
        self.assertIsNone(v.buildmetadata)
        self.assertEqual(str(v), "1.2.3")

    def test_parse_with_prefix(self):
        v = SemVer.parse("v2.0.4-rc.1+build.123")
        self.assertEqual(v.major, 2)
        self.assertEqual(v.minor, 0)
        self.assertEqual(v.patch, 4)
        self.assertEqual(v.prerelease, "rc.1")
        self.assertEqual(v.buildmetadata, "build.123")
        self.assertEqual(str(v), "2.0.4-rc.1+build.123")

    def test_invalid_versions(self):
        invalid = ["1", "1.2", "1.2.a", "v1.2", "abc", "-1.0.0"]
        for item in invalid:
            self.assertFalse(SemVer.is_valid(item))
            with self.assertRaises(ValueError):
                SemVer.parse(item)

    def test_bump_patch(self):
        v = SemVer.parse("1.0.0")
        self.assertEqual(str(v.bump("patch")), "1.0.1")

    def test_bump_minor(self):
        v = SemVer.parse("1.2.3")
        self.assertEqual(str(v.bump("minor")), "1.3.0")

    def test_bump_major(self):
        v = SemVer.parse("1.2.3")
        self.assertEqual(str(v.bump("major")), "2.0.0")

    def test_bump_with_prerelease(self):
        v = SemVer.parse("1.0.0")
        self.assertEqual(str(v.bump("minor", prerelease_id="alpha.1")), "1.1.0-alpha.1")

    def test_comparison(self):
        self.assertTrue(SemVer.parse("1.0.0") < SemVer.parse("2.0.0"))
        self.assertTrue(SemVer.parse("1.1.0") < SemVer.parse("1.2.0"))
        self.assertTrue(SemVer.parse("1.0.1") < SemVer.parse("1.0.2"))
        self.assertTrue(SemVer.parse("1.0.0-alpha") < SemVer.parse("1.0.0"))
        self.assertTrue(SemVer.parse("1.0.0-alpha.1") < SemVer.parse("1.0.0-alpha.2"))
        self.assertTrue(SemVer.parse("1.0.0-alpha") < SemVer.parse("1.0.0-beta"))
        self.assertEqual(SemVer.parse("1.0.0"), SemVer.parse("v1.0.0"))


if __name__ == "__main__":
    unittest.main()
