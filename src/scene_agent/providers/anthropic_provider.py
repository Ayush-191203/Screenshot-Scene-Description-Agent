"""Anthropic (Claude) vision provider.

Model id is read from config (default ``claude-sonnet-4-20250514``) - RE-VERIFY
current vision-capable model ids against https://docs.anthropic.com before
relying on this in production.
"""

from __future__ import annotations

import base64
import os
import time

import anthropic

from scene_agent.config import ProviderConfig
from scene_agent.errors import (
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderTransientError,
)
from scene_agent.providers.base import DescribeResult, Provider, call_with_retries


class AnthropicProvider(Provider):
    """Vision-capable description provider backed by the Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize the provider.

        Args:
            config: Shared provider configuration (model id, timeout, retries).

        Raises:
            ProviderAuthError: If ``ANTHROPIC_API_KEY`` is not set. Never sends
                a request without an explicit key.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderAuthError(
                "ANTHROPIC_API_KEY environment variable is not set; refusing to call Anthropic."
            )
        self._model = config.anthropic.model
        self._timeout_s = config.timeout_s
        self._max_retries = config.max_retries
        self._client = anthropic.Anthropic(api_key=api_key, timeout=config.timeout_s, max_retries=0)

    def describe(self, image_bytes: bytes, media_type: str, prompt: str) -> DescribeResult:
        """See :meth:`scene_agent.providers.base.Provider.describe`."""

        def _once() -> tuple[str, dict | None]:
            encoded = base64.standard_b64encode(image_bytes).decode("ascii")
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": encoded,
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                )
            except anthropic.AuthenticationError as exc:
                raise ProviderAuthError(f"Anthropic authentication failed: {exc}") from exc
            except anthropic.PermissionDeniedError as exc:
                raise ProviderAuthError(f"Anthropic permission denied: {exc}") from exc
            except anthropic.BadRequestError as exc:
                raise ProviderBadRequestError(f"Anthropic rejected the request: {exc}") from exc
            except anthropic.RateLimitError as exc:
                raise ProviderRateLimitError(f"Anthropic rate limit: {exc}") from exc
            except anthropic.APITimeoutError as exc:
                raise ProviderTimeoutError(f"Anthropic request timed out: {exc}") from exc
            except (anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
                raise ProviderTransientError(f"Anthropic transient error: {exc}") from exc
            except anthropic.APIStatusError as exc:
                if exc.status_code >= 500:
                    raise ProviderTransientError(f"Anthropic server error: {exc}") from exc
                raise ProviderBadRequestError(f"Anthropic request error: {exc}") from exc

            text = "".join(
                block.text for block in response.content if getattr(block, "type", None) == "text"
            )
            usage = (
                {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
                if response.usage
                else None
            )
            return text, usage

        start = time.perf_counter()
        try:
            (text, usage), retry_count = call_with_retries(_once, max_attempts=self._max_retries)
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - defensive catch-all
            raise ProviderError(f"Unexpected Anthropic provider failure: {exc}") from exc
        latency_ms = (time.perf_counter() - start) * 1000

        return DescribeResult(
            text=text,
            provider=self.name,
            model=self._model,
            usage=usage,
            latency_ms=latency_ms,
            retry_count=retry_count,
        )
