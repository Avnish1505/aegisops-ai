"""Hash-chained audit events.

hash = sha256(prev_hash + canonical_json({id, ts, actor, type, payload})); the first event's
prev_hash is GENESIS_HASH. ``prev_hash`` is unique, so two writers racing to extend the same head
cannot fork the chain: one insert fails and must retry.

Events that create a decision or an approval carry the SHA-256 of that row's content, so editing
the row itself (not just the event) is also detected.

Limit: deleting the newest event leaves a valid, shorter chain. Keep ``head_hash`` somewhere
outside the database to detect truncation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegisops.domain.canonical import canonical_json, sha256_hex
from backend.db.models import Approval, Decision, Event

GENESIS_HASH = "0" * 64


def event_hash(
    prev_hash: str, event_id: int, ts: str, actor: str, event_type: str, payload: object
) -> str:
    body = canonical_json(
        {"id": event_id, "ts": ts, "actor": actor, "type": event_type, "payload": payload}
    )
    return sha256_hex(prev_hash + body)


def append_event(session: Session, *, actor: str, type: str, payload: dict[str, object]) -> Event:
    head = session.scalars(select(Event).order_by(Event.id.desc()).limit(1)).first()
    event_id = head.id + 1 if head is not None else 1
    prev_hash = head.hash if head is not None else GENESIS_HASH
    ts = datetime.now(UTC).isoformat(timespec="microseconds")
    event = Event(
        id=event_id,
        ts=ts,
        actor=actor,
        type=type,
        payload=payload,
        prev_hash=prev_hash,
        hash=event_hash(prev_hash, event_id, ts, actor, type, payload),
    )
    session.add(event)
    session.flush()
    return event


def decision_record_sha256(decision: Decision) -> str:
    return sha256_hex(
        canonical_json(
            {
                "id": decision.id,
                "scenario_sha256": decision.scenario_sha256,
                "engine": decision.engine,
                "status": decision.status,
                "requires_human_approval": decision.requires_human_approval,
                "coverage": decision.coverage,
                "assignments": decision.assignments,
                "unmet_requirements": decision.unmet_requirements,
                "verification": decision.verification,
                "drafts": decision.drafts,
                "constraints": decision.constraints,
                "travel_times": decision.travel_times,
                "proposer_sub": decision.proposer_sub,
            }
        )
    )


def approval_record_sha256(approval: Approval) -> str:
    return sha256_hex(
        canonical_json(
            {
                "id": approval.id,
                "decision_id": approval.decision_id,
                "user_id": approval.user_id,
                "approved": approval.approved,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class BrokenLink:
    event_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class ChainReport:
    ok: bool
    events_checked: int
    head_hash: str
    first_broken: BrokenLink | None

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "events_checked": self.events_checked,
            "head_hash": self.head_hash,
            "first_broken": None
            if self.first_broken is None
            else {"event_id": self.first_broken.event_id, "reason": self.first_broken.reason},
        }


def verify_chain(session: Session) -> ChainReport:
    """Walk the chain from genesis; report the first event whose link or record is broken."""
    expected_prev = GENESIS_HASH
    checked = 0
    for event in session.scalars(select(Event).order_by(Event.id)):
        checked += 1
        broken = _check_event(session, event, expected_prev)
        if broken is not None:
            return ChainReport(False, checked, expected_prev, BrokenLink(event.id, broken))
        expected_prev = event.hash
    return ChainReport(True, checked, expected_prev, None)


def _check_event(session: Session, event: Event, expected_prev: str) -> str | None:
    if event.prev_hash != expected_prev:
        return "prev_hash does not match the previous event's hash (edited or deleted event)"
    recomputed = event_hash(
        event.prev_hash, event.id, event.ts, event.actor, event.type, event.payload
    )
    if recomputed != event.hash:
        return "hash does not match the event's content (event edited)"
    payload = event.payload if isinstance(event.payload, dict) else {}
    record = payload.get("record")
    if isinstance(record, dict):
        return _check_record(session, record)
    return None


def _check_record(session: Session, record: dict[str, object]) -> str | None:
    table, row_id, expected = record.get("table"), record.get("id"), record.get("sha256")
    if not isinstance(row_id, int):
        return "event names a record without an integer id"
    if table == "decisions":
        decision = session.get(Decision, row_id)
        actual = decision_record_sha256(decision) if decision is not None else None
    elif table == "approvals":
        approval = session.get(Approval, row_id)
        actual = approval_record_sha256(approval) if approval is not None else None
    else:
        return f"event names an unknown table {table!r}"
    if actual is None:
        return f"{table} row {row_id} referenced by this event is missing"
    if actual != expected:
        return f"{table} row {row_id} differs from the content recorded in this event"
    return None


def record_ref(table: str, row_id: int, sha256: str) -> dict[str, object]:
    return {"table": table, "id": row_id, "sha256": sha256}
