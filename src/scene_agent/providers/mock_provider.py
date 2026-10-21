"""Deterministic mock provider for offline tests and demos (no network calls)."""

from __future__ import annotations

import hashlib
import time

from scene_agent.config import ProviderConfig
from scene_agent.providers.base import DescribeResult, Provider


class MockProvider(Provider):
    """Returns a fixed, deterministic description without any network access."""

    name = "mock"

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize the provider.

        Args:
            config: Shared provider configuration; only ``mock.fixed_text`` is used.
        """
        self._fixed_text = config.mock.fixed_text

    def describe(self, image_bytes: bytes, media_type: str, prompt: str) -> DescribeResult:
        """Return a deterministic description derived from the image content hash.

        Args:
            image_bytes: Encoded image bytes (unused beyond hashing).
            media_type: MIME type of ``image_bytes`` (unused).
            prompt: The prompt that would have been sent (unused by the mock).

        Returns:
            A :class:`DescribeResult` with ``provider="mock"`` and no retries.
        """
        start = time.perf_counter()
        digest = hashlib.sha256(image_bytes).hexdigest()[:12]
        text = f"{self._fixed_text} (image sha256 prefix: {digest})"
        latency_ms = (time.perf_counter() - start) * 1000
        return DescribeResult(
            text=text,
            provider=self.name,
            model="mock-v1",
            usage={"input_tokens": 0, "output_tokens": 0},
            latency_ms=latency_ms,
            retry_count=0,
        )
