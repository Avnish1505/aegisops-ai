"""Validate the safety gate (aliased for readability), then allocate the resource."""


def validate_safety_gate(resource: dict[str, object]) -> object:
    return resource.get("approved", False)


def allocate_resource(resource: dict[str, object]) -> dict[str, object]:
    gate = validate_safety_gate
    if not gate(resource):
        raise PermissionError("resource allocation blocked")
    return _reserve(resource)


def _reserve(resource: dict[str, object]) -> dict[str, object]:
    return {"reserved": True}
