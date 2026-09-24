"""User-study API: create a participant's session, time each task, export results as CSV.

A session holds twelve plans (one task set in each interface), each stored as an ordinary decision
proposed by ``study-proposer``, so the participant (an approver) may approve or reject them in
either interface through the normal disposition endpoint. See aegisops/study/tasks.py and
docs/USER_STUDY.md.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from aegisops.api.auth import Principal, require_operator, require_viewer
from aegisops.audit.event_log import append_event
from aegisops.domain.models import Scenario
from aegisops.infrastructure.decision_store import record_decision
from aegisops.planning.travel import TravelTimeProvider
from aegisops.study.results import TaskResult, score, to_csv
from aegisops.study.tasks import build_task, session_plan
from backend.db.models import Approval, Exercise, StudySession, StudyTask

PROPOSER = "study-proposer"


class NewSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant: Annotated[str, Field(pattern=r"^P\d{2,3}$")]


def _results(session: Session, study: StudySession) -> list[TaskResult]:
    tasks = session.scalars(
        select(StudyTask).where(StudyTask.session_id == study.id).order_by(StudyTask.order)
    )
    rows = []
    for task in tasks:
        first = session.scalars(
            select(Approval).where(Approval.decision_id == task.decision_id).order_by(Approval.id)
        ).first()
        rows.append(score(
            participant=study.participant, participant_number=study.participant_number,
            order=task.order, ui=task.ui, task=task.task_key, injected_error=task.injected_error,
            expected_action=task.expected_action, expected_reason=task.expected_reason,
            decision_id=task.decision_id, started_at=task.started_at,
            action=None if first is None else ("approve" if first.approved else "reject"),
            reason_code=None if first is None else first.reason_code,
            decided_at=None if first is None else first.commented_at,
        ))
    return rows


def _session_dict(session: Session, study: StudySession) -> dict[str, Any]:
    tasks = {t.order: t for t in session.scalars(
        select(StudyTask).where(StudyTask.session_id == study.id)
    )}
    return {
        "id": study.id,
        "participant": study.participant,
        "participant_number": study.participant_number,
        "tasks": [
            {"id": tasks[r.order].id, "order": r.order, "ui": r.ui, "task": r.task,
             "decision_id": r.decision_id, "started": r.started_at is not None,
             "decided": r.action is not None}
            for r in _results(session, study)
        ],
    }


def study_router(session_factory: sessionmaker[Session], travel: TravelTimeProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1/study", tags=["study"])

    @router.post("/sessions")
    def create_session(
        body: NewSession, principal: Annotated[Principal, Depends(require_operator)]
    ) -> dict[str, Any]:
        number = int(re.sub(r"\D", "", body.participant))
        with session_factory() as session:
            if session.scalars(select(StudySession).where(
                StudySession.participant == body.participant)).first():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail=f"{body.participant} already has a session.")
            exercise = session.scalars(
                select(Exercise).order_by(Exercise.created_at.desc()).limit(1)).first()
            if exercise is None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="Seed the exercise first.")
            base = Scenario.model_validate(exercise.scenario)
        built = [(planned, *build_task(base, planned.spec, travel))
                 for planned in session_plan(number)]
        with session_factory.begin() as session:
            study = StudySession(participant=body.participant, participant_number=number,
                                 created_at=datetime.now(UTC))
            session.add(study)
            session.flush()
            for planned, scenario, outcome in built:
                decision = record_decision(session, scenario, outcome, proposer=PROPOSER)
                session.add(StudyTask(
                    session_id=study.id, order=planned.order, ui=planned.ui,
                    task_key=planned.spec.key, injected_error=planned.spec.error,
                    expected_action=planned.spec.expected_action,
                    expected_reason=planned.spec.expected_reason, decision_id=decision.id,
                ))
            session.flush()
            append_event(session, actor=principal.sub, type="study_session_created",
                         payload={"session_id": study.id, "participant": body.participant})
            return _session_dict(session, study)

    @router.get("/sessions")
    def list_sessions(
        principal: Annotated[Principal, Depends(require_viewer)],
    ) -> list[dict[str, Any]]:
        del principal
        with session_factory() as session:
            return [_session_dict(session, s)
                    for s in session.scalars(select(StudySession).order_by(StudySession.id))]

    @router.get("/sessions/{session_id}")
    def get_session(
        session_id: int, principal: Annotated[Principal, Depends(require_viewer)]
    ) -> dict[str, Any]:
        del principal
        with session_factory() as session:
            study = session.get(StudySession, session_id)
            if study is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail="Session not found.")
            return _session_dict(session, study)

    @router.post("/tasks/{task_id}/start")
    def start_task(
        task_id: int, principal: Annotated[Principal, Depends(require_viewer)]
    ) -> dict[str, Any]:
        """Mark the moment the participant opens the plan; only the first call counts."""
        del principal
        with session_factory.begin() as session:
            task = session.get(StudyTask, task_id)
            if task is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail="Task not found.")
            if task.started_at is None:
                task.started_at = datetime.now(UTC)
            started = task.started_at
            return {"id": task.id, "started_at": (
                started if started.tzinfo else started.replace(tzinfo=UTC)).isoformat()}

    @router.get("/export.csv")
    def export(principal: Annotated[Principal, Depends(require_viewer)]) -> Response:
        del principal
        with session_factory() as session:
            rows = [row for study in session.scalars(select(StudySession).order_by(
                StudySession.id)) for row in _results(session, study)]
        return Response(to_csv(rows), media_type="text/csv", headers={
            "Content-Disposition": 'attachment; filename="user_study.csv"'})

    return router
