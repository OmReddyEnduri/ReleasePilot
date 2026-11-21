"""Configuration loader and schema management for ReleasePilot."""

from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_FILENAME = "releasepilot.json"


@dataclass
class PackagingConfig:
    dist_dir: str = "dist"
    formats: List[str] = field(default_factory=lambda: ["zip", "tar.gz"])
    include: List[str] = field(default_factory=lambda: [
        "releasepilot/**",
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "pyproject.toml"
    ])
    exclude: List[str] = field(default_factory=lambda: [
        "**/__pycache__/**",
        "**/*.pyc",
        "**/*.pyo",
        "**/.git/**",
        "**/dist/**",
        "**/.venv/**",
        "**/node_modules/**",
        "**/.pytest_cache/**",
        "**/.DS_Store"
    ])
    checksum_file: str = "SHA256SUMS"


@dataclass
class ChecksConfig:
    require_clean_git: bool = False
    require_tag_match: bool = False
    require_changelog_entry: bool = True
    require_semver: bool = True
    verify_checksums: bool = True
    sync_version_files: bool = True


@dataclass
class ReleasePilotConfig:
    project_name: str = "ReleasePilot"
    version: str = "0.1.0"
    tag_prefix: str = "v"
    changelog_file: str = "CHANGELOG.md"
    version_files: List[str] = field(default_factory=lambda: [
        "releasepilot/__init__.py",
        "pyproject.toml"
    ])
    packaging: PackagingConfig = field(default_factory=PackagingConfig)
    checks: ChecksConfig = field(default_factory=ChecksConfig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "$schema": "https://raw.githubusercontent.com/OmReddyEnduri/ReleasePilot/main/schema.json",
            "project_name": self.project_name,
            "version": self.version,
            "tag_prefix": self.tag_prefix,
            "changelog_file": self.changelog_file,
            "version_files": self.version_files,
            "packaging": asdict(self.packaging),
            "checks": asdict(self.checks),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ReleasePilotConfig:
        packaging_data = data.get("packaging", {})
        checks_data = data.get("checks", {})
        return cls(
            project_name=data.get("project_name", "ReleasePilot"),
            version=data.get("version", "0.1.0"),
            tag_prefix=data.get("tag_prefix", "v"),
            changelog_file=data.get("changelog_file", "CHANGELOG.md"),
            version_files=data.get("version_files", ["releasepilot/__init__.py", "pyproject.toml"]),
            packaging=PackagingConfig(**packaging_data) if packaging_data else PackagingConfig(),
            checks=ChecksConfig(**checks_data) if checks_data else ChecksConfig(),
        )

    def save(self, path: Path) -> None:
        target = path / CONFIG_FILENAME if path.is_dir() else path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def find_config(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Search for releasepilot.json in start_dir or parents."""
    curr = (start_dir or Path.cwd()).resolve()
    for directory in [curr, *curr.parents]:
        cfg = directory / CONFIG_FILENAME
        if cfg.is_file():
            return cfg
    return None


def load_config(start_dir: Optional[Path] = None) -> Tuple[ReleasePilotConfig, Path]:
    """Load config from directory or return default."""
    cfg_path = find_config(start_dir)
    if cfg_path and cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            return ReleasePilotConfig.from_dict(data), cfg_path
        except Exception:
            pass

    # Fallback to root or default
    root = (start_dir or Path.cwd()).resolve()
    return ReleasePilotConfig(), root / CONFIG_FILENAME
