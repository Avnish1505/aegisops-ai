"""Validate the payment safety gate, then commit the payment."""

from typing import TypedDict


class Payment(TypedDict):
    amount: float
    currency: str


def validate_payment_safety_gate(payment: Payment) -> bool:
    return payment.get("amount", 0) > 0 and payment.get("currency") is not None


def commit_payment(payment: Payment) -> dict[str, object]:
    if not validate_payment_safety_gate(payment):
        raise ValueError("payment failed safety validation")
    return _write_ledger_entry(payment)


def _write_ledger_entry(payment: Payment) -> dict[str, object]:
    return {"ledger_id": "abc123", "amount": payment["amount"]}
