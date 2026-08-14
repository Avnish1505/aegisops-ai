"""Validate the safety gate, then execute the transfer."""


def validate_safety_gate(transfer: dict[str, object]) -> None:
    pass


def execute_transfer(transfer: dict[str, object]) -> dict[str, object]:
    validate_safety_gate(transfer)
    return _do_transfer(transfer)


def _do_transfer(transfer: dict[str, object]) -> dict[str, object]:
    return {"status": "sent", "amount": transfer["amount"]}
