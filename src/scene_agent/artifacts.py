"""Collision-safe artifact naming, hashing, and JSON metadata writing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ArtifactPaths:
    """The four co-located artifact paths for a single run."""

    original_png: Path
    branded_png: Path
    txt: Path
    json: Path


def compute_stem(timestamp: datetime) -> str:
    """Return the base filename stem for a run, e.g. ``capture_20250101_120000``."""
    return f"capture_{timestamp:%Y%m%d_%H%M%S}"


def build_artifact_paths(input_dir: str | Path, output_dir: str | Path, timestamp: datetime) -> ArtifactPaths:
    """Compute collision-safe paths for all four artifacts sharing one base name.

    If any of the four target paths already exists (e.g. two runs within the
    same second), a numeric suffix (``_1``, ``_2``, ...) is appended to the
    stem until all four paths are free.

    Args:
        input_dir: Folder for the original screenshot.
        output_dir: Folder for the branded image, .txt, and .json.
        timestamp: Timestamp used to derive the base stem.

    Returns:
        An :class:`ArtifactPaths` with four non-colliding paths.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    base_stem = compute_stem(timestamp)

    suffix = 0
    while True:
        stem = base_stem if suffix == 0 else f"{base_stem}_{suffix}"
        candidates = ArtifactPaths(
            original_png=input_path / f"{stem}.png",
            branded_png=output_path / f"{stem}_branded.png",
            txt=output_path / f"{stem}.txt",
            json=output_path / f"{stem}.json",
        )
        if not any(
            p.exists()
            for p in (
                candidates.original_png,
                candidates.branded_png,
                candidates.txt,
                candidates.json,
            )
        ):
            return candidates
        suffix += 1


def compute_sha256(path: str | Path) -> str:
    """Compute the SHA-256 hex digest of a file's contents."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_prompt(prompt: str) -> str:
    """Compute a short SHA-256 hex digest of the prompt text for metadata."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def write_json_metadata(path: str | Path, metadata: dict) -> None:
    """Write run metadata as pretty-printed JSON."""
    Path(path).write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text_file(path: str | Path, text: str) -> None:
    """Write the full (untruncated) description text."""
    Path(path).write_text(text, encoding="utf-8")


__all__ = [
    "ArtifactPaths",
    "compute_stem",
    "build_artifact_paths",
    "compute_sha256",
    "hash_prompt",
    "write_json_metadata",
    "write_text_file",
]
