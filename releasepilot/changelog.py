"""Keep a Changelog parser, validator, and manager."""

from __future__ import annotations
import datetime
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from releasepilot.semver import SemVer

STANDARD_CATEGORIES = [
    "Added",
    "Changed",
    "Deprecated",
    "Removed",
    "Fixed",
    "Security",
]

VERSION_HEADER_REGEX = re.compile(
    r"^##\s+\[(?P<version>[^\]]+)\](?:\s+-\s+(?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)
CATEGORY_HEADER_REGEX = re.compile(
    r"^###\s+(?P<category>[A-Za-z]+)\s*$"
)
LINK_REF_REGEX = re.compile(
    r"^\[(?P<label>[^\]]+)\]:\s*(?P<url>\S+)\s*$"
)


class ChangelogValidationError:
    """Represents a validation error or warning in CHANGELOG.md."""

    def __init__(self, message: str, line_num: Optional[int] = None, severity: str = "error") -> None:
        self.message = message
        self.line_num = line_num
        self.severity = severity

    def __str__(self) -> str:
        loc = f"Line {self.line_num}: " if self.line_num is not None else ""
        return f"[{self.severity.upper()}] {loc}{self.message}"


class ChangelogRelease:
    """Represents a release entry in the changelog."""

    def __init__(self, version: str, date: Optional[str] = None, raw_body: str = "") -> None:
        self.version = version  # e.g. "Unreleased" or "1.0.0"
        self.date = date  # "YYYY-MM-DD" or None
        self.raw_body = raw_body.strip()
        self.categories: Dict[str, List[str]] = {}

    @property
    def is_unreleased(self) -> bool:
        return self.version.strip().lower() == "unreleased"


class Changelog:
    """Parser and manager for CHANGELOG.md following Keep a Changelog standard."""

    def __init__(self, content: str = "", path: Optional[Path] = None) -> None:
        self.content = content
        self.path = path
        self.releases: List[ChangelogRelease] = []
        self.link_references: Dict[str, str] = {}
        self.header_text: str = ""
        if content:
            self.parse()

    @classmethod
    def from_file(cls, path: str | Path) -> Changelog:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Changelog file not found: {p}")
        content = p.read_text(encoding="utf-8")
        return cls(content=content, path=p)

    def parse(self) -> None:
        """Parse the changelog markdown."""
        lines = self.content.splitlines()
        self.releases = []
        self.link_references = {}
        
        current_release: Optional[ChangelogRelease] = None
        current_category: Optional[str] = None
        release_lines: List[str] = []
        header_lines: List[str] = []

        in_header = True

        for idx, line in enumerate(lines, 1):
            link_match = LINK_REF_REGEX.match(line)
            if link_match:
                self.link_references[link_match.group("label")] = link_match.group("url")
                continue

            v_match = VERSION_HEADER_REGEX.match(line)
            if v_match:
                in_header = False
                if current_release is not None:
                    current_release.raw_body = "\n".join(release_lines).strip()
                    self.releases.append(current_release)
                    release_lines = []
                    current_category = None

                ver_str = v_match.group("version")
                date_str = v_match.group("date")
                current_release = ChangelogRelease(ver_str, date_str)
                continue

            if in_header:
                header_lines.append(line)
            else:
                cat_match = CATEGORY_HEADER_REGEX.match(line)
                if cat_match and current_release:
                    current_category = cat_match.group("category")
                    if current_category not in current_release.categories:
                        current_release.categories[current_category] = []
                elif current_category and current_release and line.strip().startswith(("-", "*")):
                    current_release.categories[current_category].append(line.strip()[1:].strip())

                release_lines.append(line)

        if current_release is not None:
            current_release.raw_body = "\n".join(release_lines).strip()
            self.releases.append(current_release)

        self.header_text = "\n".join(header_lines).strip()

    def validate(self) -> List[ChangelogValidationError]:
        """Validate the changelog against Keep a Changelog (1.1.0) standards."""
        errors: List[ChangelogValidationError] = []

        if not self.content.strip():
            errors.append(ChangelogValidationError("Changelog is empty", severity="error"))
            return errors

        lines = self.content.splitlines()

        # Check title
        first_non_empty = next((l for l in lines if l.strip()), "")
        if not re.match(r"^#\s+Changelog", first_non_empty, re.IGNORECASE):
            errors.append(
                ChangelogValidationError(
                    "Top-level header must be '# Changelog'",
                    line_num=1,
                    severity="warning",
                )
            )

        # Check Keep a Changelog reference
        if "keepachangelog" not in self.content.lower():
            errors.append(
                ChangelogValidationError(
                    "Changelog should reference 'Keep a Changelog' standard (https://keepachangelog.com/)",
                    severity="warning",
                )
            )

        # Check releases
        if not self.releases:
            errors.append(
                ChangelogValidationError("No version entries found (e.g. '## [Unreleased]' or '## [1.0.0]')")
            )
            return errors

        for release in self.releases:
            if release.is_unreleased:
                if release.date is not None:
                    errors.append(
                        ChangelogValidationError(
                            f"[Unreleased] section should not have a date, got '{release.date}'"
                        )
                    )
            else:
                # Must be SemVer
                if not SemVer.is_valid(release.version):
                    errors.append(
                        ChangelogValidationError(
                            f"Version '{release.version}' is not a valid Semantic Version (SemVer)"
                        )
                    )
                # Must have date
                if not release.date:
                    errors.append(
                        ChangelogValidationError(
                            f"Release [{release.version}] is missing release date (expected format: ## [{release.version}] - YYYY-MM-DD)"
                        )
                    )
                else:
                    try:
                        datetime.date.fromisoformat(release.date)
                    except ValueError:
                        errors.append(
                            ChangelogValidationError(
                                f"Release [{release.version}] has invalid date format '{release.date}' (expected YYYY-MM-DD)"
                            )
                        )

            # Check categories used in release
            for category in release.categories:
                if category not in STANDARD_CATEGORIES:
                    errors.append(
                        ChangelogValidationError(
                            f"Non-standard category '{category}' in release [{release.version}]. "
                            f"Standard categories are: {', '.join(STANDARD_CATEGORIES)}",
                            severity="warning",
                        )
                    )

        return errors

    def get_release(self, version: str) -> Optional[ChangelogRelease]:
        """Find release entry by version or 'unreleased'."""
        v_clean = version.strip().lstrip("vV")
        for rel in self.releases:
            if rel.is_unreleased and v_clean.lower() == "unreleased":
                return rel
            if rel.version.strip().lstrip("vV") == v_clean:
                return rel
        return None

    def get_release_notes(self, version: str) -> Optional[str]:
        """Extract markdown notes for a specific version."""
        rel = self.get_release(version)
        if not rel:
            return None
        return rel.raw_body

    def get_latest_version(self) -> Optional[str]:
        """Return the latest released SemVer from changelog."""
        for rel in self.releases:
            if not rel.is_unreleased and SemVer.is_valid(rel.version):
                return rel.version
        return None

    def bump_unreleased(self, new_version: str, release_date: Optional[str] = None) -> str:
        """Promote [Unreleased] section to [new_version] - YYYY-MM-DD and insert a new [Unreleased]."""
        if not SemVer.is_valid(new_version):
            raise ValueError(f"Invalid SemVer: {new_version}")

        target_date = release_date or datetime.date.today().isoformat()
        clean_v = str(SemVer.parse(new_version))

        unreleased_match = re.search(
            r"^##\s+\[Unreleased\]\s*$", self.content, re.MULTILINE | re.IGNORECASE
        )
        if not unreleased_match:
            # If no unreleased section, prepend new version section after header
            new_section = (
                f"## [Unreleased]\n\n"
                f"## [{clean_v}] - {target_date}\n\n"
                f"### Added\n- Initial release\n"
            )
            # Find insertion point after top header
            header_end = re.search(r"^(#\s+Changelog.*?)(?=\n##|\Z)", self.content, re.DOTALL)
            if header_end:
                idx = header_end.end()
                new_content = self.content[:idx].rstrip() + "\n\n" + new_section + "\n" + self.content[idx:].lstrip()
            else:
                new_content = f"# Changelog\n\n{new_section}\n"
        else:
            # Replace ## [Unreleased] with ## [Unreleased]\n\n## [new_version] - date
            # But wait: if [Unreleased] had content, that content belongs to new_version!
            start_pos = unreleased_match.start()
            end_header = unreleased_match.end()

            # Find next ## or EOF or link refs
            next_header = re.search(r"\n##\s+\[", self.content[end_header:])
            link_ref_start = re.search(r"\n\[[^\]]+\]:\s*", self.content[end_header:])

            cut_pos = None
            if next_header and link_ref_start:
                cut_pos = end_header + min(next_header.start(), link_ref_start.start())
            elif next_header:
                cut_pos = end_header + next_header.start()
            elif link_ref_start:
                cut_pos = end_header + link_ref_start.start()
            else:
                cut_pos = len(self.content)

            unreleased_body = self.content[end_header:cut_pos].strip()
            if not unreleased_body:
                unreleased_body = "### Added\n- Release updates"

            new_block = (
                f"## [Unreleased]\n\n"
                f"## [{clean_v}] - {target_date}\n\n"
                f"{unreleased_body}\n"
            )

            new_content = (
                self.content[:start_pos] + new_block + self.content[cut_pos:]
            )

        self.content = new_content
        self.parse()
        if self.path:
            self.path.write_text(self.content, encoding="utf-8")
        return self.content

    @classmethod
    def scaffold(cls, project_name: str, version: str = "0.1.0") -> str:
        """Create a standard Keep a Changelog template."""
        today = datetime.date.today().isoformat()
        return f"""# Changelog

All notable changes to {project_name} will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [{version}] - {today}
### Added
- Initial project release and workspace setup.
- Core CLI framework and hygiene checks.
"""
