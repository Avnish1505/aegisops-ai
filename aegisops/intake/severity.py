"""Severity from grounded fields by fixed rules. The model never sets severity.

Rules are checked in order; the first that matches decides. They are deliberately simple and
auditable, and every candidate records which rule fired.
"""

from __future__ import annotations

from collections.abc import Sequence

from aegisops.domain.models import IncidentType, Severity
from aegisops.intake.models import CountField, SignalField, TypeField

LIFE_THREAT = {"drowning", "unconscious", "electrocution"}
SERIOUS = {"trapped", "injured", "missing_person", "fire_spreading", "collapse"}
RULES = (
    ("R1 life-threat signal (drowning, unconscious, electrocution)", Severity.CRITICAL),
    ("R2 people trapped in a collapse", Severity.CRITICAL),
    ("R3 50 or more people affected", Severity.CRITICAL),
    ("R4 trapped, injured, missing, spreading fire or collapse", Severity.HIGH),
    ("R5 fire, structural collapse or hazmat incident", Severity.HIGH),
    ("R6 10 or more people affected", Severity.HIGH),
    ("R7 flood or medical incident, rising water or medical emergency", Severity.MEDIUM),
    ("R8 3 or more people affected", Severity.MEDIUM),
    ("R9 default", Severity.LOW),
)


def severity_for(
    incident_type: TypeField | None,
    people_count: CountField | None,
    signals: Sequence[SignalField],
) -> tuple[Severity, str]:
    kinds = {s.signal for s in signals}
    kind = incident_type.value if incident_type else None
    people = people_count.value if people_count else None
    checks = (
        bool(kinds & LIFE_THREAT),
        "trapped" in kinds and ("collapse" in kinds or kind == IncidentType.STRUCTURAL_COLLAPSE),
        people is not None and people >= 50,
        bool(kinds & SERIOUS),
        kind in {IncidentType.FIRE, IncidentType.STRUCTURAL_COLLAPSE, IncidentType.HAZMAT},
        people is not None and people >= 10,
        bool(kinds & {"water_rising", "medical_emergency"})
        or kind in {IncidentType.FLOOD, IncidentType.MEDICAL},
        people is not None and people >= 3,
        True,
    )
    for (rule, severity), matched in zip(RULES, checks, strict=True):
        if matched:
            return severity, rule
    raise AssertionError("R9 always matches")
