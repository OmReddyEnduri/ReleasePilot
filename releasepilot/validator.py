"""Release validation engine for ReleasePilot."""

from __future__ import annotations
import json
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from releasepilot.changelog import Changelog
from releasepilot.config import ReleasePilotConfig, load_config
from releasepilot.packager import verify_checksums
from releasepilot.semver import SemVer


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    INFO = "INFO"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class ValidationReport:
    version: str
    project_dir: Path
    results: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.status != CheckStatus.FAIL for r in self.results)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.WARN)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.PASS)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "passed": self.passed,
            "counts": {
                "pass": self.pass_count,
                "warn": self.warn_count,
                "fail": self.fail_count,
            },
            "checks": [r.to_dict() for r in self.results],
        }

    def render_console(self) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append(f" ReleasePilot Hygiene & Validation Report: v{self.version}")
        lines.append("=" * 60)

        icons = {
            CheckStatus.PASS: "[PASS]",
            CheckStatus.FAIL: "[FAIL]",
            CheckStatus.WARN: "[WARN]",
            CheckStatus.INFO: "[INFO]",
        }

        for res in self.results:
            icon = icons.get(res.status, "[?]")
            lines.append(f" {icon:6} {res.name}: {res.message}")
            if res.details:
                for d_line in res.details.strip().splitlines():
                    lines.append(f"        | {d_line}")

        lines.append("-" * 60)
        lines.append(
            f" Summary: {self.pass_count} passed, {self.warn_count} warnings, {self.fail_count} failed."
        )
        if self.passed:
            lines.append(" Status: READY FOR RELEASE")
        else:
            lines.append(" Status: RELEASE BLOCKED (Resolve failures before releasing)")
        lines.append("=" * 60)
        return "\n".join(lines)


