"""Triage rules for read reports: why a report needs a human look, likely duplicates, and turning
operator-confirmed fields into an Incident.

The Reader gives no confidence score and none is invented here. A report needs review for
concrete, checkable reasons: it has not been read, a field was dropped because its quote was not
in the report, the place could not be found or was matched fuzzily, the type is missing, or the
text reads like an instruction. Severity is always recomputed from the (confirmed) fields by the
deterministic rules in ``aegisops.intake.severity``; an operator edits facts, not severity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz import fuzz

from aegisops.application.scenario_service import RESOURCE_REQUIREMENTS
from aegisops.domain.models import Incident, IncidentType, Location, ResourceType, Severity
from aegisops.domain.policy import haversine_km
from aegisops.intake.models import CountField, IncidentCandidate, Signal, SignalField, TypeField
from aegisops.intake.severity import severity_for
from aegisops.verification.injection import looks_like_instruction

DUPLICATE_DISTANCE_KM = 0.3
DUPLICATE_WINDOW_MIN = 30
DUPLICATE_TEXT_SCORE = 85.0
OPERATOR_QUOTE = "(confirmed by operator)"


def review_reasons(text: str, candidate: IncidentCandidate | None) -> list[str]:
    reasons: list[str] = []
    if candidate is None:
        reasons.append("not_read")
    else:
        reasons += [f"field_dropped:{field}" for field in candidate.dropped]
        if candidate.incident_type is None:
            reasons.append("no_incident_type")
        if candidate.geocode is None:
            reasons.append("no_location")
        elif candidate.geocode.method == "fuzzy":
            reasons.append("fuzzy_location")
    if looks_like_instruction(text):
        reasons.append("instruction_like_text")
    return reasons


@dataclass(frozen=True, slots=True)
class ReportView:
    """What duplicate detection needs to know about a stored report."""

    id: int
    text: str
    received_at: datetime
    incident_type: str | None
    lat: float | None
    lon: float | None


def duplicate_of(report: ReportView, others: Sequence[ReportView]) -> list[dict[str, object]]:
    """Other reports that are probably the same incident, with the rule that matched."""
    matches: list[dict[str, object]] = []
    for other in others:
        if other.id == report.id:
            continue
        minutes = abs((report.received_at - other.received_at).total_seconds()) / 60
        near = (
            report.lat is not None and other.lat is not None
            and report.lon is not None and other.lon is not None
            and haversine_km(Location(lat=report.lat, lon=report.lon),
                             Location(lat=other.lat, lon=other.lon)) <= DUPLICATE_DISTANCE_KM
        )
        same_type = report.incident_type is not None and report.incident_type == other.incident_type
        text_score = fuzz.token_set_ratio(report.text.lower(), other.text.lower())
        if near and same_type and minutes <= DUPLICATE_WINDOW_MIN:
            matches.append({"id": other.id, "rule": "same type within 300 m and 30 min",
                            "text_score": round(text_score, 1)})
        elif text_score >= DUPLICATE_TEXT_SCORE:
            matches.append({"id": other.id, "rule": "near-identical text",
                            "text_score": round(text_score, 1)})
    return matches


class ConfirmedPlace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class ConfirmedFields(BaseModel):
    """The facts an operator signs off. Each is either the model's grounded value or an edit."""

    model_config = ConfigDict(extra="forbid")

    incident_type: IncidentType
    place: ConfirmedPlace
    people_count: int | None = Field(default=None, ge=0, le=100_000)
    needs: dict[ResourceType, int] = Field(default_factory=dict)
    signals: list[Signal] = Field(default_factory=list)


def fields_from_candidate(candidate: IncidentCandidate) -> ConfirmedFields | None:
    """The model's grounded reading as a starting point, or None if type or place is missing."""
    if candidate.incident_type is None or candidate.geocode is None:
        return None
    return ConfirmedFields(
        incident_type=candidate.incident_type.value,
        place=ConfirmedPlace(name=candidate.geocode.name, lat=candidate.geocode.lat,
                             lon=candidate.geocode.lon),
        people_count=candidate.people_count.value if candidate.people_count else None,
        needs={need.resource_type: need.quantity for need in candidate.needs},
        signals=[signal.signal for signal in candidate.signals],
    )


def edited_fields(candidate: IncidentCandidate | None, confirmed: ConfirmedFields) -> list[str]:
    """Which confirmed fields differ from the model's grounded reading."""
    original = fields_from_candidate(candidate) if candidate else None
    if original is None:
        return sorted(ConfirmedFields.model_fields)
    return sorted(
        name for name in ConfirmedFields.model_fields
        if getattr(original, name) != getattr(confirmed, name)
        and not (name == "signals" and sorted(original.signals) == sorted(confirmed.signals))
    )


def confirmed_severity(fields: ConfirmedFields) -> tuple[str, str]:
    severity, rule = severity_for(
        TypeField(value=fields.incident_type, quote=OPERATOR_QUOTE),
        CountField(value=fields.people_count, quote=OPERATOR_QUOTE)
        if fields.people_count is not None else None,
        [SignalField(signal=signal, quote=OPERATOR_QUOTE) for signal in fields.signals],
    )
    return severity.value, rule


def incident_from_fields(
    fields: ConfirmedFields, incident_id: str, report: str, reported_at_min: int
) -> Incident:
    severity, _ = confirmed_severity(fields)
    needs = dict(fields.needs) or dict(RESOURCE_REQUIREMENTS[fields.incident_type])
    return Incident(
        id=incident_id,
        type=fields.incident_type,
        severity=Severity(severity),
        location=Location(lat=fields.place.lat, lon=fields.place.lon),
        people_affected=fields.people_count or 0,
        reported_at_min=reported_at_min,
        resources_needed=needs,
        report=report[:2_000],
    )
