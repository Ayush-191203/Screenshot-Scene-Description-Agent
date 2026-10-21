"""Custom exception hierarchy for the Screenshot Scene-Description Agent.

Every exception carries a stable ``error_code`` string that is written into the
JSON run metadata, and a human-readable message that is safe to log (callers
should still pass messages through :func:`sanitize_error_message` before
persisting free-form text originating from external services).
"""

from __future__ import annotations

import re

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"(?i)(api[_-]?key|authorization|bearer)\s*[:=]\s*\S+"),
]


def sanitize_error_message(message: str) -> str:
    """Redact substrings that look like API keys or auth headers from a message.

    Args:
        message: Raw error message, possibly containing sensitive tokens.

    Returns:
        The message with any matched secrets replaced by ``"***REDACTED***"``.
    """
    sanitized = message
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("***REDACTED***", sanitized)
    return sanitized


class SceneAgentError(Exception):
    """Base class for all errors raised by this application."""

    error_code: str = "UNKNOWN"

    def __init__(self, message: str) -> None:
        super().__init__(sanitize_error_message(message))


class ConfigError(SceneAgentError):
    """Raised when configuration loading or validation fails."""

    error_code = "CONFIG_ERROR"


class CaptureError(SceneAgentError):
    """Base class for screenshot capture failures."""

    error_code = "CAPTURE_ERROR"


class CaptureTimeoutError(CaptureError):
    """Raised when navigation or readiness waits exceed the configured timeout."""

    error_code = "CAPTURE_TIMEOUT"


class WindowNotFoundError(CaptureError):
    """Raised when no desktop window matches the requested title/process name."""

    error_code = "WINDOW_NOT_FOUND"


class ProviderError(SceneAgentError):
    """Base class for vision-LLM provider failures."""

    error_code = "PROVIDER_ERROR"


class ProviderAuthError(ProviderError):
    """Raised for authentication/authorization failures. Never retried."""

    error_code = "PROVIDER_AUTH_ERROR"


class ProviderBadRequestError(ProviderError):
    """Raised for malformed/rejected requests (4xx other than auth/rate-limit). Never retried."""

    error_code = "PROVIDER_BAD_REQUEST"


class ProviderRateLimitError(ProviderError):
    """Raised when the provider reports rate limiting. Retried."""

    error_code = "PROVIDER_RATE_LIMIT"


class ProviderTimeoutError(ProviderError):
    """Raised when a request to the provider times out. Retried."""

    error_code = "PROVIDER_TIMEOUT"


class ProviderTransientError(ProviderError):
    """Raised for connection errors or 5xx server errors. Retried."""

    error_code = "PROVIDER_TRANSIENT"


class ImagingError(SceneAgentError):
    """Base class for Pillow-based branding/caption failures."""

    error_code = "IMAGING_ERROR"


class LogoError(ImagingError):
    """Raised when the configured logo file is missing or cannot be decoded."""

    error_code = "LOGO_ERROR"


class ArtifactError(SceneAgentError):
    """Raised when writing output artifacts (PNG/TXT/JSON) fails."""

    error_code = "ARTIFACT_ERROR"
