"""OpenAI (GPT) vision provider.

Model id is read from config (default ``gpt-4o``) - RE-VERIFY current
vision-capable model ids against https://platform.openai.com/docs before
relying on this in production.
"""

from __future__ import annotations

import base64
import os
import time

import openai

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


class OpenAIProvider(Provider):
    """Vision-capable description provider backed by the OpenAI Chat Completions API."""

    name = "openai"

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize the provider.

        Args:
            config: Shared provider configuration (model id, timeout, retries).

        Raises:
            ProviderAuthError: If ``OPENAI_API_KEY`` is not set. Never sends a
                request without an explicit key.
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ProviderAuthError(
                "OPENAI_API_KEY environment variable is not set; refusing to call OpenAI."
            )
        self._model = config.openai.model
        self._timeout_s = config.timeout_s
        self._max_retries = config.max_retries
        self._client = openai.OpenAI(api_key=api_key, timeout=config.timeout_s, max_retries=0)

    def describe(self, image_bytes: bytes, media_type: str, prompt: str) -> DescribeResult:
        """See :meth:`scene_agent.providers.base.Provider.describe`."""

        def _once() -> tuple[str, dict | None]:
            encoded = base64.standard_b64encode(image_bytes).decode("ascii")
            data_url = f"data:{media_type};base64,{encoded}"
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        }
                    ],
                )
            except openai.AuthenticationError as exc:
                raise ProviderAuthError(f"OpenAI authentication failed: {exc}") from exc
            except openai.PermissionDeniedError as exc:
                raise ProviderAuthError(f"OpenAI permission denied: {exc}") from exc
            except openai.BadRequestError as exc:
                raise ProviderBadRequestError(f"OpenAI rejected the request: {exc}") from exc
            except openai.RateLimitError as exc:
                raise ProviderRateLimitError(f"OpenAI rate limit: {exc}") from exc
            except openai.APITimeoutError as exc:
                raise ProviderTimeoutError(f"OpenAI request timed out: {exc}") from exc
            except (openai.APIConnectionError, openai.InternalServerError) as exc:
                raise ProviderTransientError(f"OpenAI transient error: {exc}") from exc
            except openai.APIStatusError as exc:
                if exc.status_code >= 500:
                    raise ProviderTransientError(f"OpenAI server error: {exc}") from exc
                raise ProviderBadRequestError(f"OpenAI request error: {exc}") from exc

            text = response.choices[0].message.content or ""
            usage = (
                {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
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
            raise ProviderError(f"Unexpected OpenAI provider failure: {exc}") from exc
        latency_ms = (time.perf_counter() - start) * 1000

        return DescribeResult(
            text=text,
            provider=self.name,
            model=self._model,
            usage=usage,
            latency_ms=latency_ms,
            retry_count=retry_count,
        )
