"""Playwright (Chromium) web capture backend.

Waits for DOMContentLoaded, then a configurable settle delay, then optionally a
readiness selector. Never relies solely on ``networkidle`` (ad-heavy pages such
as Finviz may never go idle) and always has a hard timeout fallback so a run
can never hang indefinitely.
"""

from __future__ import annotations

import contextlib
import io
import time

from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from scene_agent.capture.base import CaptureBackend, CaptureResult
from scene_agent.config import CaptureWebConfig
from scene_agent.errors import CaptureError, CaptureTimeoutError


class WebCaptureBackend(CaptureBackend):
    """Captures a screenshot of a URL using headless/headed Chromium."""

    def __init__(self, config: CaptureWebConfig) -> None:
        """Initialize the backend.

        Args:
            config: Web capture settings (URL, viewport, timeouts, selectors).
        """
        self._config = config

    def capture(self) -> CaptureResult:
        """Navigate to the configured URL and return a full screenshot.

        Returns:
            A :class:`CaptureResult` with the PNG bytes and dimensions.

        Raises:
            CaptureTimeoutError: If navigation exceeds ``timeout_ms``.
            CaptureError: For any other Playwright/browser failure.
        """
        config = self._config
        start = time.perf_counter()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=config.headless)
                try:
                    context = browser.new_context(
                        viewport={
                            "width": config.viewport_width,
                            "height": config.viewport_height,
                        }
                    )
                    page = context.new_page()
                    page.goto(
                        config.url,
                        wait_until="domcontentloaded",
                        timeout=config.timeout_ms,
                    )

                    self._dismiss_consent_banners(page)

                    if config.settle_delay_ms > 0:
                        page.wait_for_timeout(config.settle_delay_ms)

                    if config.ready_selector:
                        with contextlib.suppress(PlaywrightTimeoutError):
                            # Best-effort readiness check; fall through to screenshot anyway.
                            page.wait_for_selector(
                                config.ready_selector, timeout=config.timeout_ms
                            )

                    image_bytes = page.screenshot(full_page=config.full_page)
                finally:
                    browser.close()
        except PlaywrightTimeoutError as exc:
            raise CaptureTimeoutError(
                f"Timed out capturing {config.url} after {config.timeout_ms}ms: {exc}"
            ) from exc
        except PlaywrightError as exc:
            raise CaptureError(f"Failed to capture {config.url}: {exc}") from exc

        duration_ms = (time.perf_counter() - start) * 1000
        with Image.open(io.BytesIO(image_bytes)) as decoded:
            width, height = decoded.size
        return CaptureResult(
            image_bytes=image_bytes,
            width=width,
            height=height,
            source_type="web",
            source_url=config.url,
            duration_ms=duration_ms,
        )

    def _dismiss_consent_banners(self, page) -> None:
        """Best-effort click of configured cookie/consent selectors; never raises."""
        for selector in self._config.dismiss_consent_selectors:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=1000):
                    locator.click(timeout=1000)
            except PlaywrightError:
                continue
