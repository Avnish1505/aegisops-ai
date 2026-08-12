"""Validate the shutdown safety gate, log the attempt, then execute the shutdown."""


def validate_shutdown_safety_gate(system):
    return system.get("maintenance_mode", False)


def execute_shutdown(system):
    log_attempt(system)
    if not validate_shutdown_safety_gate(system):
        raise PermissionError("shutdown blocked: not in maintenance mode")
    return _power_off(system)


def log_attempt(system):
    return {"logged": True, "system": system.get("name")}


def _power_off(system):
    return {"powered_off": True}
