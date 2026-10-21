"""Live provider test - only runs when real API credentials are present in the environment.

This test makes a real network call to the configured provider and is skipped
otherwise, so CI and offline development never require API keys.
"""

from __future__ import annotations

import os

import pytest

from scene_agent.config import ProviderConfig
from scene_agent.providers.registry import get_provider

_HAS_ANTHROPIC_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))
_HAS_OPENAI_KEY = bool(os.environ.get("OPENAI_API_KEY"))


def _tiny_png_bytes() -> bytes:
    import io

    from PIL import Image

    image = Image.new("RGB", (32, 32), (200, 30, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.skipif(not _HAS_ANTHROPIC_KEY, reason="ANTHROPIC_API_KEY not set")
def test_live_anthropic_describe() -> None:
    config = ProviderConfig(name="anthropic")
    provider = get_provider(config)
    result = provider.describe(_tiny_png_bytes(), "image/png", "Describe this test image briefly.")
    assert result.text
    assert result.provider == "anthropic"


@pytest.mark.skipif(not _HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
def test_live_openai_describe() -> None:
    config = ProviderConfig(name="openai")
    provider = get_provider(config)
    result = provider.describe(_tiny_png_bytes(), "image/png", "Describe this test image briefly.")
    assert result.text
    assert result.provider == "openai"
