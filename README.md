# 🚀 ReleasePilot

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![SemVer 2.0.0](https://img.shields.io/badge/SemVer-2.0.0-green.svg)](https://semver.org/)
[![Status: Production Ready](https://img.shields.io/badge/status-production--ready-brightgreen.svg)]()

> **Developer workspace for Semantic Versioning (SemVer 2.0.0), release hygiene validation, and automated multi-format artifact packaging.**

---

## 🌟 Highlights

- **🛡️ Release Hygiene Validation**: Validates full SemVer conformity, Keep a Changelog structure, release date integrity, and multi-file version synchronization.
- **🔄 Multi-Target Version Bumper**: Increment `patch`, `minor`, or `major` across `pyproject.toml`, `package.json`, `releasepilot.json`, `__init__.py`, and `CHANGELOG.md` in one atomic operation.
- **📦 Deterministic Packaging**: Generates compressed release bundles (`.zip` and `.tar.gz`) with streaming SHA-256 checksums (`SHA256SUMS`).
- **📝 Automatic Release Notes**: Extracts structured release notes for specific tags or unreleased changes ready for GitHub Releases or CI/CD pipelines.
- **⚡ Zero External Dependencies**: 100% standard library Python implementation compatible with Python 3.10+.

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/OmReddyEnduri/ReleasePilot.git
cd ReleasePilot

# Install in editable mode
pip install -e .
```

---

## 🛠️ CLI Quickstart

```bash
# Initialize release tracking in your project
releasepilot init --name "MyCoolProject" --version "0.1.0"

# Check release readiness
releasepilot check --strict

# Bump version atomically
releasepilot bump minor

# Package release archives with checksums
releasepilot package

# Extract release notes for current version
releasepilot notes
```

---

## 🧪 Running Tests

```bash
python -m unittest discover tests -v
```

All 27 automated unit tests verify SemVer parsing, changelog validation, atomic file bumping, archive creation, and CLI subcommands.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.  
Copyright (c) 2026 OmReddyEnduri
