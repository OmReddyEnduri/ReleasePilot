"""Command-line interface for ReleasePilot."""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from releasepilot.bumper import VersionBumper
from releasepilot.changelog import Changelog
from releasepilot.config import ReleasePilotConfig, find_config, load_config
from releasepilot.packager import create_release_bundles
from releasepilot.validator import ReleaseValidator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="releasepilot",
        description="ReleasePilot - Developer release hygiene and artifact packaging workstation.",
    )
    parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=".",
        help="Target project directory (defaults to current directory)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: init
    init_parser = subparsers.add_parser("init", help="Scaffold release config releasepilot.json and changelog template")
    init_parser.add_argument("--name", "-n", type=str, help="Project name (defaults to directory name)")
    init_parser.add_argument("--version", "-v", type=str, default="0.1.0", help="Initial version (default: 0.1.0)")
    init_parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing configuration if present")

    # Command: check
    check_parser = subparsers.add_parser("check", help="Run comprehensive release hygiene checks")
    check_parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    check_parser.add_argument("--json", action="store_true", help="Output report in JSON format")

    # Command: bump
    bump_parser = subparsers.add_parser("bump", help="Bump project version across all project files and changelog")
    bump_parser.add_argument("part", choices=["patch", "minor", "major"], help="Version component to increment")
    bump_parser.add_argument("--prerelease", "-p", type=str, help="Optional pre-release identifier (e.g. rc.1, beta)")
    bump_parser.add_argument("--dry-run", action="store_true", help="Preview version changes without writing to disk")

    # Command: package
    package_parser = subparsers.add_parser("package", help="Generate zip/tar.gz release bundles with SHA256 checksums file")
    package_parser.add_argument("dist_dir", nargs="?", default=None, help="Output directory for distribution bundles")
    package_parser.add_argument(
        "--format",
        "-F",
        type=str,
        default="zip,tar.gz",
        help="Comma-separated archive formats (zip, tar.gz)",
    )

    # Command: notes
    notes_parser = subparsers.add_parser("notes", help="Extract release notes for current version or unreleased changes")
    notes_parser.add_argument("--version", "-v", type=str, help="Specific version to extract notes for")
    notes_parser.add_argument("--unreleased", "-u", action="store_true", help="Extract notes from [Unreleased] section")

    return parser


def handle_init(args: argparse.Namespace, project_dir: Path) -> int:
    config_file = project_dir / "releasepilot.json"
    if config_file.exists() and not args.force:
        print(f"[!] 'releasepilot.json' already exists at {config_file}. Use --force to overwrite.", file=sys.stderr)
        return 1

    project_name = args.name or project_dir.name or "MyProject"
    config = ReleasePilotConfig(project_name=project_name, version=args.version)
    config.save(config_file)
    print(f"[+] Initialized release configuration: {config_file}")

    # Check CHANGELOG.md
    changelog_file = project_dir / config.changelog_file
    if not changelog_file.exists():
        scaffolded = Changelog.scaffold(project_name=project_name, version=args.version)
        changelog_file.write_text(scaffolded, encoding="utf-8")
        print(f"[+] Scaffolded Keep a Changelog template: {changelog_file}")

    return 0


def handle_check(args: argparse.Namespace, project_dir: Path) -> int:
    validator = ReleaseValidator(project_dir=project_dir)
    report = validator.validate()

    if getattr(args, "json", False):
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.render_console())

    if not report.passed:
        return 1
    if getattr(args, "strict", False) and report.warn_count > 0:
        print(f"[!] Strict mode failed: {report.warn_count} warning(s) encountered.", file=sys.stderr)
        return 1
    return 0


def handle_bump(args: argparse.Namespace, project_dir: Path) -> int:
    bumper = VersionBumper(project_dir=project_dir)
    try:
        old_v, new_v, updated = bumper.bump(
            part=args.part,
            prerelease_id=args.prerelease,
            dry_run=args.dry_run,
        )
        mode_prefix = "[DRY-RUN] " if args.dry_run else ""
        print(f"{mode_prefix}Bumped version: {old_v} -> {new_v}")
        print(f"Updated {len(updated)} file(s):")
        for f in updated:
            rel = f.relative_to(project_dir) if f.is_relative_to(project_dir) else f
            print(f"  - {rel}")
        return 0
    except Exception as e:
        print(f"[-] Failed to bump version: {e}", file=sys.stderr)
        return 1


def handle_package(args: argparse.Namespace, project_dir: Path) -> int:
    config, _ = load_config(project_dir)
    dist_dir_name = args.dist_dir or config.packaging.dist_dir
    dist_path = project_dir / dist_dir_name

    formats = [f.strip() for f in args.format.split(",") if f.strip()]

    print(f"Packaging {config.project_name} v{config.version}...")
    try:
        created, sums_path = create_release_bundles(
            source_dir=project_dir,
            dist_dir=dist_path,
            project_name=config.project_name,
            version=config.version,
            formats=formats,
            include_patterns=config.packaging.include,
            exclude_patterns=config.packaging.exclude,
            checksum_filename=config.packaging.checksum_file,
        )
        print(f"[+] Successfully generated {len(created)} bundle(s) in {dist_path}:")
        for archive in created:
            print(f"    * {archive.name} ({archive.stat().st_size:,} bytes)")
        print(f"[+] SHA256 Checksums file written to: {sums_path.name}")
        print(sums_path.read_text(encoding="utf-8").strip())
        return 0
    except Exception as e:
        print(f"[-] Packaging failed: {e}", file=sys.stderr)
        return 1


def handle_notes(args: argparse.Namespace, project_dir: Path) -> int:
    config, _ = load_config(project_dir)
    changelog_file = project_dir / config.changelog_file

    if not changelog_file.is_file():
        print(f"[-] Changelog file not found at {changelog_file}", file=sys.stderr)
        return 1

    try:
        cl = Changelog.from_file(changelog_file)
        target_version = "Unreleased" if args.unreleased else (args.version or config.version)
        notes = cl.get_release_notes(target_version)

        if notes is None:
            print(f"[-] No notes found in CHANGELOG.md for [{target_version}]", file=sys.stderr)
            return 1

        print(f"## Release Notes: [{target_version}]\n")
        print(notes)
        return 0
    except Exception as e:
        print(f"[-] Error extracting release notes: {e}", file=sys.stderr)
        return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    project_dir = Path(args.dir).resolve()
    if not project_dir.exists():
        print(f"[-] Target directory does not exist: {project_dir}", file=sys.stderr)
        return 1

    handlers = {
        "init": handle_init,
        "check": handle_check,
        "bump": handle_bump,
        "package": handle_package,
        "notes": handle_notes,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args, project_dir)


if __name__ == "__main__":
    sys.exit(main())
