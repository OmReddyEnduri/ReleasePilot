"""Semantic Versioning (SemVer 2.0.0) implementation."""

from __future__ import annotations
import re
from functools import total_ordering
from typing import Optional, Tuple, Union

SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


@total_ordering
class SemVer:
    """Represents a Semantic Version complying with SemVer 2.0.0."""

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        prerelease: Optional[str] = None,
        buildmetadata: Optional[str] = None,
    ) -> None:
        self.major = int(major)
        self.minor = int(minor)
        self.patch = int(patch)
        self.prerelease = prerelease or None
        self.buildmetadata = buildmetadata or None

        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Major, minor, and patch numbers must be non-negative integers")

    @classmethod
    def parse(cls, version_str: str) -> SemVer:
        """Parse a SemVer string. Strips optional leading 'v' or 'V'."""
        cleaned = str(version_str).strip()
        if cleaned.startswith(("v", "V")):
            cleaned = cleaned[1:]

        match = SEMVER_REGEX.match(cleaned)
        if not match:
            raise ValueError(f"Invalid SemVer string: {version_str!r}")

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        prerelease = match.group("prerelease")
        buildmetadata = match.group("buildmetadata")

        return cls(major, minor, patch, prerelease, buildmetadata)

    @classmethod
    def is_valid(cls, version_str: str) -> bool:
        """Check if string is a valid SemVer."""
        try:
            cls.parse(version_str)
            return True
        except (ValueError, TypeError):
            return False

    def bump(self, part: str, prerelease_id: Optional[str] = None) -> SemVer:
        """Bump major, minor, or patch part."""
        part = part.lower().strip()
        if part == "major":
            return SemVer(self.major + 1, 0, 0, prerelease=prerelease_id)
        elif part == "minor":
            return SemVer(self.major, self.minor + 1, 0, prerelease=prerelease_id)
        elif part == "patch":
            # If current version has prerelease and no part specified, bump can drop prerelease or increment patch
            return SemVer(self.major, self.minor, self.patch + 1, prerelease=prerelease_id)
        else:
            raise ValueError(f"Invalid bump part: {part!r}. Expected 'major', 'minor', or 'patch'.")

    def _cmp_prerelease(self, other: SemVer) -> int:
        if self.prerelease is None and other.prerelease is None:
            return 0
        if self.prerelease is None and other.prerelease is not None:
            return 1  # 1.0.0 > 1.0.0-alpha
        if self.prerelease is not None and other.prerelease is None:
            return -1  # 1.0.0-alpha < 1.0.0

        # Both have prereleases, compare identifiers
        a_parts = self.prerelease.split(".")  # type: ignore[union-attr]
        b_parts = other.prerelease.split(".")  # type: ignore[union-attr]

        for a, b in zip(a_parts, b_parts):
            a_is_int = a.isdigit()
            b_is_int = b.isdigit()
            if a_is_int and b_is_int:
                ai, bi = int(a), int(b)
                if ai != bi:
                    return 1 if ai > bi else -1
            elif a_is_int and not b_is_int:
                return -1  # Numeric identifiers have lower precedence than alphanumeric
            elif not a_is_int and b_is_int:
                return 1
            else:
                if a != b:
                    return 1 if a > b else -1

        if len(a_parts) != len(b_parts):
            return 1 if len(a_parts) > len(b_parts) else -1
        return 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            if isinstance(other, str) and SemVer.is_valid(other):
                other = SemVer.parse(other)
            else:
                return False
        return (
            (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
            and self._cmp_prerelease(other) == 0
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            if isinstance(other, str) and SemVer.is_valid(other):
                other = SemVer.parse(other)
            else:
                return NotImplemented

        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

        return self._cmp_prerelease(other) < 0

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            s += f"-{self.prerelease}"
        if self.buildmetadata:
            s += f"+{self.buildmetadata}"
        return s

    def __repr__(self) -> str:
        return f"SemVer({str(self)!r})"
