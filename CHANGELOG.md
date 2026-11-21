# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Automated release workflow integration.

## [0.1.0] - 2026-11-21
### Added
- Release hygiene validation engine covering SemVer 2.0.0 conformity, Keep a Changelog formatting, and multi-file version synchronization.
- CLI subcommands: `init`, `check`, `bump`, `package`, and `notes`.
- Automated packaging engine with ZIP and TAR.GZ compression support and SHA256 checksum generation (`SHA256SUMS`).
- Automated multi-target version bumping across `pyproject.toml`, `package.json`, `releasepilot.json`, `__init__.py`, and `CHANGELOG.md`.
- Release notes extractor for versioned releases and unreleased changes.

[Unreleased]: https://github.com/OmReddyEnduri/ReleasePilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OmReddyEnduri/ReleasePilot/releases/tag/v0.1.0
