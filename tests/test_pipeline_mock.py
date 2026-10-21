"""Full pipeline test using the mock provider and a fake capture backend (no network/browser)."""

from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

from scene_agent.capture.base import CaptureResult
from scene_agent.config import AppConfig
from scene_agent.pipeline import run_pipeline


def _fake_capture_result() -> CaptureResult:
    image = Image.new("RGB", (640, 480), (30, 60, 90))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return CaptureResult(
        image_bytes=buffer.getvalue(),
        width=640,
        height=480,
        source_type="web",
        source_url="https://example.com",
        duration_ms=12.3,
    )


class _FakeBackend:
    def __init__(self, result: CaptureResult) -> None:
        self._result = result

    def capture(self) -> CaptureResult:
        return self._result


def test_pipeline_success_produces_all_four_artifacts(base_config: AppConfig, monkeypatch) -> None:
    fake_result = _fake_capture_result()
    monkeypatch.setattr(
        "scene_agent.pipeline._build_capture_backend", lambda config: _FakeBackend(fake_result)
    )

    result = run_pipeline(base_config)

    assert result.success is True
    paths = result.metadata["paths"]
    for key in ("original_png", "branded_png", "txt", "json"):
        assert paths[key] is not None, key
        assert Path(paths[key]).is_file(), f"{key} missing: {paths[key]}"

    # Original must be byte-identical to what capture produced.
    assert Path(paths["original_png"]).read_bytes() == fake_result.image_bytes

    # Branded image should be taller than the original (logo + caption band appended).
    with Image.open(paths["branded_png"]) as branded:
        assert branded.height > fake_result.height
        assert branded.width == fake_result.width

    # Description text should be present and match the .txt file.
    txt_content = Path(paths["txt"]).read_text(encoding="utf-8")
    assert txt_content == result.metadata["description"]
    assert len(txt_content) > 0

    with open(paths["json"], encoding="utf-8") as handle:
        metadata_on_disk = json.load(handle)
    assert metadata_on_disk["status"] == "success"
    assert metadata_on_disk["provider"] == "mock"
    assert metadata_on_disk["original_sha256"]
    assert metadata_on_disk["durations_ms"]["total"] >= 0
    assert metadata_on_disk["error_code"] is None


def test_pipeline_capture_failure_writes_failed_json_and_no_originals(
    base_config: AppConfig, monkeypatch
) -> None:
    class _FailingBackend:
        def capture(self) -> CaptureResult:
            from scene_agent.errors import CaptureTimeoutError

            raise CaptureTimeoutError("simulated capture timeout")

    monkeypatch.setattr(
        "scene_agent.pipeline._build_capture_backend", lambda config: _FailingBackend()
    )

    result = run_pipeline(base_config)

    assert result.success is False
    assert result.metadata["status"] == "failed"
    assert result.metadata["error_code"] == "CAPTURE_TIMEOUT"
    assert result.metadata["paths"]["original_png"] is None
    assert Path(result.metadata["paths"]["json"]).is_file()
