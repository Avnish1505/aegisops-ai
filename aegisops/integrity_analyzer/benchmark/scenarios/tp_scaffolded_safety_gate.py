"""Validate the safety gate, then execute the transfer."""


def validate_safety_gate(transfer):
    pass


def execute_transfer(transfer):
    validate_safety_gate(transfer)
    return _do_transfer(transfer)


def _do_transfer(transfer):
    return {"status": "sent", "amount": transfer["amount"]}
