"""Validate the identity gate and the risk gate, then allocate funds."""

from typing import TypedDict


class User(TypedDict):
    verified: bool
    risk_score: float


def validate_identity_gate(user: User) -> bool:
    return user.get("verified", False)


def validate_risk_gate(user: User) -> bool:
    return user.get("risk_score", 1.0) < 0.5


def allocate_funds(user: User, amount: float) -> dict[str, object]:
    if not validate_identity_gate(user):
        raise PermissionError("identity not verified")
    if not validate_risk_gate(user):
        raise PermissionError("risk too high")
    return _transfer(user, amount)


def _transfer(user: User, amount: float) -> dict[str, object]:
    return {"transferred": amount}
