"""Observability tests for request IDs and structured logging."""

import json
import logging
import re
from datetime import datetime

from fastapi.testclient import TestClient

from aegisops.api.app import app
from aegisops.core.logging import RequestIDFormatter, request_id_var

client = TestClient(app)


def test_request_id_header_present():
    """Test that the X-Request-ID header is present in responses."""
    response = client.get("/health/live")
    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    # Check that it's a valid UUID (version 4)
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[4][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        re.I
    )
    assert uuid_pattern.match(request_id), f"Invalid UUID format: {request_id}"


def test_metrics_endpoint():
    """Test that the /metrics endpoint returns Prometheus metrics."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    # Check that we have some metric lines
    assert len(response.text) > 0
    # Look for a known metric from fastapi or starlette
    # We'll just check that there's at least one line that looks like a metric
    lines = [line for line in response.text.split('\n') if line and not line.startswith('#')]
    assert len(lines) > 0, "No metric lines found in output"

def test_json_log_record_has_real_timestamp_and_level():
    """JSON logs must carry a parseable timestamp and the record's level, never null."""
    record = logging.LogRecord(
        name="aegisops.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="decision_created id=%s",
        args=(7,),
        exc_info=None,
    )
    token = request_id_var.set("trace-log")
    try:
        payload = json.loads(RequestIDFormatter().format(record))
    finally:
        request_id_var.reset(token)

    assert payload["level"] == "WARNING"
    assert payload["message"] == "decision_created id=7"
    assert payload["request_id"] == "trace-log"
    parsed = datetime.fromisoformat(payload["timestamp"])
    assert parsed.tzinfo is not None
    assert abs(parsed.timestamp() - record.created) < 1
