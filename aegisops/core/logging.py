"""Structured logging setup that avoids recording scenario payloads."""

from __future__ import annotations

import contextvars
import logging
from collections.abc import MutableMapping
from typing import Any

from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore[import-untyped]

# Context variable to hold the request ID for logging
request_id_var: contextvars.ContextVar[Any] = contextvars.ContextVar('request_id', default=None)


class RequestIDFormatter(JsonFormatter):  # type: ignore[misc]
    """JSON log formatter that adds the request ID from context and renames fields."""

    def add_fields(
        self,
        log_record: MutableMapping[str, Any],
        record: logging.LogRecord,
        message_dict: MutableMapping[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        # Rename standard fields to match our desired schema
        if 'levelname' in log_record:
            log_record['level'] = log_record.pop('levelname')
        if 'asctime' in log_record:
            log_record['timestamp'] = log_record.pop('asctime')
        # Add the request ID from context
        log_record['request_id'] = request_id_var.get()


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
        formatter = RequestIDFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)