"""User-study tasks: small Lucknow exercise plans, some with one injected error.

Two parallel sets of six tasks (A and B). Each set has three error-free plans (right answer:
approve) and three plans with one injected error (right answer: reject, naming the error):

- ``wrong_eta``: one assignment claims a travel time well below the road time.
- ``phantom_unit``: one assignment names a unit that does not exist in the scenario.
- ``sitrep_mismatch``: one ETA written in the SITREP differs from the plan.

Every plan, injected or not, is verified exactly as in production, so the verifier's findings
are on screen in both user interfaces; the study measures whether a reviewer reaches the right
decision, names the error, and how long it takes. A participant does one set in each interface;
``session_plan`` counterbalances interface order and set assignment by participant number.
"""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from aegisops.application.decision_service import DecisionOutcome, DecisionService
from aegisops.domain.models import Assignment, DecisionResult, DecisionStatus, Scenario
from aegisops.planning.constraints import PlanningConstraint
from aegisops.planning.travel import TravelTimeMatrix, TravelTimeProvider
from aegisops.verification.models import TextDraft, Verdict, VerificationPolicy
from aegisops.verification.verifier import verify

ErrorKind = Literal["wrong_eta", "phantom_unit", "sitrep_mismatch"]
UI = Literal["legacy", "console"]
EXPECTED_REASON: dict[ErrorKind, str] = {
    "wrong_eta": "eta_incorrect",
    "phantom_unit": "unit_unavailable_or_unknown",
    "sitrep_mismatch": "sitrep_numbers_wrong",
}
# Position of the injected error (or None) for each of the six tasks in a set.
SETS: dict[str, list[ErrorKind | None]] = {
    "A": [None, "wrong_eta", None, "phantom_unit", "sitrep_mismatch", None],
    "B": ["phantom_unit", None, "sitrep_mismatch", None, None, "wrong_eta"],
}
SEED = 20260924
INCIDENTS_PER_TASK = 5
UNITS_PER_TASK = 16
PHANTOM_UNIT_ID = "RES-BOAT-n9990001-1"
MAX_ATTEMPTS = 200


@dataclass(frozen=True, slots=True)
class TaskSpec:
    set_name: str
    position: int  # 1..6 within the set
    error: ErrorKind | None

    @property
    def key(self) -> str:
        return f"{self.set_name}{self.position}"

    @property
    def expected_action(self) -> str:
        return "approve" if self.error is None else "reject"

    @property
    def expected_reason(self) -> str | None:
        return EXPECTED_REASON[self.error] if self.error else None


@dataclass(frozen=True, slots=True)
class PlannedTask:
    spec: TaskSpec
    ui: UI
    order: int  # 1..12 within the session


def session_plan(participant_number: int) -> list[PlannedTask]:
    """Odd participants start with the legacy UI; set A/B alternates every two participants."""
    first: UI = "legacy" if participant_number % 2 == 1 else "console"
    second: UI = "console" if first == "legacy" else "legacy"
    first_set, second_set = ("A", "B") if (participant_number // 2) % 2 == 0 else ("B", "A")
    tasks: list[PlannedTask] = []
    for ui, set_name in ((first, first_set), (second, second_set)):
        for position, error in enumerate(SETS[set_name], start=1):
            tasks.append(PlannedTask(TaskSpec(set_name, position, error), ui, len(tasks) + 1))
    return tasks


def task_scenario(exercise: Scenario, spec: TaskSpec, attempt: int = 0) -> Scenario:
    """A deterministic slice of the exercise: five incidents and sixteen units per task."""
    rng = random.Random(f"{SEED}-{spec.key}-{attempt}")
    incidents = sorted(rng.sample(exercise.incidents, INCIDENTS_PER_TASK), key=lambda i: i.id)
    resources = sorted(rng.sample(exercise.resources, UNITS_PER_TASK), key=lambda r: r.id)
    return Scenario(scenario_id=f"STUDY-{spec.key}", incidents=incidents, resources=resources)


class _FixedPlan:
    """An engine that proposes a plan built elsewhere (the solver's, possibly with an error)."""

    name: str = "study"

    def __init__(self, plan: DecisionResult) -> None:
        self._plan = plan

    def recommend(
        self,
        scenario: Scenario,
        travel_times: TravelTimeMatrix | None = None,
        constraints: Sequence[PlanningConstraint] = (),
    ) -> DecisionResult:
        return self._plan


def _longest_assignment(plan: DecisionResult) -> int:
    return max(range(len(plan.assignments)), key=lambda i: plan.assignments[i].travel_minutes)


def _inject(plan: DecisionResult, error: ErrorKind) -> DecisionResult:
    index = _longest_assignment(plan)
    original = plan.assignments[index]
    if error == "wrong_eta":
        changed: Assignment = original.model_copy(
            update={"travel_minutes": round(max(0.5, original.travel_minutes * 0.35), 1)}
        )
    elif error == "phantom_unit":
        changed = original.model_copy(update={"resource_id": PHANTOM_UNIT_ID})
    else:
        return plan
    assignments = list(plan.assignments)
    assignments[index] = changed
    return plan.model_copy(update={"assignments": assignments})


def _corrupt_sitrep(outcome: DecisionOutcome, scenario: Scenario) -> DecisionOutcome:
    """Change the first unit ETA in the SITREP by +7.0 min and re-verify."""
    draft = outcome.drafts[0]
    corrupted = re.sub(
        r"ETA (\d+(?:\.\d+)?) min",
        lambda m: f"ETA {float(m.group(1)) + 7.0:.1f} min",
        draft.text,
        count=1,
    )
    drafts = (TextDraft(id=draft.id, kind=draft.kind, text=corrupted),)
    report = verify(
        outcome.result,
        scenario,
        reference_plan=outcome.reference,
        travel_times=outcome.travel_times,
        constraints=outcome.constraints,
        evidence=outcome.result.evidence,
        text_drafts=drafts,
        policy=VerificationPolicy(require_citations=False),
    )
    status = (
        DecisionStatus.BLOCKED
        if report.verdict == Verdict.BLOCKED or outcome.result.status == DecisionStatus.BLOCKED
        else DecisionStatus.REQUIRES_HUMAN_APPROVAL
    )
    result = outcome.result.model_copy(update={
        "status": status,
        "decision_trace": [*outcome.result.decision_trace, "Study task: SITREP edited."],
    })
    return DecisionOutcome(result=result, verification=report, reference=outcome.reference,
                           travel_times=outcome.travel_times, drafts=drafts,
                           constraints=outcome.constraints)


def build_task(
    exercise: Scenario, spec: TaskSpec, travel: TravelTimeProvider
) -> tuple[Scenario, DecisionOutcome]:
    """The task's scenario and a verified plan for it, with the task's error injected.

    Slices are re-drawn (deterministically) until the solver's plan passes every check, so an
    error-free task can be approved and an injected task has exactly one problem."""
    for attempt in range(MAX_ATTEMPTS):
        scenario = task_scenario(exercise, spec, attempt)
        solver = DecisionService({}, travel).decide(scenario)
        if not solver.verification.failed() and solver.result.status != DecisionStatus.BLOCKED:
            break
    else:
        raise ValueError(f"no clean slice for study task {spec.key}")
    if spec.error is None:
        return scenario, solver
    if spec.error == "sitrep_mismatch":
        return scenario, _corrupt_sitrep(solver, scenario)
    injected = _inject(solver.result, spec.error)
    return scenario, DecisionService({"study": _FixedPlan(injected)}, travel).decide(
        scenario, "study"
    )
