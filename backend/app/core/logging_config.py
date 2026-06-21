"""Centralized logging configuration with structured JSON output.

When New Relic log forwarding is enabled, these JSON-formatted logs are
automatically picked up and forwarded by the Python agent. They are also
useful for Docker log drivers, CloudWatch, or any other log aggregator.
"""

from __future__ import annotations

import json
import logging
import os
import sys


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for structured log parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Attach exception info when present
        if record.exc_info and record.exc_info[0] is not None:
            log_data["error.class"] = record.exc_info[0].__name__
            log_data["error.message"] = str(record.exc_info[1])
            log_data["error.stack"] = self.formatException(record.exc_info)

        # Include extra fields added via `extra={}` or New Relic local decorating
        for key in ("trace.id", "span.id", "entity.name", "entity.guid"):
            value = getattr(record, key, None)
            if value:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(debug: bool | None = None) -> None:
    """Configure the root logger to emit structured JSON to stdout.

    Call this once during application startup (e.g. in the FastAPI lifespan
    handler) so that all downstream ``logging.getLogger(__name__)`` calls
    produce JSON-formatted output.

    Parameters
    ----------
    debug:
        When *True*, set the root level to DEBUG.  When *None* (the default),
        the level is inferred from the ``DEBUG`` environment variable.
    """
    if debug is None:
        debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Quiet down noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "asyncio", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
