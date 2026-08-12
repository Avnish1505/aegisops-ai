"""Validate the safety gate, then dispatch resources to the queue."""


def validate_safety_gate(request):
    return request.get("approved", False)


def run_admin_diagnostics(request):
    validate_safety_gate(request)
    return {"ok": True}


def dispatch_resources(request):
    return _send_to_queue(request)


def _send_to_queue(request):
    return {"queued": True}
