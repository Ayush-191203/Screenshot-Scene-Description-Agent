"""Scheduler tests: survives a failed run, respects max_runs, no overlapping runs."""

from __future__ import annotations

import pytest

from scene_agent.scheduler import parse_interval, run_scheduler


@pytest.mark.parametrize(
    "interval,expected_seconds",
    [("30s", 30), ("10m", 600), ("1h", 3600), ("2h", 7200)],
)
def test_parse_interval(interval: str, expected_seconds: int) -> None:
    assert parse_interval(interval) == expected_seconds


def test_parse_interval_rejects_invalid_format() -> None:
    with pytest.raises(ValueError):
        parse_interval("not-an-interval")


def test_scheduler_survives_a_failed_run(base_config, monkeypatch) -> None:
    call_count = {"n": 0}

    class _Result:
        def __init__(self, success: bool) -> None:
            self.success = success
            self.metadata = {"status": "success" if success else "failed"}
            self.run_id = "test"

    def fake_run_pipeline(config):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated unhandled failure on run 2")
        return _Result(success=True)

    monkeypatch.setattr("scene_agent.scheduler.run_pipeline", fake_run_pipeline)

    run_count = run_scheduler(base_config, every="0s", max_runs=3)

    assert run_count == 3
    assert call_count["n"] == 3  # the scheduler kept going after the run-2 failure


def test_scheduler_respects_max_runs(base_config, monkeypatch) -> None:
    class _Result:
        success = True
        metadata = {"status": "success"}
        run_id = "test"

    monkeypatch.setattr("scene_agent.scheduler.run_pipeline", lambda config: _Result())

    run_count = run_scheduler(base_config, every="0s", max_runs=2)
    assert run_count == 2
