"""Clean, fully verified cases for fault injection: 50 seeded scenarios, one plan each.

Each case is a CP-SAT plan with valid citations and a matching SITREP. Scenarios are adjusted so
every mutator applies to every case: incident 0 is critical and covered, every demanded unit type
has at least one idle surplus unit, and one unavailable unit of every type exists.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from aegisops.application.scenario_service import generate_scenario
from aegisops.communication.sitrep import render_sitrep
from aegisops.domain.models import (
    Citation,
    DecisionResult,
    Evidence,
    Location,
    Resource,
    ResourceType,
    Scenario,
    Severity,
)
from aegisops.infrastructure.retrieval_engine import RetrievalEngine
from aegisops.planning.solver import SolverDecisionEngine, SolveResult, solve
from aegisops.planning.travel import StraightLineProvider, TravelTimeMatrix
from aegisops.verification.models import TextDraft, VerificationPolicy, VerificationReport
from aegisops.verification.verifier import verify

SEEDS = tuple(range(50))
KNOWLEDGE = Path(__file__).resolve().parents[2] / "knowledge"
REPORT_TEMPLATES = (
    "{people} people affected; caller reports {kind} near the market.",
    "Field team confirms {kind}; {people} residents need assistance.",
    "Neighbour called in a {kind} with about {people} people involved.",
)


@dataclass(frozen=True)
class FaultCase:
    seed: int
    scenario: Scenario
    travel_times: TravelTimeMatrix
    reference: SolveResult
    plan: DecisionResult
    evidence: tuple[Evidence, ...]
    drafts: tuple[TextDraft, ...]

    def with_plan(self, plan: DecisionResult) -> FaultCase:
        """Replace the plan and re-render the SITREP so it stays consistent with the plan."""
        return replace(
            self, plan=plan, drafts=(render_sitrep(plan, self.scenario, self.travel_times),)
        )

    def verify(self) -> VerificationReport:
        return verify(
            self.plan,
            self.scenario,
            reference_plan=self.reference,
            travel_times=self.travel_times,
            evidence=self.evidence,
            text_drafts=self.drafts,
            policy=VerificationPolicy(require_citations=True),
        )


def _adjusted_scenario(seed: int) -> Scenario:
    base = generate_scenario(seed=seed)
    rng = random.Random(f"fault-corpus:{seed}")
    incidents = [
        incident.model_copy(
            update={
                "severity": Severity.CRITICAL if index == 0 else incident.severity,
                "report": rng.choice(REPORT_TEMPLATES).format(
                    people=incident.people_affected, kind=incident.type.value.replace("_", " ")
                ),
            }
        )
        for index, incident in enumerate(base.incidents)
    ]
    demand: dict[ResourceType, int] = {}
    for incident in incidents:
        for resource_type, quantity in incident.resources_needed.items():
            demand[resource_type] = demand.get(resource_type, 0) + quantity
    resources = list(base.resources)
    for resource_type in ResourceType:
        supply = sum(r.type == resource_type for r in resources)
        missing = max(0, demand.get(resource_type, 0) + 1 - supply)
        for index in range(missing):
            unit_id = f"RES-surplus-{resource_type.value}-{index}"
            resources.append(_unit(unit_id, resource_type, rng))
        resources.append(
            _unit(f"RES-offline-{resource_type.value}", resource_type, rng, available=False)
        )
    return Scenario.model_validate(
        {
            "scenario_id": base.scenario_id,
            "incidents": [incident.model_dump(mode="json") for incident in incidents],
            "resources": [resource.model_dump(mode="json") for resource in resources],
        }
    )


def _unit(
    unit_id: str, resource_type: ResourceType, rng: random.Random, available: bool = True
) -> Resource:
    return Resource(
        id=unit_id.replace("_", "-"),
        type=resource_type,
        location=Location(
            lat=round(rng.uniform(26.78, 26.93), 5), lon=round(rng.uniform(80.87, 81.05), 5)
        ),
        available=available,
    )


def _first_sentence(evidence: Evidence) -> str:
    body = next(
        paragraph
        for paragraph in evidence.description.split("\n\n")
        if paragraph.strip() and not paragraph.lstrip().startswith("#")
    )
    return " ".join(body.split()).split(". ")[0]


@cache
def _retriever() -> RetrievalEngine:
    return RetrievalEngine(KNOWLEDGE)


@cache
def clean_case(seed: int) -> FaultCase:
    scenario = _adjusted_scenario(seed)
    matrix = StraightLineProvider().matrix(scenario)
    reference = solve(scenario, matrix)
    evidence = tuple(_retriever().retrieve_evidence("resource allocation capability"))
    cite = Citation(evidence_id=evidence[0].id, quote=_first_sentence(evidence[0]))
    plan = SolverDecisionEngine().result_from_solve(scenario, reference)
    plan = plan.model_copy(
        update={
            "assignments": [
                assignment.model_copy(update={"citations": [cite]})
                for assignment in plan.assignments
            ],
            "evidence": list(evidence),
        }
    )
    return FaultCase(
        seed=seed,
        scenario=scenario,
        travel_times=matrix,
        reference=reference,
        plan=plan,
        evidence=evidence,
        drafts=(render_sitrep(plan, scenario, matrix),),
    )
