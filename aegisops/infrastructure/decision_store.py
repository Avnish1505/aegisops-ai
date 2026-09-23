"""Persist a verified decision with everything needed to replay and audit it."""

from __future__ import annotations

from sqlalchemy.orm import Session

from aegisops.application.decision_service import DecisionOutcome
from aegisops.audit.event_log import append_event, decision_record_sha256, record_ref
from aegisops.domain.canonical import canonical_json, sha256_hex
from aegisops.domain.models import Scenario
from aegisops.planning.objective import plan_objective
from backend.db.models import Decision


def record_decision(
    session: Session, scenario: Scenario, outcome: DecisionOutcome, proposer: str
) -> Decision:
    """Store the full decision record and append its creation and verification events."""
    result = outcome.result
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
        proposer_sub=proposer,
        verification=outcome.verification.model_dump(mode="json"),
        drafts=[draft.model_dump(mode="json") for draft in outcome.drafts],
        constraints=[item.model_dump(mode="json") for item in outcome.constraints],
        travel_times=outcome.travel_times.model_dump(mode="json"),
        objective=plan_objective(
            result.assignments,
            result.unmet_requirements,
            scenario,
            outcome.travel_times,
            outcome.constraints,
        ).total,
        reference_objective=outcome.reference.objective,
        solve_status=outcome.reference.status.value,
        infeasibility=(
            outcome.reference.infeasibility.model_dump(mode="json")
            if outcome.reference.infeasibility is not None
            else None
        ),
    )
    session.add(decision)
    session.flush()
    append_event(
        session,
        actor=proposer,
        type="decision_created",
        payload={
            "decision_id": decision.id,
            "scenario_sha256": decision.scenario_sha256,
            "engine": decision.engine,
            "status": decision.status,
            "record": record_ref("decisions", decision.id, decision_record_sha256(decision)),
        },
    )
    report = outcome.verification
    append_event(
        session,
        actor="verifier",
        type="verification_completed",
        payload={
            "decision_id": decision.id,
            "verdict": report.verdict.value,
            "blocking_check_ids": report.blocking_check_ids,
            "failed_check_ids": [check.id for check in report.failed()],
            "safety_gate_blocked": report.safety_gate_blocked,
            "report_sha256": sha256_hex(canonical_json(report.model_dump(mode="json"))),
        },
    )
    return decision


def serialize_decision(decision: Decision) -> dict[str, object]:
    """The single API shape for a stored decision (POST response and GET)."""
    travel = decision.travel_times or {}
    return {
        "decision_id": decision.id,
        "scenario_id": decision.scenario_id,
        "scenario_sha256": decision.scenario_sha256,
        "scenario": decision.scenario,
        "engine": decision.engine,
        "status": decision.status,
        "requires_human_approval": decision.requires_human_approval,
        "coverage": decision.coverage,
        "assignments": decision.assignments,
        "unmet_requirements": decision.unmet_requirements,
        "safety_findings": decision.safety_findings,
        "evidence": decision.evidence,
        "decision_trace": decision.decision_trace,
        "prompt_version": decision.prompt_version,
        "model_version": decision.model_version,
        "proposer_sub": decision.proposer_sub,
        "verification": decision.verification,
        "drafts": decision.drafts,
        "constraints": decision.constraints,
        "objective": decision.objective,
        "reference_objective": decision.reference_objective,
        "solve_status": decision.solve_status,
        "infeasibility": decision.infeasibility,
        "travel_times": decision.travel_times,
        "travel_provider": travel.get("provider"),
        "travel_degraded": travel.get("degraded"),
        "created_at": decision.created_at.isoformat(),
        "approvals": [
            {
                "disposition_id": approval.id,
                "action": "approve" if approval.approved else "reject",
                "actor": approval.user.username,
                "timestamp": approval.commented_at.isoformat(),
            }
            for approval in decision.approvals
        ],
    }
