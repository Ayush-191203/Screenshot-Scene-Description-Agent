"""Retry behavior tests: fail-then-succeed, permanent auth failure, timeout exhaustion."""

from __future__ import annotations

import pytest

from scene_agent.errors import ProviderAuthError, ProviderTimeoutError
from scene_agent.providers.base import call_with_retries


def test_retry_succeeds_after_transient_failures() -> None:
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ProviderTimeoutError("simulated timeout")
        return "ok"

    result, retry_count = call_with_retries(flaky, max_attempts=3)
    assert result == "ok"
    assert retry_count == 2
    assert attempts["count"] == 3


def test_retry_does_not_retry_auth_errors() -> None:
    attempts = {"count": 0}

    def always_auth_error() -> str:
        attempts["count"] += 1
        raise ProviderAuthError("bad key")

    with pytest.raises(ProviderAuthError):
        call_with_retries(always_auth_error, max_attempts=3)
    assert attempts["count"] == 1  # never retried


def test_retry_exhausts_after_max_attempts_on_persistent_timeout() -> None:
    attempts = {"count": 0}

    def always_times_out() -> str:
        attempts["count"] += 1
        raise ProviderTimeoutError("still timing out")

    with pytest.raises(ProviderTimeoutError):
        call_with_retries(always_times_out, max_attempts=3)
    assert attempts["count"] == 3
