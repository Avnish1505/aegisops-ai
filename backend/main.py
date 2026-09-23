"""ASGI entry point: ``uvicorn backend.main:app``. Settings come from AEGISOPS_* variables."""

from aegisops.api.app import create_app

app = create_app()
