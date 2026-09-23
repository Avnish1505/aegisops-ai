"""What the Reader asks the model for, and what it keeps after grounding."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from aegisops.domain.models import IncidentType, ResourceType, Severity

Signal = Literal[
    "trapped",
    "injured",
    "unconscious",
    "drowning",
    "electrocution",
    "collapse",
    "fire_spreading",
    "water_rising",
    "missing_person",
    "medical_emergency",
]
Quote = Annotated[str, Field(min_length=1, max_length=500)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TypeField(_Strict):
    value: IncidentType
    quote: Quote


class TextField(_Strict):
    value: Annotated[str, Field(min_length=1, max_length=200)]
    quote: Quote


class CountField(_Strict):
    value: Annotated[int, Field(ge=0, le=100_000)]
    quote: Quote


class Need(_Strict):
    resource_type: ResourceType
    quantity: Annotated[int, Field(ge=1, le=100)]
    quote: Quote


class SignalField(_Strict):
    signal: Signal
    quote: Quote


class ReaderOutput(_Strict):
    """The JSON schema the model must fill (constrained decoding)."""

    language: Literal["en", "hi", "hinglish", "other"]
    incident_type: TypeField | None
    location: TextField | None
    people_count: CountField | None
    needs: list[Need]
    signals: list[SignalField]


class Geocode(_Strict):
    lat: float
    lon: float
    name: str
    osm: str
    kind: str
    method: str
    score: float


class IncidentCandidate(_Strict):
    """A grounded reading of one report. Every value has a quote found verbatim in the report."""

    report: str
    language: str
    incident_type: TypeField | None
    location_text: TextField | None
    people_count: CountField | None
    needs: list[Need]
    signals: list[SignalField]
    severity: Severity  # from aegisops.intake.severity rules, never from the model
    severity_rule: str
    geocode: Geocode | None
    dropped: list[str]  # fields the model returned whose quote failed grounding
