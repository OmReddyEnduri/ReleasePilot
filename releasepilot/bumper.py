"""Version bumping across pyproject.toml, package.json, changelog, and source files."""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from releasepilot.changelog import Changelog
from releasepilot.config import ReleasePilotConfig, load_config
from releasepilot.semver import SemVer


class VersionBumper:
    """Manages version bumping across multiple project metadata files."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir.resolve()

    def bump(
        self,
        part: str,
        prerelease_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> Tuple[str, str, List[Path]]:
        """
        Bumps the project version.
        Returns (old_version, new_version, list_of_updated_files).
        """
        config, config_path = load_config(self.project_dir)
        old_version_str = self.detect_current_version(config)
        old_semver = SemVer.parse(old_version_str)
        new_semver = old_semver.bump(part, prerelease_id=prerelease_id)
        new_version_str = str(new_semver)

        updated_files: List[Path] = []

        # 1. Bump releasepilot.json if it exists
        if config_path.is_file():
            if not dry_run:
                config.version = new_version_str
                config.save(config_path)
            updated_files.append(config_path)

        # 2. Bump pyproject.toml
        pyproject_path = self.project_dir / "pyproject.toml"
        if pyproject_path.is_file():
            content = pyproject_path.read_text(encoding="utf-8")
            # Replace version = "..."
            new_content, count = re.subn(
                r'(^version\s*=\s*["\'])([^"\']+)(["\'])',
                rf"\g<1>{new_version_str}\g<3>",
                content,
                count=1,
                flags=re.MULTILINE,
            )
            if count > 0:
                if not dry_run:
                    pyproject_path.write_text(new_content, encoding="utf-8")
                updated_files.append(pyproject_path)

        # 3. Bump package.json
        package_json_path = self.project_dir / "package.json"
        if package_json_path.is_file():
            try:
                pkg_data = json.loads(package_json_path.read_text(encoding="utf-8"))
                pkg_data["version"] = new_version_str
                if not dry_run:
                    package_json_path.write_text(json.dumps(pkg_data, indent=2) + "\n", encoding="utf-8")
                updated_files.append(package_json_path)
            except Exception:
                pass

        # 4. Bump version_files from config (e.g. __init__.py)
        for rel_file in config.version_files:
            target_path = self.project_dir / rel_file
            if target_path.is_file() and target_path not in updated_files:
                content = target_path.read_text(encoding="utf-8")
                new_content, count = re.subn(
                    r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
                    rf"\g<1>{new_version_str}\g<3>",
                    content,
                    count=1,
                )
                if count > 0:
                    if not dry_run:
                        target_path.write_text(new_content, encoding="utf-8")
                    updated_files.append(target_path)

        # 5. Bump CHANGELOG.md
        changelog_path = self.project_dir / config.changelog_file
        if changelog_path.is_file():
            if not dry_run:
                cl = Changelog.from_file(changelog_path)
                cl.bump_unreleased(new_version_str)
            updated_files.append(changelog_path)

        return old_version_str, new_version_str, updated_files

    def detect_current_version(self, config: Optional[ReleasePilotConfig] = None) -> str:
        """Detect current version from config or project metadata."""
        if config and config.version and config.version != "0.0.0":
            return config.version

        # Try pyproject.toml
        pyproject_path = self.project_dir / "pyproject.toml"
        if pyproject_path.is_file():
            content = pyproject_path.read_text(encoding="utf-8")
            m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if m:
                return m.group(1).strip()

        # Try package.json
        package_json = self.project_dir / "package.json"
        if package_json.is_file():
            try:
                data = json.loads(package_json.read_text(encoding="utf-8"))
                if "version" in data:
                    return str(data["version"]).strip()
            except Exception:
                pass

        # Fallback default
        return "0.1.0"
