"""Write alerts once: (source, identifier) is unique, so re-polling never duplicates."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aegisops.ingestion.models import AlertRecord
from backend.db.models import Alert


@dataclass(frozen=True, slots=True)
class StoreResult:
    inserted: int
    duplicates: int


def known_identifiers(session: Session, source: str) -> set[str]:
    return set(session.scalars(select(Alert.identifier).where(Alert.source == source)))


def known_source_refs(session: Session, source: str) -> set[str]:
    refs = session.scalars(
        select(Alert.source_ref).where(Alert.source == source, Alert.source_ref.is_not(None))
    )
    return {ref for ref in refs if ref is not None}


def store_alerts(
    session: Session, records: Iterable[AlertRecord], fetched_at: datetime
) -> StoreResult:
    """Insert unseen alerts. Each insert runs in a savepoint, so a racing duplicate (another
    worker got there first) is counted and skipped instead of failing the whole batch."""
    inserted = duplicates = 0
    seen: dict[str, set[str]] = {}
    for record in records:
        known = seen.setdefault(record.source, known_identifiers(session, record.source))
        if record.identifier in known:
            duplicates += 1
            continue
        try:
            with session.begin_nested():
                session.add(
                    Alert(
                        source=record.source,
                        identifier=record.identifier,
                        source_ref=record.source_ref,
                        fetched_at=fetched_at,
                        sent_at=record.sent_at,
                        event=record.event,
                        severity=record.severity,
                        headline=record.headline,
                        area_desc=record.area_desc,
                        location=(
                            (record.lat, record.lon)
                            if record.lat is not None and record.lon is not None
                            else None
                        ),
                        raw_payload=record.raw_payload,
                        parsed=record.parsed,
                    )
                )
        except IntegrityError:
            duplicates += 1
        else:
            inserted += 1
        known.add(record.identifier)
    return StoreResult(inserted=inserted, duplicates=duplicates)
