"""Provider registry: maps a config name to a provider factory.

Adding a new provider requires exactly one new module plus one entry in
``_REGISTRY`` below - no changes to the pipeline or CLI.
"""

from __future__ import annotations

from collections.abc import Callable

from scene_agent.config import ProviderConfig
from scene_agent.errors import ConfigError
from scene_agent.providers.anthropic_provider import AnthropicProvider
from scene_agent.providers.base import Provider
from scene_agent.providers.mock_provider import MockProvider
from scene_agent.providers.openai_provider import OpenAIProvider

_REGISTRY: dict[str, Callable[[ProviderConfig], Provider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "mock": MockProvider,
}


def get_provider(config: ProviderConfig) -> Provider:
    """Instantiate the provider selected by ``config.name``.

    Args:
        config: Provider configuration; ``config.name`` selects the implementation.

    Returns:
        A ready-to-use :class:`Provider` instance.

    Raises:
        ConfigError: If ``config.name`` is not a registered provider.
    """
    factory = _REGISTRY.get(config.name)
    if factory is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ConfigError(f"Unknown provider {config.name!r}. Available: {available}")
    return factory(config)
