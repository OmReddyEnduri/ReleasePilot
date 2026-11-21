"""Artifact packaging and SHA256 checksum generation for ReleasePilot."""

from __future__ import annotations
import fnmatch
import hashlib
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hex digest of a file in streaming chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def match_patterns(rel_path: str, patterns: List[str]) -> bool:
    """Check if normalized relative path matches any glob pattern."""
    norm_path = rel_path.replace("\\", "/")
    for pat in patterns:
        norm_pat = pat.replace("\\", "/")
        if fnmatch.fnmatch(norm_path, norm_pat) or fnmatch.fnmatch(norm_path, f"*/{norm_pat}"):
            return True
        # Also check directory prefixes
        if norm_pat.endswith("/**"):
            prefix = norm_pat[:-3].rstrip("/")
            if norm_path == prefix or norm_path.startswith(prefix + "/"):
                return True
    return False


def collect_package_files(
    source_dir: Path,
    include_patterns: List[str],
    exclude_patterns: List[str],
) -> List[Path]:
    """Collect relative file paths that match include patterns and not exclude patterns."""
    matched_files: List[Path] = []
    
    for root, dirs, files in os.walk(source_dir):
        # Exclude directories early if matching exclude pattern
        rel_root = os.path.relpath(root, source_dir)
        if rel_root != ".":
            norm_rel_root = rel_root.replace("\\", "/")
            if any(fnmatch.fnmatch(norm_rel_root, ex.strip("/")) or fnmatch.fnmatch(norm_rel_root, f"*/{ex.strip('/')}") for ex in exclude_patterns):
                dirs[:] = []
                continue

        for f in files:
            full_path = Path(root) / f
            rel_file = full_path.relative_to(source_dir)
            rel_str = str(rel_file).replace("\\", "/")

            # Check exclude
            if match_patterns(rel_str, exclude_patterns):
                continue

            # Check include
            if include_patterns:
                if match_patterns(rel_str, include_patterns):
                    matched_files.append(rel_file)
            else:
                matched_files.append(rel_file)

    return sorted(matched_files)


def create_release_bundles(
    source_dir: Path,
    dist_dir: Path,
    project_name: str,
    version: str,
    formats: Optional[List[str]] = None,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    checksum_filename: str = "SHA256SUMS",
) -> Tuple[List[Path], Path]:
    """
    Package release bundles into zip / tar.gz and generate SHA256 checksums file.
    Returns (list of created bundle paths, checksum file path).
    """
    formats = formats or ["zip", "tar.gz"]
    dist_dir.mkdir(parents=True, exist_ok=True)

    files_to_pack = collect_package_files(
        source_dir=source_dir,
        include_patterns=include_patterns or ["**/*"],
        exclude_patterns=exclude_patterns or ["**/__pycache__/**", "**/*.pyc", "**/.git/**", "**/dist/**"],
    )

    bundle_prefix = f"{project_name}-{version}"
    created_archives: List[Path] = []

    for fmt in formats:
        fmt_clean = fmt.lower().strip()
        if fmt_clean == "zip":
            archive_path = dist_dir / f"{bundle_prefix}.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for rel_path in files_to_pack:
                    source_file = source_dir / rel_path
                    arcname = f"{bundle_prefix}/{rel_path.as_posix()}"
                    zf.write(source_file, arcname=arcname)
            created_archives.append(archive_path)

        elif fmt_clean in ("tar.gz", "tgz", "tar"):
            archive_path = dist_dir / f"{bundle_prefix}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tf:
                for rel_path in files_to_pack:
                    source_file = source_dir / rel_path
                    arcname = f"{bundle_prefix}/{rel_path.as_posix()}"
                    tf.add(source_file, arcname=arcname)
            created_archives.append(archive_path)
        else:
            raise ValueError(f"Unsupported archive format: {fmt}")

    # Write SHA256SUMS file
    checksums_file = dist_dir / checksum_filename
    lines = []
    for archive in created_archives:
        digest = compute_sha256(archive)
        lines.append(f"{digest}  {archive.name}\n")

    checksums_file.write_text("".join(lines), encoding="utf-8")
    return created_archives, checksums_file


def verify_checksums(
    dist_dir: Path,
    checksum_filename: str = "SHA256SUMS",
) -> Dict[str, Dict[str, str | bool]]:
    """
    Verify checksums in dist_dir against checksum_file.
    Returns dictionary with results: {filename: {'valid': bool, 'expected': str, 'actual': str, 'error': Optional[str]}}
    """
    sums_path = dist_dir / checksum_filename
    if not sums_path.is_file():
        raise FileNotFoundError(f"Checksum file not found: {sums_path}")

    results: Dict[str, Dict[str, str | bool]] = {}
    content = sums_path.read_text(encoding="utf-8")

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        expected_hash, filename = parts[0].strip(), parts[1].strip()
        # strip optional leading * (binary mode indicator in sha256sum)
        filename = filename.lstrip("*")
        target_file = dist_dir / filename

        if not target_file.exists():
            results[filename] = {
                "valid": False,
                "expected": expected_hash,
                "actual": "",
                "error": "File not found",
            }
            continue

        actual_hash = compute_sha256(target_file)
        is_match = expected_hash.lower() == actual_hash.lower()
        results[filename] = {
            "valid": is_match,
            "expected": expected_hash,
            "actual": actual_hash,
            "error": None if is_match else "Checksum mismatch",
        }

    return results
