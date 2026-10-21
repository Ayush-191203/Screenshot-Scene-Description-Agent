"""Command-line interface for the Screenshot Scene-Description Agent.

Commands:
    run              Execute a single capture/describe/brand run.
    schedule         Run repeatedly on a fixed interval.
    list-windows     Enumerate capturable desktop windows (Windows only).
    validate-config  Load and validate a config file without running anything.
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from scene_agent.config import AppConfig, ConfigError, apply_overrides, load_config
from scene_agent.logging_setup import setup_logging
from scene_agent.pipeline import run_pipeline
from scene_agent.scheduler import run_scheduler

logger = logging.getLogger("scene_agent.cli")


def _add_common_overrides(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="config/config.yaml", help="Path to config YAML file.")
    parser.add_argument("--provider", choices=["anthropic", "openai", "nvidia", "mock"], default=None)
    parser.add_argument("--input-dir", default=None, help="Override paths.input_dir.")
    parser.add_argument("--output-dir", default=None, help="Override paths.output_dir.")
    parser.add_argument("--url", default=None, help="Override capture.web.url.")
    parser.add_argument("--prompt", default=None, help="Override provider.prompt.")
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument("--headless", dest="headless", action="store_true", default=None)
    headless_group.add_argument("--headed", dest="headless", action="store_false", default=None)


def _load_and_configure(args: argparse.Namespace) -> AppConfig:
    load_dotenv()
    config = load_config(args.config)
    config = apply_overrides(
        config,
        provider=getattr(args, "provider", None),
        input_dir=getattr(args, "input_dir", None),
        output_dir=getattr(args, "output_dir", None),
        url=getattr(args, "url", None),
        headless=getattr(args, "headless", None),
        prompt=getattr(args, "prompt", None),
    )
    setup_logging(
        config.paths.log_dir,
        level="INFO",
    )
    return config


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        config = _load_and_configure(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    result = run_pipeline(config)
    print(f"status={result.metadata['status']} run_id={result.run_id}")
    print(f"  original: {result.metadata['paths']['original_png']}")
    print(f"  branded:  {result.metadata['paths']['branded_png']}")
    print(f"  txt:      {result.metadata['paths']['txt']}")
    print(f"  json:     {result.metadata['paths']['json']}")
    if not result.success:
        print(f"  error_code: {result.metadata['error_code']}", file=sys.stderr)
        print(f"  error: {result.metadata['error_message']}", file=sys.stderr)
    return 0 if result.success else 1


def _cmd_schedule(args: argparse.Namespace) -> int:
    try:
        config = _load_and_configure(args)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    run_count = run_scheduler(config, every=args.every, max_runs=args.max_runs)
    print(f"Scheduler stopped after {run_count} run(s).")
    return 0


def _cmd_list_windows(args: argparse.Namespace) -> int:
    from scene_agent.capture.window import list_windows

    try:
        windows = list_windows()
    except Exception as exc:  # covers non-Windows CaptureError and Win32 failures
        print(f"Could not list windows: {exc}", file=sys.stderr)
        return 1

    if not windows:
        print("No capturable windows found.")
        return 0

    print(f"{'TITLE':<60} {'PROCESS':<20} GEOMETRY")
    for window in windows:
        geometry = f"{window.width}x{window.height} @ ({window.left},{window.top})"
        title = (window.title[:57] + "...") if len(window.title) > 60 else window.title
        print(f"{title:<60} {window.process_name:<20} {geometry}")
    return 0


def _cmd_validate_config(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {args.config} is valid.")
    print(f"  capture.mode={config.capture.mode}")
    print(f"  provider.name={config.provider.name}")
    print(f"  paths.input_dir={config.paths.input_dir}")
    print(f"  paths.output_dir={config.paths.output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(prog="scene-agent", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute a single run.")
    _add_common_overrides(run_parser)
    run_parser.set_defaults(func=_cmd_run)

    schedule_parser = subparsers.add_parser("schedule", help="Run repeatedly on an interval.")
    _add_common_overrides(schedule_parser)
    schedule_parser.add_argument("--every", required=True, help="Interval, e.g. '10m', '30s', '1h'.")
    schedule_parser.add_argument("--max-runs", type=int, default=None, help="Optional run limit.")
    schedule_parser.set_defaults(func=_cmd_schedule)

    list_windows_parser = subparsers.add_parser("list-windows", help="List capturable desktop windows.")
    list_windows_parser.set_defaults(func=_cmd_list_windows)

    validate_parser = subparsers.add_parser("validate-config", help="Validate a config file.")
    validate_parser.add_argument("--config", default="config/config.yaml", help="Path to config YAML file.")
    validate_parser.set_defaults(func=_cmd_validate_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
