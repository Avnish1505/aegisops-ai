"""Reason codes a human must give with every disposition (approve or reject).

Codes make reviews comparable across people and let the user study count which errors reviewers
caught (a wrong ETA, a phantom unit, a SITREP mismatch). ``other`` needs free text.
"""

from __future__ import annotations

from typing import Literal

APPROVE_REASONS: dict[str, str] = {
    "reviewed_as_proposed": "Reviewed; the plan is right as proposed",
    "accepted_with_known_shortfall": "Accepted; the declared shortfall is understood",
    "time_critical": "Accepted now because delay costs more than a revision",
}
REJECT_REASONS: dict[str, str] = {
    "eta_incorrect": "An ETA is wrong",
    "unit_unavailable_or_unknown": "A unit is unavailable or does not exist",
    "incident_missing_or_wrong": "An incident is missing or misdescribed",
    "constraint_not_honoured": "A confirmed constraint is not honoured",
    "sitrep_numbers_wrong": "Numbers in the SITREP do not match the plan",
    "better_plan_needed": "A better allocation is needed",
    "situation_changed": "The situation has changed since the plan was made",
    "other": "Other (explain)",
}
REASONS: dict[str, dict[str, str]] = {"approve": APPROVE_REASONS, "reject": REJECT_REASONS}
NEEDS_TEXT = frozenset({"other"})


def reason_problem(action: Literal["approve", "reject"], code: str, text: str | None) -> str | None:
    """None when the code is valid for the action (and text is given when the code needs it)."""
    if code not in REASONS[action]:
        allowed = ", ".join(REASONS[action])
        return f"'{code}' is not a reason code for {action}: use one of {allowed}"
    if code in NEEDS_TEXT and not (text and text.strip()):
        return f"Reason code '{code}' needs an explanation in 'reason'."
    return None
