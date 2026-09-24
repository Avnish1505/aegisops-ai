"""Seed the triage queue with the fictional demo reports (backend/demo_reports.json).

Readings come from backend/demo_reads.json, written once by ``scripts/record_demo_reads.py`` with a
real model and stored with its model name and prompt version, so the public demo never calls a
model. Reports with no recorded reading are stored unread and say so.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aegisops.audit.event_log import append_event
from aegisops.domain.canonical import sha256_hex
from aegisops.intake.models import IncidentCandidate
from aegisops.intake.triage import review_reasons
from backend.db.models import IntakeReport

REPORTS = Path(__file__).with_name("demo_reports.json")
READS = Path(__file__).with_name("demo_reads.json")
ACTOR = "demo-seed"


def load_reads(path: Path = READS) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8"))["reads"])


def seed_demo_intake(
    session: Session,
    *,
    now: datetime | None = None,
    reports: list[str] | None = None,
    reads: dict[str, dict[str, Any]] | None = None,
) -> int:
    """Insert the demo reports if the queue is empty; returns how many were added."""
    if session.scalar(select(func.count(IntakeReport.id))):
        return 0
    texts = reports if reports is not None else json.loads(REPORTS.read_text("utf-8"))["reports"]
    recorded = reads if reads is not None else load_reads()
    moment = now or datetime.now(UTC)
    for index, text in enumerate(texts):
        read = recorded.get(sha256_hex(text))
        candidate = IncidentCandidate.model_validate(read["candidate"]) if read else None
        reasons = review_reasons(text, candidate)
        report = IntakeReport(
            received_at=moment - timedelta(minutes=3 * (len(texts) - index)),
            text=text,
            source="demo_seed",
            status="unread" if candidate is None else ("needs_review" if reasons else "ready"),
            candidate=candidate.model_dump(mode="json") if candidate else None,
            read_meta=read["read_meta"] if read else None,
            review_reasons=reasons,
        )
        session.add(report)
        session.flush()
        append_event(session, actor=ACTOR, type="intake_read" if read else "intake_received",
                     payload={"intake_id": report.id, "text_sha256": sha256_hex(text),
                              "recorded_read": bool(read), "status": report.status})
    return len(texts)
