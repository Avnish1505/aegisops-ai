"""Read endpoints and the live stream behind the operations console.

The stream is Server-Sent Events. Browsers' ``EventSource`` cannot send an Authorization header,
so a signed-in client first exchanges its bearer token for a single-use ticket that is valid for
30 seconds (``POST /api/v1/stream/ticket``) and opens ``GET /api/v1/stream?ticket=...``. The
stream polls the database for new audit events, alerts and feed polls, so it sees writes from
the API and from the separate feed worker without a message broker. Tickets live in this
process's memory: run one API process, or put a shared store behind ``TicketBook``.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from aegisops.api.auth import Principal, require_viewer
from aegisops.core.config import Settings
from aegisops.domain.models import Scenario
from aegisops.geodata.labels import Labeller
from aegisops.llm.client import LLMClient
from backend.db.models import Alert, Approval, Decision, Event, Exercise, Facility, FeedPoll

FEEDS = ("sachet", "usgs", "gdacs")
STALE_AFTER_INTERVALS = 3
TICKET_TTL_S = 30.0
EVENT_SCAN_LIMIT = 2_000
SSE_EVENT_NAMES = {
    "decision_created": "decision.created",
    "verification_completed": "decision.verified",
    "disposition_recorded": "disposition.recorded",
    "drafts_generated": "drafts.generated",
}


class TicketBook:
    """Single-use, short-lived stream tickets bound to a token subject."""

    def __init__(self, ttl_s: float = TICKET_TTL_S, clock: Callable[[], float] = time.monotonic):
        self._ttl_s = ttl_s
        self._clock = clock
        self._tickets: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def issue(self, sub: str) -> str:
        ticket = secrets.token_urlsafe(24)
        with self._lock:
            now = self._clock()
            self._tickets = {k: v for k, v in self._tickets.items() if v[1] > now}
            self._tickets[ticket] = (sub, now + self._ttl_s)
        return ticket

    def redeem(self, ticket: str) -> str | None:
        with self._lock:
            entry = self._tickets.pop(ticket, None)
        if entry is None or entry[1] <= self._clock():
            return None
        return entry[0]


# --- Status -----------------------------------------------------------------------------------
def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    aware = _aware(value)
    return aware.isoformat() if aware is not None else None


def feed_health(session: Session, settings: Settings, now: datetime) -> list[dict[str, Any]]:
    """ok, stale (no successful poll for 3 intervals), failing (last poll failed) or no_data."""
    intervals = {
        "sachet": settings.ingest_sachet_interval_min,
        "usgs": settings.ingest_usgs_interval_min,
        "gdacs": settings.ingest_gdacs_interval_min,
    }
    feeds = []
    for source in FEEDS:
        last = session.scalars(
            select(FeedPoll).where(FeedPoll.source == source)
            .order_by(FeedPoll.polled_at.desc()).limit(1)
        ).first()
        last_ok = _aware(session.scalar(
            select(func.max(FeedPoll.polled_at)).where(FeedPoll.source == source, FeedPoll.ok)
        ))
        if last_ok is None:
            # Older databases have alerts but no poll records; fall back to the alert timestamps.
            last_ok = _aware(session.scalar(
                select(func.max(Alert.fetched_at)).where(Alert.source == source)
            ))
        if last is None and last_ok is None:
            state = "no_data"
        elif last is not None and not last.ok:
            state = "failing"
        elif last_ok is not None and now - last_ok > timedelta(
            minutes=intervals[source] * STALE_AFTER_INTERVALS
        ):
            state = "stale"
        else:
            state = "ok"
        feeds.append({
            "source": source,
            "state": state,
            "last_ok_at": _iso(last_ok),
            "last_poll_at": _iso(last.polled_at) if last else None,
            "last_error": last.error if last and not last.ok else None,
            "interval_min": intervals[source],
        })
    return feeds


def pending_approvals(session: Session) -> int:
    decided = select(Approval.decision_id)
    return session.scalar(
        select(func.count(Decision.id)).where(
            Decision.status == "requires_human_approval", Decision.id.not_in(decided)
        )
    ) or 0


def decision_summary(decision: Decision) -> dict[str, Any]:
    verification = decision.verification or {}
    last = decision.approvals[-1] if decision.approvals else None
    return {
        "decision_id": decision.id,
        "scenario_id": decision.scenario_id,
        "engine": decision.engine,
        "status": decision.status,
        "coverage": decision.coverage,
        "proposer_sub": decision.proposer_sub,
        "created_at": _iso(decision.created_at),
        "blocking_check_ids": verification.get("blocking_check_ids", []),
        "disposition": None if last is None else {
            "action": "approve" if last.approved else "reject",
            "actor": last.user.username,
            "timestamp": _iso(last.commented_at),
        },
    }


def event_dict(event: Event) -> dict[str, Any]:
    return {
        "id": event.id, "ts": event.ts, "actor": event.actor, "type": event.type,
        "payload": event.payload, "prev_hash": event.prev_hash, "hash": event.hash,
    }


# --- Stream -----------------------------------------------------------------------------------
Message = tuple[str, str, dict[str, Any]]  # (sse id, sse event name, data)


@dataclass
class Cursor:
    event_id: int
    alert_id: int
    poll_id: int


def current_cursor(session: Session) -> Cursor:
    return Cursor(
        event_id=session.scalar(select(func.max(Event.id))) or 0,
        alert_id=session.scalar(select(func.max(Alert.id))) or 0,
        poll_id=session.scalar(select(func.max(FeedPoll.id))) or 0,
    )


def new_messages(session: Session, cursor: Cursor, limit: int = 200) -> list[Message]:
    """Everything after the cursor, oldest first; advances the cursor."""
    messages: list[Message] = []
    for event in session.scalars(
        select(Event).where(Event.id > cursor.event_id).order_by(Event.id).limit(limit)
    ):
        cursor.event_id = event.id
        messages.append((f"e{event.id}", SSE_EVENT_NAMES.get(event.type, f"audit.{event.type}"),
                         event_dict(event)))
    for alert in session.scalars(
        select(Alert).where(Alert.id > cursor.alert_id).order_by(Alert.id).limit(limit)
    ):
        cursor.alert_id = alert.id
        messages.append((f"a{alert.id}", "alert.ingested", {
            "id": alert.id, "source": alert.source, "event": alert.event,
            "severity": alert.severity, "headline": alert.headline,
        }))
    for poll in session.scalars(
        select(FeedPoll).where(FeedPoll.id > cursor.poll_id).order_by(FeedPoll.id).limit(limit)
    ):
        cursor.poll_id = poll.id
        messages.append((f"p{poll.id}", "feed.health", {
            "source": poll.source, "ok": poll.ok, "polled_at": _iso(poll.polled_at),
            "error": poll.error,
        }))
    return messages


def sse_frame(event_id: str, name: str, data: dict[str, Any]) -> str:
    return f"id: {event_id}\nevent: {name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def stream_messages(
    session_factory: sessionmaker[Session],
    is_disconnected: Callable[[], Awaitable[bool]],
    *,
    poll_s: float = 1.0,
    heartbeat_s: float = 15.0,
) -> AsyncIterator[str]:
    def snapshot() -> Cursor:
        with session_factory() as session:
            return current_cursor(session)

    def fetch(cursor: Cursor) -> list[Message]:
        with session_factory() as session:
            return new_messages(session, cursor)

    cursor = await asyncio.to_thread(snapshot)
    yield sse_frame("ready", "ready", {"retry_ms": 3000})
    last_sent = time.monotonic()
    while not await is_disconnected():
        messages = await asyncio.to_thread(fetch, cursor)
        for message in messages:
            yield sse_frame(*message)
            last_sent = time.monotonic()
        if time.monotonic() - last_sent >= heartbeat_s:
            yield ": keepalive\n\n"
            last_sent = time.monotonic()
        await asyncio.sleep(poll_s)


# --- Router -----------------------------------------------------------------------------------
def console_router(
    session_factory: sessionmaker[Session],
    settings: Settings,
    llm: LLMClient,
    tickets: TicketBook,
    labeller: Labeller,
    *,
    stream_poll_s: float = 1.0,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.post("/labels", tags=["console"])
    def labels(
        scenario: Scenario, principal: Annotated[Principal, Depends(require_viewer)]
    ) -> dict[str, dict[str, str | None]]:
        """Display names: nearest OSM place for incidents, OSM facility name for units."""
        del principal
        with session_factory() as session:
            names = {
                (osm_type, osm_id): name
                for osm_type, osm_id, name in session.execute(
                    select(Facility.osm_type, Facility.osm_id, Facility.name)
                )
                if name
            }
        return labeller.labels(scenario, names)

    @router.get("/status", tags=["console"])
    def get_status(principal: Annotated[Principal, Depends(require_viewer)]) -> dict[str, Any]:
        del principal
        now = datetime.now(UTC)
        with session_factory() as session:
            exercise = session.scalars(
                select(Exercise).order_by(Exercise.created_at.desc()).limit(1)
            ).first()
            return {
                "server_time": now.isoformat(),
                "feeds": feed_health(session, settings, now),
                "model": {"configured": llm.available, "model": llm.model,
                          "provider": llm.provider},
                "pending_approvals": pending_approvals(session),
                "exercise": None if exercise is None else {
                    "id": exercise.id, "name": exercise.name,
                    "started_at": _iso(exercise.created_at),
                },
            }

    @router.get("/decisions", tags=["decisions"])
    def list_decisions(
        principal: Annotated[Principal, Depends(require_viewer)],
        status_filter: Annotated[str | None, Query(alias="status")] = None,
        scenario_id: str | None = None,
        pending: bool = False,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[dict[str, Any]]:
        del principal
        with session_factory() as session:
            query = select(Decision).order_by(Decision.id.desc()).limit(limit)
            if status_filter:
                query = query.where(Decision.status == status_filter)
            if scenario_id:
                query = query.where(Decision.scenario_id == scenario_id)
            if pending:
                query = query.where(
                    Decision.status == "requires_human_approval",
                    Decision.id.not_in(select(Approval.decision_id)),
                )
            return [decision_summary(d) for d in session.scalars(query)]

    @router.get("/events", tags=["audit"])
    def list_events(
        principal: Annotated[Principal, Depends(require_viewer)],
        decision_id: int | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[dict[str, Any]]:
        """Newest first. With ``decision_id``, the newest 2,000 events are searched."""
        del principal
        with session_factory() as session:
            scan = EVENT_SCAN_LIMIT if decision_id is not None else limit
            events = session.scalars(select(Event).order_by(Event.id.desc()).limit(scan))
            rows = [
                event_dict(e) for e in events
                if decision_id is None or e.payload.get("decision_id") == decision_id
            ]
            return rows[:limit]

    @router.post("/stream/ticket", tags=["console"])
    def stream_ticket(principal: Annotated[Principal, Depends(require_viewer)]) -> dict[str, Any]:
        return {"ticket": tickets.issue(principal.sub), "expires_in": TICKET_TTL_S}

    @router.get("/stream", tags=["console"])
    async def stream(request: Request, ticket: str) -> StreamingResponse:
        if tickets.redeem(ticket) is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Stream ticket is invalid, used or expired.")
        return StreamingResponse(
            stream_messages(session_factory, request.is_disconnected, poll_s=stream_poll_s),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
