"""Desktop window capture backend (Windows only - FR1).

Finds a window by title substring or owning process name, then grabs its
on-screen bounding box with ``mss``. DPI awareness is set at import time so
window coordinates returned by Win32 match physical pixels.
"""

from __future__ import annotations

import contextlib
import ctypes
import sys
import time
from dataclasses import dataclass

from scene_agent.capture.base import CaptureBackend, CaptureResult
from scene_agent.config import CaptureWindowConfig
from scene_agent.errors import CaptureError, WindowNotFoundError

if sys.platform == "win32":
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2; keeps window rects in physical pixels.
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


@dataclass(frozen=True)
class WindowInfo:
    """Metadata about an enumerated desktop window."""

    title: str
    process_name: str
    left: int
    top: int
    width: int
    height: int
    hwnd: int


def _require_windows_deps():
    """Import pygetwindow/psutil/mss lazily so non-Windows installs can still import this module."""
    if sys.platform != "win32":
        raise CaptureError("Window capture backend is only supported on Windows.")
    import mss
    import psutil
    import pygetwindow as gw
    import win32con
    import win32gui
    import win32process

    return gw, mss, psutil, win32process, win32gui, win32con


def list_windows() -> list[WindowInfo]:
    """Enumerate visible, non-empty top-level windows with their owning process name.

    Returns:
        A list of :class:`WindowInfo` for every window with a non-empty title
        and non-zero size.

    Raises:
        CaptureError: If called on a non-Windows platform.
    """
    gw, _mss, psutil, win32process, _win32gui, _win32con = _require_windows_deps()

    results: list[WindowInfo] = []
    for window in gw.getAllWindows():
        if not window.title or window.width <= 0 or window.height <= 0:
            continue
        process_name = "unknown"
        try:
            _, pid = win32process.GetWindowThreadProcessId(window._hWnd)
            process_name = psutil.Process(pid).name()
        except Exception:
            process_name = "unknown"
        results.append(
            WindowInfo(
                title=window.title,
                process_name=process_name,
                left=window.left,
                top=window.top,
                width=window.width,
                height=window.height,
                hwnd=window._hWnd,
            )
        )
    return results


class WindowCaptureBackend(CaptureBackend):
    """Captures a screenshot of a specific desktop window by title or process name."""

    def __init__(self, config: CaptureWindowConfig) -> None:
        """Initialize the backend.

        Args:
            config: Window capture settings (title/process_name, timeout).
        """
        self._config = config

    def capture(self) -> CaptureResult:
        """Find the configured window and capture its bounding box.

        Returns:
            A :class:`CaptureResult` with PNG bytes of the window region.

        Raises:
            WindowNotFoundError: If no matching window is found before the timeout,
                the message lists all currently available window titles.
            CaptureError: On any other failure (e.g. non-Windows platform, mss error).
        """
        config = self._config
        start = time.perf_counter()
        deadline = start + (config.timeout_ms / 1000)

        match: WindowInfo | None = None
        available: list[WindowInfo] = []
        while time.perf_counter() < deadline and match is None:
            available = list_windows()
            match = self._find_match(available)
            if match is None:
                time.sleep(0.2)

        if match is None:
            titles = ", ".join(sorted({w.title for w in available})) or "(none found)"
            target = config.title or config.process_name
            raise WindowNotFoundError(
                f"No window matched title/process {target!r}. Available windows: {titles}"
            )

        _gw, mss_module, _psutil, _win32process, win32gui, win32con = _require_windows_deps()
        self._bring_to_foreground(match.hwnd, win32gui, win32con)
        # Re-fetch geometry: activation can restore a minimized window or move it.
        refreshed = next((w for w in list_windows() if w.hwnd == match.hwnd), match)

        try:
            with mss_module.mss() as sct:
                monitor = {
                    "left": refreshed.left,
                    "top": refreshed.top,
                    "width": refreshed.width,
                    "height": refreshed.height,
                }
                shot = sct.grab(monitor)
                image_bytes = mss_module.tools.to_png(shot.rgb, shot.size)
        except Exception as exc:
            raise CaptureError(f"Failed to capture window {match.title!r}: {exc}") from exc

        duration_ms = (time.perf_counter() - start) * 1000
        return CaptureResult(
            image_bytes=image_bytes,
            width=refreshed.width,
            height=refreshed.height,
            source_type="window",
            source_url=match.title,
            duration_ms=duration_ms,
        )

    def _bring_to_foreground(self, hwnd: int, win32gui, win32con) -> None:
        """Best-effort: restore and raise the target window so screen-region capture isn't
        occluded by other windows. Windows' focus-stealing prevention can block this when
        called from a non-interactive/background process; failures are logged, not fatal.
        """
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.25)  # let the compositor finish redrawing before the grab
        except Exception:
            pass

    def _find_match(self, windows: list[WindowInfo]) -> WindowInfo | None:
        config = self._config
        for window in windows:
            if config.title and config.title.lower() in window.title.lower():
                return window
            if config.process_name and config.process_name.lower() == window.process_name.lower():
                return window
        return None
