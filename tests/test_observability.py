"""Observability tests for request IDs and structured logging."""

import re

from fastapi.testclient import TestClient

from aegisops.api.app import app

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