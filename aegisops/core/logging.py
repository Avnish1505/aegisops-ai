"""Structured logging setup that avoids recording scenario payloads."""

from __future__ import annotations

import logging


def configure_logging(debug: bool) -> None:
    """Configure application logging once; scenario content is never logged by handlers."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
