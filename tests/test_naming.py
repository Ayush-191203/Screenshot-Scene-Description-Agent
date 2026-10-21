"""Artifact naming and collision-safety tests."""

from __future__ import annotations

from datetime import UTC, datetime

from scene_agent.artifacts import build_artifact_paths, compute_sha256, compute_stem


def test_compute_stem_format() -> None:
    ts = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert compute_stem(ts) == "capture_20250102_030405"


def test_build_artifact_paths_basic(tmp_path) -> None:
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    ts = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
    paths = build_artifact_paths(input_dir, output_dir, ts)
    assert paths.original_png == input_dir / "capture_20250102_030405.png"
    assert paths.branded_png == output_dir / "capture_20250102_030405_branded.png"
    assert paths.txt == output_dir / "capture_20250102_030405.txt"
    assert paths.json == output_dir / "capture_20250102_030405.json"


def test_build_artifact_paths_collision_suffix(tmp_path) -> None:
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    ts = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)

    first = build_artifact_paths(input_dir, output_dir, ts)
    first.original_png.write_bytes(b"fake-png")

    second = build_artifact_paths(input_dir, output_dir, ts)
    assert second.original_png.name == "capture_20250102_030405_1.png"
    assert second.branded_png.name == "capture_20250102_030405_1_branded.png"
    assert second.original_png != first.original_png


def test_compute_sha256_matches_known_value(tmp_path) -> None:
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"hello world")
    import hashlib

    expected = hashlib.sha256(b"hello world").hexdigest()
    assert compute_sha256(file_path) == expected
