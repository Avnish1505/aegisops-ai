"""Validate the identity gate and the risk gate, then allocate funds."""


def validate_identity_gate(user):
    return user.get("verified", False)


def validate_risk_gate(user):
    return user.get("risk_score", 1.0) < 0.5


def allocate_funds(user, amount):
    if not validate_identity_gate(user):
        raise PermissionError("identity not verified")
    if not validate_risk_gate(user):
        raise PermissionError("risk too high")
    return _transfer(user, amount)


def _transfer(user, amount):
    return {"transferred": amount}
