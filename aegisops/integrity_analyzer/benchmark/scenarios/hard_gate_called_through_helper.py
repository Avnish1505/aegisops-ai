"""Validate the safety gate through the shared pre-flight check, then commit the deployment."""


def validate_safety_gate(plan: dict[str, object]) -> object:
    return plan.get("reviewed", False)


def preflight_check(plan: dict[str, object]) -> object:
    return validate_safety_gate(plan)


def commit_deployment(plan: dict[str, object]) -> dict[str, object]:
    if not preflight_check(plan):
        raise PermissionError("deployment blocked by preflight check")
    return _apply(plan)


def _apply(plan: dict[str, object]) -> dict[str, object]:
    return {"applied": True}