class ReleaseValidator:
    """Executes full release hygiene verification."""

    def __init__(self, project_dir: Path, config: Optional[ReleasePilotConfig] = None) -> None:
        self.project_dir = project_dir.resolve()
        if config is None:
            loaded_config, _ = load_config(self.project_dir)
            self.config = loaded_config
        else:
            self.config = config

    def validate(self) -> ValidationReport:
        report = ValidationReport(version=self.config.version, project_dir=self.project_dir)

        # 1. SemVer conformity check
        self._check_semver(report)

        # 2. CHANGELOG Keep a Changelog check
        self._check_changelog(report)

        # 3. Multi-file version synchronization check
        self._check_version_sync(report)

        # 4. Git tag & repository alignment check
        self._check_git_alignment(report)

        # 5. Artifact checksum validation check
        self._check_artifact_checksums(report)

        return report

    def _check_semver(self, report: ValidationReport) -> None:
        version = self.config.version
        if not version:
            report.results.append(
                CheckResult(
                    name="SemVer Conformity",
                    status=CheckStatus.FAIL,
                    message="No version defined in releasepilot.json configuration.",
                )
            )
            return

        if SemVer.is_valid(version):
            parsed = SemVer.parse(version)
            details = f"Major: {parsed.major}, Minor: {parsed.minor}, Patch: {parsed.patch}"
            if parsed.prerelease:
                details += f", Pre-release: {parsed.prerelease}"
            report.results.append(
                CheckResult(
                    name="SemVer Conformity",
                    status=CheckStatus.PASS,
                    message=f"Version '{version}' strictly adheres to SemVer 2.0.0 specification.",
                    details=details,
                )
            )
        else:
            report.results.append(
                CheckResult(
                    name="SemVer Conformity",
                    status=CheckStatus.FAIL,
                    message=f"Version '{version}' is NOT a valid SemVer 2.0.0 string.",
                )
            )

    def _check_changelog(self, report: ValidationReport) -> None:
        changelog_file = self.project_dir / self.config.changelog_file
        if not changelog_file.is_file():
            status = CheckStatus.FAIL if self.config.checks.require_changelog_entry else CheckStatus.WARN
            report.results.append(
                CheckResult(
                    name="CHANGELOG Standards",
                    status=status,
                    message=f"Changelog file '{self.config.changelog_file}' not found.",
                )
            )
            return

        try:
            cl = Changelog.from_file(changelog_file)
            errors = cl.validate()
            hard_errors = [e for e in errors if e.severity == "error"]
            warnings = [e for e in errors if e.severity == "warning"]

            # Check for current version entry
            target_v = self.config.version
            rel_entry = cl.get_release(target_v)

            if not rel_entry:
                if self.config.checks.require_changelog_entry:
                    hard_errors.append(
                        f"Missing changelog entry for version [{target_v}]. Found versions: "
                        f"{', '.join(r.version for r in cl.releases)}"
                    )

            if hard_errors:
                report.results.append(
                    CheckResult(
                        name="CHANGELOG Standards",
                        status=CheckStatus.FAIL,
                        message=f"CHANGELOG.md failed Keep a Changelog validation ({len(hard_errors)} error(s)).",
                        details="\n".join(str(e) for e in hard_errors),
                    )
                )
            elif warnings:
                report.results.append(
                    CheckResult(
                        name="CHANGELOG Standards",
                        status=CheckStatus.WARN,
                        message=f"CHANGELOG.md conforms to Keep a Changelog with {len(warnings)} recommendation(s).",
                        details="\n".join(str(w) for w in warnings),
                    )
                )
            else:
                report.results.append(
                    CheckResult(
                        name="CHANGELOG Standards",
                        status=CheckStatus.PASS,
                        message="CHANGELOG.md fully adheres to Keep a Changelog standard (1.1.0).",
                        details=f"Verified entry for version [{target_v}] dated {rel_entry.date if rel_entry else 'N/A'}",
                    )
                )
        except Exception as exc:
            report.results.append(
                CheckResult(
                    name="CHANGELOG Standards",
                    status=CheckStatus.FAIL,
                    message=f"Error parsing CHANGELOG.md: {exc}",
                )
            )

    def _check_version_sync(self, report: ValidationReport) -> None:
        target_version = self.config.version
        mismatches: List[str] = []
        checked_files: List[str] = []

        # Check pyproject.toml
        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.is_file():
            content = pyproject.read_text(encoding="utf-8")
            m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if m:
                found_v = m.group(1).strip()
                checked_files.append(f"pyproject.toml ({found_v})")
                if found_v != target_version:
                    mismatches.append(f"pyproject.toml has version '{found_v}' (expected '{target_version}')")

        # Check package.json
        package_json = self.project_dir / "package.json"
        if package_json.is_file():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                found_v = str(data.get("version", "")).strip()
                checked_files.append(f"package.json ({found_v})")
                if found_v and found_v != target_version:
                    mismatches.append(f"package.json has version '{found_v}' (expected '{target_version}')")
            except Exception:
                pass

        # Check version_files in config
        for rel_file in self.config.version_files:
            p = self.project_dir / rel_file
            if p.is_file() and p.suffix == ".py":
                content = p.read_text(encoding="utf-8")
                m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    found_v = m.group(1).strip()
                    checked_files.append(f"{rel_file} ({found_v})")
                    if found_v != target_version:
                        mismatches.append(f"{rel_file} has version '{found_v}' (expected '{target_version}')")

        if mismatches:
            report.results.append(
                CheckResult(
                    name="Version Synchronization",
                    status=CheckStatus.FAIL,
                    message=f"Version mismatch detected across project files.",
                    details="\n".join(mismatches),
                )
            )
        else:
            files_desc = ", ".join(checked_files) if checked_files else "configuration verified"
            report.results.append(
                CheckResult(
                    name="Version Synchronization",
                    status=CheckStatus.PASS,
                    message=f"All configured version files synchronized at '{target_version}'.",
                    details=f"Verified: {files_desc}",
                )
            )

    def _check_git_alignment(self, report: ValidationReport) -> None:
        git_dir = self.project_dir / ".git"
        if not git_dir.exists():
            report.results.append(
                CheckResult(
                    name="Git Alignment",
                    status=CheckStatus.WARN if not self.config.checks.require_clean_git else CheckStatus.FAIL,
                    message="Not a git repository (or .git not found). Git checks skipped.",
                )
            )
            return

        expected_tag = f"{self.config.tag_prefix}{self.config.version}"
        tag_matched = False
        working_clean = True
        git_details: List[str] = []

        # Check tags
        try:
            res_tags = subprocess.run(
                ["git", "tag", "-l", expected_tag, self.config.version],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            found_tags = [t.strip() for t in res_tags.stdout.splitlines() if t.strip()]
            if expected_tag in found_tags or self.config.version in found_tags:
                tag_matched = True
                git_details.append(f"Release tag '{expected_tag}' is present in repository.")
            else:
                git_details.append(f"Tag '{expected_tag}' not yet tagged in git.")
        except Exception as e:
            git_details.append(f"Could not query git tags: {e}")

        # Check clean working directory
        try:
            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            uncommitted = [l for l in res_status.stdout.splitlines() if l.strip()]
            if uncommitted:
                working_clean = False
                git_details.append(f"{len(uncommitted)} uncommitted change(s) in working tree.")
            else:
                git_details.append("Working tree is completely clean.")
        except Exception as e:
            git_details.append(f"Could not check git status: {e}")

        # Determine status
        if self.config.checks.require_clean_git and not working_clean:
            report.results.append(
                CheckResult(
                    name="Git Alignment",
                    status=CheckStatus.FAIL,
                    message="Uncommitted changes in git repository (require_clean_git enabled).",
                    details="\n".join(git_details),
                )
            )
        elif self.config.checks.require_tag_match and not tag_matched:
            report.results.append(
                CheckResult(
                    name="Git Alignment",
                    status=CheckStatus.WARN,
                    message=f"Git tag '{expected_tag}' does not exist yet.",
                    details="\n".join(git_details),
                )
            )
        else:
            report.results.append(
                CheckResult(
                    name="Git Alignment",
                    status=CheckStatus.PASS,
                    message="Git repository state verified.",
                    details="\n".join(git_details),
                )
            )

    def _check_artifact_checksums(self, report: ValidationReport) -> None:
        dist_dir = self.project_dir / self.config.packaging.dist_dir
        sums_filename = self.config.packaging.checksum_file
        sums_file = dist_dir / sums_filename

        if not dist_dir.is_dir() or not any(dist_dir.iterdir()):
            report.results.append(
                CheckResult(
                    name="Artifact Integrity",
                    status=CheckStatus.INFO,
                    message=f"No distribution artifacts in '{self.config.packaging.dist_dir}/'. Ready for 'releasepilot package'.",
                )
            )
            return

        if not sums_file.is_file():
            report.results.append(
                CheckResult(
                    name="Artifact Integrity",
                    status=CheckStatus.WARN,
                    message=f"Artifacts exist in '{self.config.packaging.dist_dir}/' but missing '{sums_filename}'.",
                )
            )
            return

        try:
            results = verify_checksums(dist_dir, sums_filename)
            failures = [f"{fname}: {data['error']}" for fname, data in results.items() if not data["valid"]]
            if failures:
                report.results.append(
                    CheckResult(
                        name="Artifact Integrity",
                        status=CheckStatus.FAIL,
                        message=f"Checksum validation failed for {len(failures)} artifact(s).",
                        details="\n".join(failures),
                    )
                )
            else:
                report.results.append(
                    CheckResult(
                        name="Artifact Integrity",
                        status=CheckStatus.PASS,
                        message=f"All {len(results)} release artifact(s) match SHA256 checksums.",
                        details="\n".join(f"{f}: OK" for f in results.keys()),
                    )
                )
        except Exception as e:
            report.results.append(
                CheckResult(
                    name="Artifact Integrity",
                    status=CheckStatus.FAIL,
                    message=f"Error validating checksums: {e}",
                )
            )
