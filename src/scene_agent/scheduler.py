"""Simple, single-threaded scheduler: runs the pipeline on an interval.

A failed run is caught, logged, and the schedule continues. Runs never
overlap because the loop is synchronous. Ctrl+C triggers a graceful shutdown
after the current run completes.
"""

from __future__ import annotations

import logging
import re
import signal
import time

from scene_agent.config import AppConfig
from scene_agent.pipeline import run_pipeline

logger = logging.getLogger("scene_agent.scheduler")

_INTERVAL_PATTERN = re.compile(r"^(\d+)\s*(s|m|h)$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}


def parse_interval(interval: str) -> float:
    """Parse an interval string like ``"10m"``, ``"30s"``, or ``"1h"`` into seconds.

    Args:
        interval: Interval string with a numeric value and unit suffix.

    Returns:
        The interval in seconds.

    Raises:
        ValueError: If the string does not match ``<number><s|m|h>``.
    """
    match = _INTERVAL_PATTERN.match(interval.strip())
    if not match:
        raise ValueError(f"Invalid interval {interval!r}; expected format like '10m', '30s', '1h'.")
    value, unit = match.groups()
    return int(value) * _UNIT_SECONDS[unit.lower()]


def run_scheduler(
    config: AppConfig,
    *,
    every: str,
    max_runs: int | None = None,
) -> int:
    """Run the pipeline repeatedly on a fixed interval until stopped.

    Args:
        config: Fully validated application configuration.
        every: Interval string, e.g. ``"10m"``.
        max_runs: Optional cap on the number of runs before stopping.

    Returns:
        The number of runs executed (for testability).
    """
    interval_s = parse_interval(every)
    stop_requested = False

    def _handle_sigint(signum, frame) -> None:  # pragma: no cover - signal path
        nonlocal stop_requested
        logger.info("Shutdown requested (Ctrl+C); finishing current run then stopping.")
        stop_requested = True

    previous_handler = signal.signal(signal.SIGINT, _handle_sigint)

    run_count = 0
    try:
        while not stop_requested:
            if max_runs is not None and run_count >= max_runs:
                break

            run_start = time.perf_counter()
            try:
                result = run_pipeline(config)
                logger.info(
                    "Scheduled run %d finished with status=%s",
                    run_count + 1,
                    "success" if result.success else "failed",
                )
            except Exception:
                logger.exception("Scheduled run %d raised an unhandled exception", run_count + 1)
            run_count += 1

            if stop_requested or (max_runs is not None and run_count >= max_runs):
                break

            elapsed = time.perf_counter() - run_start
            remaining = max(0.0, interval_s - elapsed)
            _sleep_interruptibly(remaining, lambda: stop_requested)
    finally:
        signal.signal(signal.SIGINT, previous_handler)

    return run_count


def _sleep_interruptibly(duration_s: float, stop_check) -> None:
    """Sleep in small increments so a signal can interrupt promptly."""
    end_time = time.perf_counter() + duration_s
    while time.perf_counter() < end_time:
        if stop_check():
            return
        time.sleep(min(0.5, end_time - time.perf_counter()))
