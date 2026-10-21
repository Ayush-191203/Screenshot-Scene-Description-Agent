"""LLM-failure path: original is preserved, JSON status is 'failed', logo-only branding still runs."""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

from scene_agent.capture.base import CaptureResult
from scene_agent.config import AppConfig
from scene_agent.errors import ProviderAuthError
from scene_agent.pipeline import run_pipeline


def _fake_capture_result() -> CaptureResult:
    image = Image.new("RGB", (400, 300), (5, 5, 5))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return CaptureResult(
        image_bytes=buffer.getvalue(),
        width=400,
        height=300,
        source_type="web",
        source_url="https://example.com",
        duration_ms=5.0,
    )


class _FakeBackend:
    def __init__(self, result: CaptureResult) -> None:
        self._result = result

    def capture(self) -> CaptureResult:
        return self._result


class _AlwaysFailingProvider:
    name = "mock"

    def describe(self, image_bytes: bytes, media_type: str, prompt: str):
        raise ProviderAuthError("simulated permanent auth failure")


def test_llm_failure_preserves_original_and_marks_failed(base_config: AppConfig, monkeypatch) -> None:
    fake_result = _fake_capture_result()
    monkeypatch.setattr(
        "scene_agent.pipeline._build_capture_backend", lambda config: _FakeBackend(fake_result)
    )
    monkeypatch.setattr(
        "scene_agent.pipeline.get_provider", lambda provider_config: _AlwaysFailingProvider()
    )

    result = run_pipeline(base_config)

    assert result.success is False
    assert result.metadata["status"] == "failed"
    assert result.metadata["error_code"] == "PROVIDER_AUTH_ERROR"

    original_path = Path(result.metadata["paths"]["original_png"])
    assert original_path.is_file()
    assert original_path.read_bytes() == fake_result.image_bytes

    # txt should NOT be produced (no description), but json must exist with the error.
    assert result.metadata["paths"]["txt"] is None

    json_path = Path(result.metadata["paths"]["json"])
    assert json_path.is_file()
    with open(json_path, encoding="utf-8") as handle:
        metadata_on_disk = json.load(handle)
    assert metadata_on_disk["status"] == "failed"
    assert metadata_on_disk["error_message"]

    # Logo-only branded image should still be produced per produce_logo_only_on_llm_failure.
    branded_path = Path(result.metadata["paths"]["branded_png"])
    assert branded_path.is_file()
    with Image.open(branded_path) as branded:
        # No caption band appended on failure, so height matches the original.
        assert branded.height == fake_result.height


def test_llm_failure_without_logo_only_flag_skips_branded(base_config: AppConfig, monkeypatch) -> None:
    base_config.run.produce_logo_only_on_llm_failure = False
    fake_result = _fake_capture_result()
    monkeypatch.setattr(
        "scene_agent.pipeline._build_capture_backend", lambda config: _FakeBackend(fake_result)
    )
    monkeypatch.setattr(
        "scene_agent.pipeline.get_provider", lambda provider_config: _AlwaysFailingProvider()
    )

    result = run_pipeline(base_config)

    assert result.success is False
    assert result.metadata["paths"]["branded_png"] is None
    original_path = Path(result.metadata["paths"]["original_png"])
    assert original_path.is_file()
