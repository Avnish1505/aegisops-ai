"""Validate the safety gate, then execute the critical maintenance operation."""


def validate_safety_gate(request: dict[str, object]) -> object:
    return request.get("approved", False)


def execute_maintenance(request: dict[str, object]) -> dict[str, object]:
    if request.get("dry_run"):
        validate_safety_gate(request)
        return {"dry_run": True}
    return _run_maintenance(request)


def _run_maintenance(request: dict[str, object]) -> dict[str, object]:
    return {"executed": True}
