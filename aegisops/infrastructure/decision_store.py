"""Persist a decision result together with the scenario it was computed from."""

from __future__ import annotations

from sqlalchemy.orm import Session

from aegisops.domain.models import DecisionResult, Scenario
from backend.db.models import AuditLog, Decision


def record_decision(
    session: Session, scenario: Scenario, result: DecisionResult, actor: str
) -> Decision:
    """Store the full decision record and its creation audit entry; returns the flushed row."""
    decision = Decision(
        scenario_id=result.scenario_id,
        engine=result.engine,
        status=result.status.value,
        requires_human_approval=result.requires_human_approval,
        coverage=result.coverage,
        decision_trace=result.decision_trace,
        scenario=scenario.model_dump(mode="json"),
        scenario_sha256=scenario.sha256(),
        assignments=[item.model_dump(mode="json") for item in result.assignments],
        unmet_requirements=[item.model_dump(mode="json") for item in result.unmet_requirements],
        safety_findings=[item.model_dump(mode="json") for item in result.safety_findings],
        evidence=[item.model_dump(mode="json") for item in result.evidence],
        prompt_version=result.prompt_version,
        model_version=result.model_version,
    )
    session.add(decision)
    session.flush()
    session.add(
        AuditLog(
            user_id=None,
            action="decision_created",
            table_name="decisions",
            record_id=str(decision.id),
            change_data={"actor": actor, "scenario_id": result.scenario_id},
        )
    )
    return decision
