"""The one path from a scenario to an operator-facing decision.

engine proposal -> CP-SAT reference -> SITREP draft -> verify -> verdict.

Whatever engine proposes, the operator only ever sees a plan that has been through ``verify``,
the status is the verifier's verdict, and ``requires_human_approval`` is always true on the way
out (a proposal that tried to drop it is recorded as a failed check, not obeyed).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from aegisops.application.ports import DecisionEngine
from aegisops.communication.sitrep import render_sitrep
from aegisops.domain.models import DecisionResult, DecisionStatus, SafetyFinding, Scenario
from aegisops.domain.policy import evaluate_safety_gates
from aegisops.planning.constraints import PlanningConstraint
from aegisops.planning.objective import plan_coverage
from aegisops.planning.solver import SolverDecisionEngine, SolveResult, solve
from aegisops.planning.travel import TravelTimeMatrix, TravelTimeProvider
from aegisops.telemetry import tool_span
from aegisops.verification.models import (
    TextDraft,
    Verdict,
    VerificationPolicy,
    VerificationReport,
)
from aegisops.verification.verifier import verify

SOLVER_ENGINE = "solver"
# Engines that read retrieved evidence must cite it for every assignment.
CITING_ENGINES = frozenset({"llm_rag"})


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    result: DecisionResult
    verification: VerificationReport
    reference: SolveResult
    travel_times: TravelTimeMatrix
    drafts: tuple[TextDraft, ...]
    constraints: tuple[PlanningConstraint, ...]


class DecisionService:
    def __init__(
        self,
        engines: Mapping[str, DecisionEngine],
        travel_provider: TravelTimeProvider,
        *,
        solver_time_limit_s: float = 10.0,
    ) -> None:
        self._engines = dict(engines)
        self._travel_provider = travel_provider
        self._solver = SolverDecisionEngine(travel_provider, time_limit_s=solver_time_limit_s)
        self._time_limit_s = solver_time_limit_s

    @property
    def engine_names(self) -> tuple[str, ...]:
        return (SOLVER_ENGINE, *self._engines)

    def decide(
        self,
        scenario: Scenario,
        engine: str = SOLVER_ENGINE,
        constraints: Sequence[PlanningConstraint] = (),
    ) -> DecisionOutcome:
        if engine != SOLVER_ENGINE and engine not in self._engines:
            raise ValueError(f"Unknown engine: {engine}")
        constraint_tuple = tuple(constraints)
        with tool_span("travel_matrix") as span:
            travel_times = self._travel_provider.matrix(scenario)
            span.set_attributes({"aegisops.travel.provider": travel_times.provider,
                                 "aegisops.travel.degraded": travel_times.degraded})
        with tool_span("cp_sat_solve", constraints=len(constraint_tuple)) as span:
            reference = solve(
                scenario, travel_times, constraint_tuple, time_limit_s=self._time_limit_s
            )
            span.set_attribute("aegisops.solve.status", reference.status.value)
        with tool_span("propose", engine=engine):
            proposal = (
                self._solver.result_from_solve(scenario, reference)
                if engine == SOLVER_ENGINE
                else self._engines[engine].recommend(scenario, travel_times, constraint_tuple)
            )
        drafts = (render_sitrep(proposal, scenario, travel_times),)
        with tool_span("verify") as span:
            report = verify(
                proposal,
                scenario,
                reference_plan=reference,
                travel_times=travel_times,
                constraints=constraint_tuple,
                evidence=proposal.evidence,
                text_drafts=drafts,
                policy=VerificationPolicy(require_citations=engine in CITING_ENGINES),
            )
            span.set_attributes({"aegisops.verify.verdict": report.verdict.value,
                                 "aegisops.verify.blocking": list(report.blocking_check_ids)})
        findings, _ = evaluate_safety_gates(
            [
                item
                for item in proposal.unmet_requirements
                if item.incident_id in {incident.id for incident in scenario.incidents}
            ],
            scenario,
        )
        result = proposal.model_copy(
            update={
                # An engine may block itself (e.g. the NIM was unreachable); verification can
                # only make a decision stricter, never unblock it.
                "status": (
                    DecisionStatus.BLOCKED
                    if report.verdict == Verdict.BLOCKED
                    or proposal.status == DecisionStatus.BLOCKED
                    else DecisionStatus.REQUIRES_HUMAN_APPROVAL
                ),
                "requires_human_approval": True,
                "coverage": plan_coverage(proposal.assignments, scenario),
                "safety_findings": [*_engine_findings(proposal), *findings],
                "decision_trace": [
                    *proposal.decision_trace,
                    f"Verified against {travel_times.provider} travel times: "
                    f"{report.verdict.value}"
                    + (
                        f" ({', '.join(report.blocking_check_ids)})"
                        if report.blocking_check_ids
                        else ""
                    )
                    + ".",
                ],
            }
        )
        return DecisionOutcome(
            result=result,
            verification=report,
            reference=reference,
            travel_times=travel_times,
            drafts=drafts,
            constraints=constraint_tuple,
        )


def _engine_findings(proposal: DecisionResult) -> list[SafetyFinding]:
    """Keep engine-level operational findings (e.g. the NIM being unavailable)."""
    gate_codes = {
        "CRITICAL_UNMET_REQUIREMENT",
        "HIGH_PRIORITY_UNMET_REQUIREMENT",
        "HUMAN_APPROVAL_REQUIRED",
    }
    return [finding for finding in proposal.safety_findings if finding.code not in gate_codes]
