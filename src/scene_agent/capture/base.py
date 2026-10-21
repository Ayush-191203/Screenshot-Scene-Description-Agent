"""Shared interface for screenshot capture backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureResult:
    """Result of a successful screenshot capture.

    Attributes:
        image_bytes: Full-resolution PNG bytes of the captured screenshot.
        width: Image width in pixels.
        height: Image height in pixels.
        source_type: Either "web" or "window".
        source_url: The captured URL (web backend) or window title (window backend).
        duration_ms: Wall-clock time spent capturing, in milliseconds.
    """

    image_bytes: bytes
    width: int
    height: int
    source_type: str
    source_url: str
    duration_ms: float


class CaptureBackend(ABC):
    """Common interface implemented by every capture backend."""

    @abstractmethod
    def capture(self) -> CaptureResult:
        """Capture a screenshot and return the raw PNG bytes.

        Raises:
            scene_agent.errors.CaptureError: On any failure to produce a screenshot.
        """
        raise NotImplementedError
