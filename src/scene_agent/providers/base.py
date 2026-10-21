"""Shared interface and retry helper for vision-LLM providers."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from scene_agent.errors import ProviderRateLimitError, ProviderTimeoutError, ProviderTransientError

_T = TypeVar("_T")

#: Exception types considered transient and therefore retried by :func:`call_with_retries`.
RETRYABLE_EXCEPTIONS = (
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderTransientError,
)


@dataclass(frozen=True)
class DescribeResult:
    """Result of a successful vision-LLM description request.

    Attributes:
        text: The model's textual description of the image.
        provider: Provider name, e.g. "anthropic".
        model: Model id used for the request.
        usage: Token/cost usage dict if the provider reports one, else None.
        latency_ms: Wall-clock time for the (final, successful) API call.
        retry_count: Number of retries that occurred before this success.
    """

    text: str
    provider: str
    model: str
    usage: dict | None
    latency_ms: float
    retry_count: int


class Provider(ABC):
    """Common interface implemented by every vision-LLM provider."""

    name: str

    @abstractmethod
    def describe(self, image_bytes: bytes, media_type: str, prompt: str) -> DescribeResult:
        """Send an image and prompt to the provider and return its description.

        Args:
            image_bytes: Encoded image bytes (already downscaled if needed).
            media_type: MIME type of ``image_bytes``, e.g. "image/png".
            prompt: User-editable instruction sent alongside the image.

        Raises:
            scene_agent.errors.ProviderError: On any failure, after retries are
                exhausted (for transient errors) or immediately (for auth/bad-request).
        """
        raise NotImplementedError


def call_with_retries(
    func: Callable[[], _T],
    *,
    max_attempts: int,
) -> tuple[_T, int]:
    """Call ``func`` with exponential-backoff-with-jitter retries on transient errors.

    Only exceptions in :data:`RETRYABLE_EXCEPTIONS` are retried. Any other
    exception (e.g. auth or bad-request errors) propagates immediately.

    Args:
        func: Zero-argument callable to invoke.
        max_attempts: Total attempts allowed, including the first.

    Returns:
        A tuple of ``(result, retry_count)`` where ``retry_count`` is the
        number of attempts beyond the first.

    Raises:
        The last exception raised by ``func`` if all attempts are exhausted,
        or immediately for non-retryable exceptions.
    """
    attempts = 0

    def _tracked() -> _T:
        nonlocal attempts
        attempts += 1
        return func()

    retryer = Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        reraise=True,
    )
    result = retryer(_tracked)
    return result, attempts - 1


def timed(func: Callable[[], _T]) -> tuple[_T, float]:
    """Run ``func`` and return ``(result, elapsed_ms)``."""
    start = time.perf_counter()
    result = func()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, elapsed_ms
