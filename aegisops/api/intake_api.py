"""Intake: store field reports, read them with the model, and let an operator confirm the facts.

Reading never plans anything. A report becomes an exercise incident only when an operator confirms
its fields (``/confirm``); severity is then recomputed from those fields by the deterministic rules.
Every step appends a hash-chained audit event.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from aegisops.api.auth import Principal, require_operator, require_viewer
from aegisops.audit.event_log import append_event
from aegisops.domain.canonical import sha256_hex
from aegisops.domain.models import Scenario
from aegisops.intake.models import IncidentCandidate
from aegisops.intake.reader import Reader, ReadResult, to_incident
from aegisops.intake.triage import (
    ConfirmedFields,
    ReportView,
    confirmed_severity,
    duplicate_of,
    edited_fields,
    fields_from_candidate,
    incident_from_fields,
    review_reasons,
)
from aegisops.llm.client import LLMError, LLMOutputError
from aegisops.telemetry import current_traceparent, step_span
from backend.db.models import Exercise, IntakeReport

OPEN_STATUSES = ("unread", "needs_review", "ready")


class ReportText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report: Annotated[str, Field(min_length=1, max_length=4_000)]


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: ConfirmedFields
    add_to_exercise: bool = True


class DismissRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=1, max_length=500)]


class MergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    into: int


def _view(report: IntakeReport) -> ReportView:
    candidate: dict[str, Any] = dict(report.candidate or {})
    geocode: dict[str, Any] = dict(candidate.get("geocode") or {})
    fields: dict[str, Any] = dict(report.confirmed_fields or {})
    place: dict[str, Any] = dict(fields.get("place") or {})
    kind = dict(candidate.get("incident_type") or {}).get("value")
    received = report.received_at
    return ReportView(
        id=report.id,
        text=report.text,
        received_at=received if received.tzinfo else received.replace(tzinfo=UTC),
        incident_type=fields.get("incident_type") or kind,
        lat=place.get("lat", geocode.get("lat")),
        lon=place.get("lon", geocode.get("lon")),
    )


def report_dict(report: IntakeReport, others: list[IntakeReport] | None = None) -> dict[str, Any]:
    candidate = IncidentCandidate.model_validate(report.candidate) if report.candidate else None
    suggested = fields_from_candidate(candidate) if candidate else None
    duplicates = (
        duplicate_of(_view(report), [_view(o) for o in others if o.status in OPEN_STATUSES])
        if others is not None and report.status in OPEN_STATUSES
        else []
    )
    return {
        "id": report.id,
        "received_at": _view(report).received_at.isoformat(),
        "text": report.text,
        "source": report.source,
        "status": report.status,
        "candidate": report.candidate,
        "read_meta": report.read_meta,
        "review_reasons": report.review_reasons,
        "suggested_fields": suggested.model_dump(mode="json") if suggested else None,
        "confirmed_fields": report.confirmed_fields,
        "edited_fields": report.edited_fields,
        "reviewed_by": report.reviewed_by,
        "merged_into": report.merged_into,
        "incident_id": report.incident_id,
        "exercise_id": report.exercise_id,
        "duplicates": duplicates,
    }


def _apply_reading(report: IntakeReport, result: ReadResult) -> None:
    report.candidate = result.candidate.model_dump(mode="json")
    report.read_meta = {
        "model": result.record.model,
        "prompt_version": result.record.prompt_version,
        "input_tokens": result.record.input_tokens,
        "output_tokens": result.record.output_tokens,
        "latency_s": round(result.record.latency_s, 3),
        "cost_usd": result.record.cost_usd,
    }
    report.review_reasons = review_reasons(report.text, result.candidate)
    report.status = "needs_review" if report.review_reasons else "ready"


def intake_router(
    session_factory: sessionmaker[Session],
    reader: Reader,
    require_llm: Callable[[], None],
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/intake", tags=["intake"])

    def _get(session: Session, report_id: int) -> IntakeReport:
        report = session.get(IntakeReport, report_id)
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
        return report

    def _read(text: str) -> ReadResult:
        require_llm()
        try:
            return reader.read(text)
        except (LLMError, LLMOutputError) as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Reader failed: {error}"
            ) from error

    @router.post("")
    def receive(
        body: ReportText, principal: Annotated[Principal, Depends(require_operator)]
    ) -> dict[str, Any]:
        """Store a report without reading it (reading needs a model; see /{id}/read)."""
        with session_factory.begin() as session:
            report = IntakeReport(
                received_at=datetime.now(UTC), text=body.report, source="operator",
                status="unread", review_reasons=review_reasons(body.report, None),
            )
            session.add(report)
            session.flush()
            append_event(session, actor=principal.sub, type="intake_received", payload={
                "intake_id": report.id, "text_sha256": sha256_hex(body.report)})
            return report_dict(report)

    @router.post("/read")
    def read_report(
        body: ReportText,
        response: Response,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, object]:
        """Free-text report -> grounded incident candidate, stored for triage (nothing planned)."""
        with step_span("read") as span:
            result = _read(body.report)
            span.set_attribute("aegisops.fields_dropped", len(result.candidate.dropped))
            traceparent = current_traceparent()
        with session_factory.begin() as session:
            report = IntakeReport(received_at=datetime.now(UTC), text=body.report,
                                  source="operator", status="unread", review_reasons=[])
            _apply_reading(report, result)
            session.add(report)
            session.flush()
            append_event(session, actor=principal.sub, type="intake_read", payload={
                "intake_id": report.id, "text_sha256": sha256_hex(body.report),
                "model": result.record.model, "prompt_version": result.record.prompt_version,
                "dropped": result.candidate.dropped, "status": report.status})
            intake_id = report.id
        incident = to_incident(result.candidate, "INC-preview")
        if traceparent:
            response.headers["traceparent"] = traceparent
        return {
            "intake_id": intake_id,
            "traceparent": traceparent,
            "candidate": result.candidate.model_dump(mode="json"),
            "incident_preview": incident.model_dump(mode="json") if incident else None,
            "llm": {
                "model": result.record.model,
                "prompt_version": result.record.prompt_version,
                "input_tokens": result.record.input_tokens,
                "output_tokens": result.record.output_tokens,
                "latency_s": round(result.record.latency_s, 3),
                "cost_usd": result.record.cost_usd,
            },
        }

    @router.post("/{report_id}/read")
    def read_stored(
        report_id: int, principal: Annotated[Principal, Depends(require_operator)]
    ) -> dict[str, Any]:
        with session_factory() as session:
            text = _get(session, report_id).text
        with step_span("read", intake_id=report_id):
            result = _read(text)
        with session_factory.begin() as session:
            report = _get(session, report_id)
            if report.status not in OPEN_STATUSES:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Report is already {report.status}.")
            _apply_reading(report, result)
            append_event(session, actor=principal.sub, type="intake_read", payload={
                "intake_id": report.id, "text_sha256": sha256_hex(report.text),
                "model": result.record.model, "prompt_version": result.record.prompt_version,
                "dropped": result.candidate.dropped, "status": report.status})
            return report_dict(report)

    @router.get("")
    def list_reports(
        principal: Annotated[Principal, Depends(require_viewer)],
        open_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Open reports first needing review, then ready, then unread; newest first within each."""
        del principal
        with session_factory() as session:
            query = select(IntakeReport).order_by(IntakeReport.received_at.desc())
            reports = list(session.scalars(query))
            shown = [r for r in reports if r.status in OPEN_STATUSES] if open_only else reports
            order = {"needs_review": 0, "ready": 1, "unread": 2}
            shown.sort(key=lambda r: order.get(r.status, 3))
            return [report_dict(r, reports) for r in shown]

    @router.get("/{report_id}")
    def get_report(
        report_id: int, principal: Annotated[Principal, Depends(require_viewer)]
    ) -> dict[str, Any]:
        del principal
        with session_factory() as session:
            others = list(session.scalars(select(IntakeReport)))
            return report_dict(_get(session, report_id), others)

    @router.post("/{report_id}/confirm")
    def confirm(
        report_id: int,
        body: ConfirmRequest,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, Any]:
        with session_factory.begin() as session:
            report = _get(session, report_id)
            if report.status not in OPEN_STATUSES:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Report is already {report.status}.")
            candidate = (IncidentCandidate.model_validate(report.candidate)
                         if report.candidate else None)
            edits = edited_fields(candidate, body.fields)
            severity, rule = confirmed_severity(body.fields)
            report.confirmed_fields = body.fields.model_dump(mode="json")
            report.edited_fields = edits
            report.status = "confirmed"
            report.reviewed_by = principal.sub
            report.reviewed_at = datetime.now(UTC)
            exercise_payload: dict[str, object] = {}
            if body.add_to_exercise:
                exercise = session.scalars(
                    select(Exercise).order_by(Exercise.created_at.desc()).limit(1)
                ).first()
                if exercise is None:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                        detail="No exercise to add the incident to.")
                scenario = Scenario.model_validate(exercise.scenario)
                seeded = (exercise.created_at.replace(tzinfo=UTC)
                          if exercise.created_at.tzinfo is None else exercise.created_at)
                latest = max((i.reported_at_min for i in scenario.incidents), default=0)
                since = max(0, int((datetime.now(UTC) - seeded).total_seconds() // 60))
                incident = incident_from_fields(
                    body.fields, f"INC-TRI-{report.id}", report.text, latest + since
                )
                updated = scenario.model_copy(update={"incidents": [*scenario.incidents, incident]})
                exercise.scenario = updated.model_dump(mode="json")
                exercise.scenario_sha256 = updated.sha256()
                report.incident_id = incident.id
                report.exercise_id = exercise.id
                exercise_payload = {"exercise_id": exercise.id, "incident_id": incident.id,
                                    "scenario_sha256": exercise.scenario_sha256}
            append_event(session, actor=principal.sub, type="intake_confirmed", payload={
                "intake_id": report.id, "edited_fields": edits, "severity": severity,
                "severity_rule": rule, **exercise_payload})
            return report_dict(report)

    @router.post("/{report_id}/dismiss")
    def dismiss(
        report_id: int,
        body: DismissRequest,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, Any]:
        with session_factory.begin() as session:
            report = _get(session, report_id)
            if report.status not in OPEN_STATUSES:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Report is already {report.status}.")
            report.status = "dismissed"
            report.reviewed_by = principal.sub
            report.reviewed_at = datetime.now(UTC)
            append_event(session, actor=principal.sub, type="intake_dismissed",
                         payload={"intake_id": report.id, "reason": body.reason})
            return report_dict(report)

    @router.post("/{report_id}/merge")
    def merge(
        report_id: int,
        body: MergeRequest,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, Any]:
        """Mark this report as a duplicate of another; the other one carries the incident."""
        if body.into == report_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail="A report cannot be merged into itself.")
        with session_factory.begin() as session:
            report, target = _get(session, report_id), _get(session, body.into)
            if report.status not in OPEN_STATUSES:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Report is already {report.status}.")
            if target.status in ("merged", "dismissed"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"Report {target.id} is {target.status}.")
            report.status = "merged"
            report.merged_into = target.id
            report.reviewed_by = principal.sub
            report.reviewed_at = datetime.now(UTC)
            append_event(session, actor=principal.sub, type="intake_merged",
                         payload={"intake_id": report.id, "into": target.id})
            return report_dict(report)

    return router
