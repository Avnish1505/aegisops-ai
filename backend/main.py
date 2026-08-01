"""Backward-compatible ASGI entry point for ``uvicorn backend.main:app``."""

from aegisops.api.app import app as application

app = application
