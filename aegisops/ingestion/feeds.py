"""Parsers for the three polled feeds. Pure functions over bytes: fetching lives in the worker.

- NDMA SACHET publishes an RSS 2.0 index (``rss_india.xml``) whose items link to CAP 1.2
  documents; ``parse_sachet_rss`` returns those links, and ``cap.cap_to_record`` parses each CAP.
  (``https://sachet.ndma.gov.in/CapFeed`` is the human-facing page that lists these feeds.)
- USGS ``all_day.geojson``: one GeoJSON Feature per earthquake, identified by ``id``.
- GDACS event list (GeoJSON): identified by event type, event id and episode id.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import defusedxml.ElementTree as SafeET
from defusedxml import DefusedXmlException

from aegisops.ingestion.models import AlertRecord


class FeedParseError(ValueError):
    """The feed payload is not what the source documents."""


@dataclass(frozen=True, slots=True)
class RssItem:
    guid: str
    link: str
    title: str | None
    category: str | None
    author: str | None
    published: datetime | None


def parse_sachet_rss(document: bytes) -> list[RssItem]:
    try:
        root = SafeET.fromstring(document, forbid_dtd=True)
    except (DefusedXmlException, SafeET.ParseError) as error:
        raise FeedParseError(f"SACHET RSS is not well-formed or unsafe XML: {error}") from error
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise FeedParseError("SACHET feed is not an RSS 2.0 document")
    items: list[RssItem] = []
    for item in channel.findall("item"):
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        if not link:
            continue
        published = item.findtext("pubDate")
        items.append(
            RssItem(
                guid=guid,
                link=link,
                title=item.findtext("title"),
                category=item.findtext("category"),
                author=item.findtext("author"),
                published=parsedate_to_datetime(published) if published else None,
            )
        )
    return items


def _geojson(document: bytes, source: str) -> list[dict[str, object]]:
    try:
        body = json.loads(document)
    except json.JSONDecodeError as error:
        raise FeedParseError(f"{source} payload is not JSON") from error
    if not isinstance(body, dict) or body.get("type") != "FeatureCollection":
        raise FeedParseError(f"{source} payload is not a GeoJSON FeatureCollection")
    features = body.get("features")
    if not isinstance(features, list):
        raise FeedParseError(f"{source} FeatureCollection has no features list")
    return [feature for feature in features if isinstance(feature, dict)]


def _text(properties: dict[str, object], key: str) -> str | None:
    value = properties.get(key)
    return value.strip() or None if isinstance(value, str) else None


def _point(feature: dict[str, object]) -> tuple[float | None, float | None]:
    geometry = feature.get("geometry")
    if isinstance(geometry, dict) and geometry.get("type") == "Point":
        coordinates = geometry.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            return float(coordinates[1]), float(coordinates[0])  # GeoJSON is lon,lat
    return None, None


def parse_usgs(document: bytes) -> list[AlertRecord]:
    records: list[AlertRecord] = []
    for feature in _geojson(document, "USGS"):
        identifier = feature.get("id")
        properties = feature.get("properties")
        if not isinstance(identifier, str) or not isinstance(properties, dict):
            raise FeedParseError("USGS feature without an id or properties")
        lat, lon = _point(feature)
        time_ms = properties.get("time")
        magnitude = properties.get("mag")
        records.append(
            AlertRecord(
                source="usgs",
                identifier=identifier,
                raw_payload=json.dumps(feature, sort_keys=True),
                sent_at=(
                    datetime.fromtimestamp(time_ms / 1000, tz=UTC)
                    if isinstance(time_ms, int | float)
                    else None
                ),
                event=str(properties.get("type") or "earthquake"),
                severity=None if magnitude is None else f"M{magnitude}",
                headline=_text(properties, "title"),
                area_desc=_text(properties, "place"),
                lat=lat,
                lon=lon,
                parsed=properties,
            )
        )
    return records


def parse_gdacs(document: bytes) -> list[AlertRecord]:
    records: list[AlertRecord] = []
    for feature in _geojson(document, "GDACS"):
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise FeedParseError("GDACS feature without properties")
        event_type, event_id = properties.get("eventtype"), properties.get("eventid")
        if not event_type or event_id is None:
            raise FeedParseError("GDACS feature without eventtype/eventid")
        lat, lon = _point(feature)
        from_date = properties.get("fromdate")
        records.append(
            AlertRecord(
                source="gdacs",
                identifier=f"{event_type}-{event_id}-{properties.get('episodeid', 0)}",
                raw_payload=json.dumps(feature, sort_keys=True),
                # GDACS publishes naive timestamps in UTC.
                sent_at=(
                    datetime.fromisoformat(from_date).replace(tzinfo=UTC)
                    if isinstance(from_date, str)
                    else None
                ),
                event=str(event_type),
                severity=_text(properties, "alertlevel"),
                headline=_text(properties, "name") or _text(properties, "description"),
                area_desc=_text(properties, "country"),
                lat=lat,
                lon=lon,
                parsed=properties,
            )
        )
    return records
