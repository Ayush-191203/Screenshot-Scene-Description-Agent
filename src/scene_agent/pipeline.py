"""End-to-end pipeline: capture -> save original -> describe -> brand -> write artifacts.

The original screenshot is always saved to disk before any LLM call and is
never modified afterwards. If the LLM call fails, the original is preserved,
a "failed" status JSON is written, and (configurably) a logo-only branded
image is still produced.
"""

from __future__ import annotations

import io
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from PIL import Image

from scene_agent.artifacts import (
    build_artifact_paths,
    compute_sha256,
    hash_prompt,
    write_json_metadata,
    write_text_file,
)
from scene_agent.capture.base import CaptureBackend, CaptureResult
from scene_agent.capture.web import WebCaptureBackend
from scene_agent.capture.window import WindowCaptureBackend
from scene_agent.config import AppConfig
from scene_agent.errors import LogoError, ProviderError, SceneAgentError
from scene_agent.imaging.caption import render_caption_band
from scene_agent.imaging.logo import apply_logo
from scene_agent.logging_setup import get_run_logger
from scene_agent.providers.registry import get_provider

_LLM_MAX_LONG_EDGE = 1568


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of a single pipeline run."""

    success: bool
    metadata: dict
    run_id: str


def _build_capture_backend(config: AppConfig) -> CaptureBackend:
    if config.capture.mode == "web":
        return WebCaptureBackend(config.capture.web)
    return WindowCaptureBackend(config.capture.window)


def _downscale_for_llm(image_bytes: bytes, max_long_edge: int) -> bytes:
    """Return PNG bytes resized so the long edge is at most ``max_long_edge``.

    If the image is already within bounds, the original bytes are returned
    unchanged (no quality loss from a redundant re-encode).
    """
    with Image.open(io.BytesIO(image_bytes)) as image:
        width, height = image.size
        long_edge = max(width, height)
        if long_edge <= max_long_edge:
            return image_bytes

        ratio = max_long_edge / long_edge
        new_size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
        resized = image.convert("RGB").resize(new_size, Image.LANCZOS)
        buffer = io.BytesIO()
        resized.save(buffer, format="PNG")
        return buffer.getvalue()


def run_pipeline(config: AppConfig) -> PipelineResult:
    """Execute a single capture -> describe -> brand -> persist run.

    Args:
        config: Fully validated application configuration.

    Returns:
        A :class:`PipelineResult` whose ``success`` flag reflects whether a
        complete set of artifacts was produced (capture + branding). An LLM
        failure still returns ``success=False`` but preserves the original.
    """
    run_id = uuid.uuid4().hex[:12]
    logger = get_run_logger(run_id)
    started_at = time.perf_counter()
    timestamp = datetime.now(UTC)

    durations_ms: dict[str, float] = {}
    status = "failed"
    error_code: str | None = None
    error_message: str | None = None
    description: str | None = None
    provider_name: str | None = None
    model_name: str | None = None
    retry_count = 0
    usage: dict | None = None
    paths = build_artifact_paths(config.paths.input_dir, config.paths.output_dir, timestamp)
    original_sha256: str | None = None
    image_dimensions: dict | None = None
    source_type = config.capture.mode
    source_url = config.capture.web.url if config.capture.mode == "web" else (
        config.capture.window.title or config.capture.window.process_name or ""
    )

    # --- Stage 1: capture -------------------------------------------------
    try:
        backend = _build_capture_backend(config)
        capture_result: CaptureResult = backend.capture()
        durations_ms["capture"] = capture_result.duration_ms
        source_url = capture_result.source_url
        image_dimensions = {"width": capture_result.width, "height": capture_result.height}
    except SceneAgentError as exc:
        error_code = exc.error_code
        error_message = str(exc)
        logger.error("Capture failed: %s", error_message)
        total_ms = (time.perf_counter() - started_at) * 1000
        durations_ms["total"] = total_ms
        metadata = _build_metadata(
            run_id=run_id,
            status="failed",
            timestamp=timestamp,
            source_type=source_type,
            source_url=source_url,
            paths_dict={
                "original_png": None,
                "branded_png": None,
                "txt": None,
                "json": str(paths.json),
            },
            description=None,
            prompt=config.provider.prompt,
            provider=None,
            model=None,
            usage=None,
            image_dimensions=None,
            original_sha256=None,
            durations_ms=durations_ms,
            retry_count=0,
            error_code=error_code,
            error_message=error_message,
        )
        write_json_metadata(paths.json, metadata)
        return PipelineResult(success=False, metadata=metadata, run_id=run_id)

    # --- Save the original immediately, before any LLM call ---------------
    paths.original_png.parent.mkdir(parents=True, exist_ok=True)
    paths.original_png.write_bytes(capture_result.image_bytes)
    original_sha256 = compute_sha256(paths.original_png)
    logger.info("Saved original screenshot to %s", paths.original_png)

    # --- Stage 2: LLM description ------------------------------------------
    llm_succeeded = False
    try:
        provider = get_provider(config.provider)
        provider_name = provider.name
        llm_bytes = _downscale_for_llm(capture_result.image_bytes, _LLM_MAX_LONG_EDGE)
        llm_start = time.perf_counter()
        result = provider.describe(llm_bytes, "image/png", config.provider.prompt)
        durations_ms["llm"] = (time.perf_counter() - llm_start) * 1000
        description = result.text
        model_name = result.model
        usage = result.usage
        retry_count = result.retry_count
        llm_succeeded = True
        logger.info(
            "LLM description succeeded (provider=%s model=%s retries=%d)",
            provider_name,
            model_name,
            retry_count,
        )
    except ProviderError as exc:
        error_code = exc.error_code
        error_message = str(exc)
        logger.error("LLM description failed: %s", error_message)
    except SceneAgentError as exc:
        error_code = exc.error_code
        error_message = str(exc)
        logger.error("LLM stage failed: %s", error_message)

    # --- Stage 3: branding --------------------------------------------------
    branding_start = time.perf_counter()
    branded_image: Image.Image | None = None
    try:
        with Image.open(paths.original_png) as original_image:
            branded_image = original_image.convert("RGBA")
            try:
                branded_image = apply_logo(branded_image, config.logo)
            except LogoError as exc:
                if config.logo.on_missing == "fail":
                    raise
                logger.warning("Continuing without logo: %s", exc)

            if llm_succeeded and config.caption.enabled and description is not None:
                branded_image = render_caption_band(
                    branded_image,
                    description,
                    font_path=config.caption.font_path,
                    font_size=config.caption.font_size,
                    text_color=config.caption.text_color,
                    background_color=config.caption.background_color,
                    background_opacity_pct=config.caption.background_opacity_pct,
                    padding_px=config.caption.padding_px,
                    max_length=config.caption.max_length,
                    max_height_pct=config.caption.max_height_pct,
                )

        should_produce_branded = llm_succeeded or config.run.produce_logo_only_on_llm_failure
        if should_produce_branded:
            paths.branded_png.parent.mkdir(parents=True, exist_ok=True)
            branded_image.save(paths.branded_png, format="PNG")
            logger.info("Saved branded image to %s", paths.branded_png)
    except SceneAgentError as exc:
        if error_code is None:
            error_code = exc.error_code
            error_message = str(exc)
        logger.error("Branding failed: %s", error_message)
        branded_image = None
    durations_ms["branding"] = (time.perf_counter() - branding_start) * 1000

    # --- Stage 4: write text + json artifacts -------------------------------
    if llm_succeeded and description is not None:
        write_text_file(paths.txt, description)

    status = "success" if (llm_succeeded and branded_image is not None) else "failed"
    durations_ms["total"] = (time.perf_counter() - started_at) * 1000

    metadata = _build_metadata(
        run_id=run_id,
        status=status,
        timestamp=timestamp,
        source_type=source_type,
        source_url=source_url,
        paths_dict={
            "original_png": str(paths.original_png),
            "branded_png": str(paths.branded_png) if paths.branded_png.is_file() else None,
            "txt": str(paths.txt) if paths.txt.is_file() else None,
            "json": str(paths.json),
        },
        description=description,
        prompt=config.provider.prompt,
        provider=provider_name,
        model=model_name,
        usage=usage,
        image_dimensions=image_dimensions,
        original_sha256=original_sha256,
        durations_ms=durations_ms,
        retry_count=retry_count,
        error_code=error_code if not llm_succeeded else None,
        error_message=error_message if not llm_succeeded else None,
    )
    write_json_metadata(paths.json, metadata)
    logger.info("Run finished with status=%s in %.1fms", status, durations_ms["total"])

    return PipelineResult(success=(status == "success"), metadata=metadata, run_id=run_id)


def _build_metadata(
    *,
    run_id: str,
    status: str,
    timestamp: datetime,
    source_type: str,
    source_url: str,
    paths_dict: dict,
    description: str | None,
    prompt: str,
    provider: str | None,
    model: str | None,
    usage: dict | None,
    image_dimensions: dict | None,
    original_sha256: str | None,
    durations_ms: dict[str, float],
    retry_count: int,
    error_code: str | None,
    error_message: str | None,
) -> dict:
    """Assemble the JSON-serializable run metadata document."""
    return {
        "run_id": run_id,
        "status": status,
        "timestamp_utc": timestamp.isoformat(),
        "source_type": source_type,
        "source_url": source_url,
        "paths": paths_dict,
        "description": description,
        "prompt_sha256": hash_prompt(prompt),
        "provider": provider,
        "model": model,
        "usage": usage,
        "image_dimensions": image_dimensions,
        "original_sha256": original_sha256,
        "durations_ms": {
            "capture": round(durations_ms.get("capture", 0.0), 2),
            "llm": round(durations_ms.get("llm", 0.0), 2),
            "branding": round(durations_ms.get("branding", 0.0), 2),
            "total": round(durations_ms.get("total", 0.0), 2),
        },
        "retry_count": retry_count,
        "error_code": error_code,
        "error_message": error_message,
    }
