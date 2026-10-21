"""Provider registry and selection tests."""

from __future__ import annotations

import pytest

from scene_agent.config import ProviderConfig
from scene_agent.errors import ConfigError, ProviderAuthError
from scene_agent.providers.mock_provider import MockProvider
from scene_agent.providers.registry import get_provider


def test_mock_provider_selected_by_name() -> None:
    config = ProviderConfig(name="mock")
    provider = get_provider(config)
    assert isinstance(provider, MockProvider)
    assert provider.name == "mock"


def test_unknown_provider_raises_config_error() -> None:
    # Bypass pydantic's Literal restriction to exercise the registry's own guard.
    config = ProviderConfig(name="mock")
    config.name = "nonexistent"
    with pytest.raises(ConfigError):
        get_provider(config)


def test_anthropic_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = ProviderConfig(name="anthropic")
    with pytest.raises(ProviderAuthError):
        get_provider(config)


def test_openai_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = ProviderConfig(name="openai")
    with pytest.raises(ProviderAuthError):
        get_provider(config)


def test_nvidia_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    config = ProviderConfig(name="nvidia")
    with pytest.raises(ProviderAuthError):
        get_provider(config)


def test_nvidia_provider_constructs_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    config = ProviderConfig(name="nvidia")
    provider = get_provider(config)
    assert provider.name == "nvidia"


def test_mock_provider_describe_is_deterministic() -> None:
    config = ProviderConfig(name="mock")
    provider = get_provider(config)
    result1 = provider.describe(b"same-bytes", "image/png", "prompt")
    result2 = provider.describe(b"same-bytes", "image/png", "prompt")
    assert result1.text == result2.text
    assert result1.retry_count == 0
    assert result1.provider == "mock"
