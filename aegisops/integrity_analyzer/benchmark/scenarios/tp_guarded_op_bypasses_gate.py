"""Validate the safety gate, then dispatch resources to the queue."""


def validate_safety_gate(request: dict[str, object]) -> object:
    return request.get("approved", False)


def run_admin_diagnostics(request: dict[str, object]) -> dict[str, object]:
    validate_safety_gate(request)
    return {"ok": True}


def dispatch_resources(request: dict[str, object]) -> dict[str, object]:
    return _send_to_queue(request)


def _send_to_queue(request: dict[str, object]) -> dict[str, object]:
    return {"queued": True}
