"""Validate the shutdown safety gate, log the attempt, then execute the shutdown."""


def validate_shutdown_safety_gate(system: dict[str, object]) -> object:
    return system.get("maintenance_mode", False)


def execute_shutdown(system: dict[str, object]) -> dict[str, object]:
    log_attempt(system)
    if not validate_shutdown_safety_gate(system):
        raise PermissionError("shutdown blocked: not in maintenance mode")
    return _power_off(system)


def log_attempt(system: dict[str, object]) -> dict[str, object]:
    return {"logged": True, "system": system.get("name")}


def _power_off(system: dict[str, object]) -> dict[str, object]:
    return {"powered_off": True}
