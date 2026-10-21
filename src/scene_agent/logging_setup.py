"""Console + rotating-file logging setup.

Logging never writes API keys: handlers format only structured fields plus
messages that have already been passed through
:func:`scene_agent.errors.sanitize_error_message` by the callers that build them.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-8s run_id=%(run_id)s %(name)s: %(message)s"
_DEFAULT_RUN_ID = "-"


class _RunIdDefaultFilter(logging.Filter):
    """Ensures every log record has a ``run_id`` attribute for the formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "run_id"):
            record.run_id = _DEFAULT_RUN_ID
        return True


def setup_logging(
    log_dir: str | Path,
    *,
    level: str = "INFO",
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure the ``scene_agent`` logger hierarchy with console + rotating file handlers.

    Args:
        log_dir: Directory for the rotating log file (created if missing).
        level: Root log level name, e.g. "INFO" or "DEBUG".
        max_bytes: Max size of a single log file before rotating.
        backup_count: Number of rotated log files to keep.

    Returns:
        The configured ``scene_agent`` logger.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("scene_agent")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT)
    run_id_filter = _RunIdDefaultFilter()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(run_id_filter)
    logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "scene_agent.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(run_id_filter)
    logger.addHandler(file_handler)

    return logger


def get_run_logger(run_id: str) -> logging.LoggerAdapter:
    """Return a :class:`logging.LoggerAdapter` that stamps every record with ``run_id``.

    Args:
        run_id: Identifier of the current pipeline run.

    Returns:
        A logger adapter whose log calls automatically include ``run_id``.
    """
    base_logger = logging.getLogger("scene_agent")
    return logging.LoggerAdapter(base_logger, {"run_id": run_id})
