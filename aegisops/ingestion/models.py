"""A normalised alert, whatever feed it came from."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AlertRecord:
    source: str  # "sachet" | "usgs" | "gdacs"
    identifier: str  # dedupe key within the source
    raw_payload: str  # exactly what the feed returned for this alert
    sent_at: datetime | None
    event: str | None
    severity: str | None
    headline: str | None
    area_desc: str | None
    lat: float | None = None
    lon: float | None = None
    source_ref: str | None = None  # e.g. the RSS guid that led to a CAP document
    parsed: dict[str, object] = field(default_factory=dict)
