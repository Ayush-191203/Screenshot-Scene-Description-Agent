"""NVIDIA API Catalog vision provider (OpenAI-compatible endpoint).

Default model is ``nvidia/nemotron-3.5-super-vl-120b-a12b`` - verified working
end-to-end against this endpoint (real Finviz screenshot, downscaled to the
pipeline's 1568px cap: ~8.1s total latency, accurate description). It requires
an ``extra_body={"chat_template_kwargs": {"enable_thinking": False}}`` field;
without it the endpoint returns a fast HTTP 500. ``enable_thinking`` is forced
to ``False`` here to avoid reasoning-mode latency overhead on the ~15s budget.

``meta/llama-3.2-11b-vision-instruct`` is also listed in config as an
alternative, but during development it hung indefinitely (no response even
after 100s) on this API key/tier - likely not currently provisioned. RE-VERIFY
both model ids and this request shape against https://build.nvidia.com before
relying on them in production; NVIDIA's hosted model lineup changes over time.

Uses the official OpenAI SDK pointed at NVIDIA's endpoint since the API is
OpenAI-compatible; the same SDK exception types are therefore raised.
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

_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaProvider(Provider):
    """Vision-capable description provider backed by NVIDIA's API Catalog."""

    name = "nvidia"

    def __init__(self, config: ProviderConfig) -> None:
        """Initialize the provider.

        Args:
            config: Shared provider configuration (model id, timeout, retries).

        Raises:
            ProviderAuthError: If ``NVIDIA_API_KEY`` is not set. Never sends a
                request without an explicit key.
        """
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise ProviderAuthError(
                "NVIDIA_API_KEY environment variable is not set; refusing to call NVIDIA."
            )
        self._model = config.nvidia.model
        self._max_retries = config.max_retries
        self._client = openai.OpenAI(
            api_key=api_key, base_url=_NVIDIA_BASE_URL, timeout=config.timeout_s, max_retries=0
        )

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
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
            except openai.AuthenticationError as exc:
                raise ProviderAuthError(f"NVIDIA authentication failed: {exc}") from exc
            except openai.PermissionDeniedError as exc:
                raise ProviderAuthError(f"NVIDIA permission denied: {exc}") from exc
            except openai.BadRequestError as exc:
                raise ProviderBadRequestError(f"NVIDIA rejected the request: {exc}") from exc
            except openai.RateLimitError as exc:
                raise ProviderRateLimitError(f"NVIDIA rate limit: {exc}") from exc
            except openai.APITimeoutError as exc:
                raise ProviderTimeoutError(f"NVIDIA request timed out: {exc}") from exc
            except (openai.APIConnectionError, openai.InternalServerError) as exc:
                raise ProviderTransientError(f"NVIDIA transient error: {exc}") from exc
            except openai.APIStatusError as exc:
                if exc.status_code >= 500:
                    raise ProviderTransientError(f"NVIDIA server error: {exc}") from exc
                raise ProviderBadRequestError(f"NVIDIA request error: {exc}") from exc

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
            raise ProviderError(f"Unexpected NVIDIA provider failure: {exc}") from exc
        latency_ms = (time.perf_counter() - start) * 1000

        return DescribeResult(
            text=text,
            provider=self.name,
            model=self._model,
            usage=usage,
            latency_ms=latency_ms,
            retry_count=retry_count,
        )
