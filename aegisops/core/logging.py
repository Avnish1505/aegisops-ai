"""Structured logging setup that avoids recording scenario payloads."""

from __future__ import annotations

import contextvars
import logging
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any

from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[import-untyped]

# Context variable to hold the request ID for logging
request_id_var: contextvars.ContextVar[Any] = contextvars.ContextVar('request_id', default=None)


class RequestIDFormatter(JsonFormatter):  # type: ignore[misc]
    """JSON log formatter emitting ``timestamp`` (ISO 8601, UTC), ``level`` and ``request_id``."""

    def __init__(self) -> None:
        # Only real LogRecord attributes may appear in the format string; the JSON formatter
        # copies each one by name, so a made-up name such as %(level)s is always null.
        super().__init__("%(levelname)s %(name)s %(message)s")

    def add_fields(
        self,
        log_record: MutableMapping[str, Any],
        record: logging.LogRecord,
        message_dict: MutableMapping[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        log_record["level"] = log_record.pop("levelname")
        log_record["request_id"] = request_id_var.get()


def configure_logging(debug: bool) -> None:
    """Configure application logging once; scenario content is never logged by handlers."""
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    else:
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        handler = logging.StreamHandler()
        handler.setFormatter(RequestIDFormatter())
        logger.addHandler(handler)