"""CAP 1.2 (OASIS Common Alerting Protocol) parsing, as published by NDMA SACHET.

Parsed with defusedxml: DTDs and entity expansion are refused, so a hostile feed cannot use
XML bombs or external entities. Required <alert> fields and enumerations follow CAP 1.2.
Area geometry follows the spec: <polygon> is space-separated "lat,lon" pairs (closed ring),
<circle> is "lat,lon radius_km", <geocode> is a valueName/value pair.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as SafeET
from defusedxml import DefusedXmlException

from aegisops.ingestion.models import AlertRecord

NS = "urn:oasis:names:tc:emergency:cap:1.2"
STATUS = {"Actual", "Exercise", "System", "Test", "Draft"}
MSG_TYPE = {"Alert", "Update", "Cancel", "Ack", "Error"}
SCOPE = {"Public", "Restricted", "Private"}
SEVERITY_ORDER = ("Extreme", "Severe", "Moderate", "Minor", "Unknown")


class CapParseError(ValueError):
    """The document is not a valid CAP 1.2 alert."""


@dataclass(frozen=True, slots=True)
class CapArea:
    area_desc: str
    polygons: list[list[tuple[float, float]]] = field(default_factory=list)
    circles: list[tuple[float, float, float]] = field(default_factory=list)  # lat, lon, km
    geocodes: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CapInfo:
    language: str
    categories: list[str]
    event: str
    urgency: str
    severity: str
    certainty: str
    headline: str | None
    description: str | None
    instruction: str | None
    effective: datetime | None
    onset: datetime | None
    expires: datetime | None
    parameters: list[tuple[str, str]]
    areas: list[CapArea]


@dataclass(frozen=True, slots=True)
class CapAlert:
    identifier: str
    sender: str
    sent: datetime
    status: str
    msg_type: str
    scope: str
    references: list[tuple[str, str, str]]  # (sender, identifier, sent)
    infos: list[CapInfo]


def _text(element: Element | None, name: str) -> str | None:
    child = element.find(f"{{{NS}}}{name}") if element is not None else None
    if child is None or child.text is None or not child.text.strip():
        return None
    return child.text.strip()


def _required(element: Element, name: str) -> str:
    value = _text(element, name)
    if value is None:
        raise CapParseError(f"required CAP element <{name}> is missing")
    return value


def _time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CapParseError(f"invalid CAP dateTime {value!r}") from error
    if parsed.tzinfo is None:
        raise CapParseError(f"CAP dateTime must carry a timezone: {value!r}")
    return parsed


def _pair(text: str) -> tuple[float, float]:
    lat, lon = (float(part) for part in text.split(","))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(text)
    return lat, lon


def _area(element: Element) -> CapArea:
    polygons: list[list[tuple[float, float]]] = []
    for polygon in element.findall(f"{{{NS}}}polygon"):
        try:
            ring = [_pair(pair) for pair in (polygon.text or "").split()]
        except ValueError as error:
            raise CapParseError(f"invalid CAP polygon {polygon.text!r}") from error
        if len(ring) < 4 or ring[0] != ring[-1]:
            raise CapParseError("CAP polygon needs at least 4 points with the first repeated last")
        polygons.append(ring)
    circles: list[tuple[float, float, float]] = []
    for circle in element.findall(f"{{{NS}}}circle"):
        try:
            centre, radius = (circle.text or "").split()
            lat, lon = _pair(centre)
            circles.append((lat, lon, float(radius)))
        except ValueError as error:
            raise CapParseError(f"invalid CAP circle {circle.text!r}") from error
    geocodes = [
        (_required(code, "valueName"), _required(code, "value"))
        for code in element.findall(f"{{{NS}}}geocode")
    ]
    return CapArea(_required(element, "areaDesc"), polygons, circles, geocodes)


def _info(element: Element) -> CapInfo:
    categories = [c.text.strip() for c in element.findall(f"{{{NS}}}category") if c.text]
    if not categories:
        raise CapParseError("CAP <info> needs at least one <category>")
    return CapInfo(
        language=_text(element, "language") or "en-US",
        categories=categories,
        event=_required(element, "event"),
        urgency=_required(element, "urgency"),
        severity=_required(element, "severity"),
        certainty=_required(element, "certainty"),
        headline=_text(element, "headline"),
        description=_text(element, "description"),
        instruction=_text(element, "instruction"),
        effective=_time(_text(element, "effective")),
        onset=_time(_text(element, "onset")),
        expires=_time(_text(element, "expires")),
        parameters=[
            (_required(p, "valueName"), _text(p, "value") or "")
            for p in element.findall(f"{{{NS}}}parameter")
        ],
        areas=[_area(area) for area in element.findall(f"{{{NS}}}area")],
    )


def parse_cap(document: bytes) -> CapAlert:
    try:
        root = SafeET.fromstring(document, forbid_dtd=True)
    except (DefusedXmlException, SafeET.ParseError) as error:
        raise CapParseError(f"not well-formed or unsafe XML: {error}") from error
    if root.tag != f"{{{NS}}}alert":
        raise CapParseError(f"root element is {root.tag}, not a CAP 1.2 <alert>")
    status, msg_type, scope = (_required(root, n) for n in ("status", "msgType", "scope"))
    for value, allowed, name in ((status, STATUS, "status"), (msg_type, MSG_TYPE, "msgType"),
                                 (scope, SCOPE, "scope")):
        if value not in allowed:
            raise CapParseError(f"CAP <{name}> {value!r} is not one of {sorted(allowed)}")
    sent = _time(_required(root, "sent"))
    assert sent is not None
    references: list[tuple[str, str, str]] = []
    for reference in (_text(root, "references") or "").split():
        parts = reference.split(",")
        if len(parts) != 3:
            raise CapParseError(f"CAP reference must be sender,identifier,sent: {reference!r}")
        references.append((parts[0], parts[1], parts[2]))
    return CapAlert(
        identifier=_required(root, "identifier"),
        sender=_required(root, "sender"),
        sent=sent,
        status=status,
        msg_type=msg_type,
        scope=scope,
        references=references,
        infos=[_info(info) for info in root.findall(f"{{{NS}}}info")],
    )


def cap_to_record(document: bytes, source_ref: str | None = None) -> AlertRecord:
    """Normalise a CAP document; the English <info> (or the first) supplies the summary."""
    alert = parse_cap(document)
    info = next((i for i in alert.infos if i.language.lower().startswith("en")), None) or (
        alert.infos[0] if alert.infos else None
    )
    centroid: tuple[float, float] | None = None
    if info is not None:
        points = [p for area in info.areas for ring in area.polygons for p in ring[:-1]]
        points += [(c[0], c[1]) for area in info.areas for c in area.circles]
        if points:
            centroid = (
                sum(p[0] for p in points) / len(points),
                sum(p[1] for p in points) / len(points),
            )
    return AlertRecord(
        source="sachet",
        identifier=alert.identifier,
        source_ref=source_ref,
        raw_payload=document.decode("utf-8", errors="replace"),
        sent_at=alert.sent,
        event=info.event if info else None,
        severity=info.severity if info else None,
        headline=info.headline if info else None,
        area_desc="; ".join(a.area_desc for a in info.areas) if info else None,
        lat=centroid[0] if centroid else None,
        lon=centroid[1] if centroid else None,
        parsed=_jsonable(asdict(alert)),
    )


def _jsonable(value: object) -> dict[str, object]:
    def convert(item: object) -> object:
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, dict):
            return {key: convert(val) for key, val in item.items()}
        if isinstance(item, list | tuple):
            return [convert(val) for val in item]
        return item

    converted = convert(value)
    assert isinstance(converted, dict)
    return converted
