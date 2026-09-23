"""Property-based tests of the solver and verifier."""

from __future__ import annotations

import itertools

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from aegisops.application.scenario_service import generate_scenario
from aegisops.communication.sitrep import render_sitrep
from aegisops.domain.models import Scenario
from aegisops.planning.constraints import ExcludeUnit
from aegisops.planning.objective import plan_objective
from aegisops.planning.solver import SolverDecisionEngine, solve
from aegisops.planning.travel import EuclideanProvider
from aegisops.verification.models import VerificationPolicy
from aegisops.verification.verifier import verify

SETTINGS = settings(max_examples=60, deadline=None)


@SETTINGS
@given(
    seed=st.integers(min_value=0, max_value=100_000),
    incidents=st.integers(min_value=1, max_value=10),
    excluded=st.lists(st.integers(min_value=0, max_value=9), max_size=3, unique=True),
)
def test_solver_plans_never_fail_a_critical_check(
    seed: int, incidents: int, excluded: list[int]
) -> None:
    scenario = generate_scenario(seed=seed, num_incidents=incidents)
    constraints = [ExcludeUnit(unit_id=scenario.resources[index].id) for index in excluded]
    matrix = EuclideanProvider().matrix(scenario)
    reference = solve(scenario, matrix, constraints)
    plan = SolverDecisionEngine().result_from_solve(scenario, reference)

    report = verify(
        plan,
        scenario,
        reference_plan=reference,
        travel_times=matrix,
        constraints=constraints,
        text_drafts=[render_sitrep(plan, scenario, matrix)],
    )

    assert report.blocking_check_ids == []
    assert report.failed() == []


@SETTINGS
@given(seed=st.integers(min_value=0, max_value=100_000))
def test_verify_is_a_pure_function(seed: int) -> None:
    scenario = generate_scenario(seed=seed)
    matrix = EuclideanProvider().matrix(scenario)
    reference = solve(scenario, matrix)
    plan = SolverDecisionEngine().result_from_solve(scenario, reference)
    drafts = [render_sitrep(plan, scenario, matrix)]

    def run():  # type: ignore[no-untyped-def]
        return verify(
            plan, scenario, reference_plan=reference, travel_times=matrix, text_drafts=drafts
        )

    assert run() == run()


@SETTINGS
@given(
    seed=st.integers(min_value=0, max_value=100_000),
    pick=st.integers(min_value=0, max_value=1_000),
    fraction=st.floats(min_value=0.0, max_value=3.0, allow_nan=False),
    overstate=st.booleans(),
)
def test_travel_time_claims_are_caught_exactly_beyond_tolerance(
    seed: int, pick: int, fraction: float, overstate: bool
) -> None:
    scenario = generate_scenario(seed=seed)
    matrix = EuclideanProvider().matrix(scenario)
    reference = solve(scenario, matrix)
    plan = SolverDecisionEngine().result_from_solve(scenario, reference)
    assume(plan.assignments)
    index = pick % len(plan.assignments)
    target = plan.assignments[index]
    true_minutes = matrix.get(target.resource_id, target.incident_id)
    assert true_minutes is not None
    tolerance = VerificationPolicy().travel_tolerance(true_minutes)
    delta = tolerance * fraction
    claim = true_minutes + delta if overstate else true_minutes - delta
    assume(claim >= 0 and abs(fraction - 1.0) > 1e-6)
    assignments = list(plan.assignments)
    assignments[index] = target.model_copy(update={"travel_minutes": claim})

    report = verify(
        plan.model_copy(update={"assignments": assignments}),
        scenario,
        reference_plan=reference,
        travel_times=matrix,
    )

    assert report.check("travel_time_matches").passed == (fraction < 1.0)


@st.composite
def tiny_scenarios(draw: st.DrawFn) -> Scenario:
    types = ["ambulance", "fire_unit"]
    coordinate = st.integers(min_value=0, max_value=100)
    incident_count = draw(st.integers(min_value=1, max_value=3))
    resource_count = draw(st.integers(min_value=0, max_value=4))
    incidents = []
    for index in range(incident_count):
        needed = draw(
            st.dictionaries(st.sampled_from(types), st.integers(1, 2), min_size=1, max_size=2)
        )
        incidents.append(
            {
                "id": f"INC-{index}",
                "type": "fire",
                "severity": draw(st.sampled_from(["low", "medium", "high", "critical"])),
                "location": [draw(coordinate), draw(coordinate)],
                "people_affected": 1,
                "reported_at_min": 0,
                "resources_needed": needed,
            }
        )
    resources = [
        {
            "id": f"RES-{index}",
            "type": draw(st.sampled_from(types)),
            "location": [draw(coordinate), draw(coordinate)],
            "available": draw(st.booleans()),
        }
        for index in range(resource_count)
    ]
    return Scenario.model_validate(
        {"scenario_id": "SCEN-tiny", "incidents": incidents, "resources": resources}
    )


@SETTINGS
@given(scenario=tiny_scenarios())
def test_solver_matches_brute_force_optimum_on_tiny_instances(scenario: Scenario) -> None:
    matrix = EuclideanProvider().matrix(scenario)
    result = solve(scenario, matrix)

    best = min(_brute_force_objectives(scenario, matrix))

    assert result.objective is not None
    # CP-SAT optimises travel rounded to 0.01 min, times a weight of at most 15: at most
    # 0.075 per assignment of drift, and nothing more.
    assert abs(result.objective - best) <= 0.1 * max(1, len(scenario.resources))


def _brute_force_objectives(scenario: Scenario, matrix):  # type: ignore[no-untyped-def]
    from aegisops.domain.models import Assignment, UnmetRequirement

    units = [r for r in scenario.resources if r.available]
    options = [
        [None, *[i.id for i in scenario.incidents if r.type in i.resources_needed]] for r in units
    ]
    incidents = {i.id: i for i in scenario.incidents}
    for choice in itertools.product(*options):
        counts: dict[tuple[str, object], int] = {}
        assignments = []
        for unit, incident_id in zip(units, choice, strict=True):
            if incident_id is None:
                continue
            key = (incident_id, unit.type)
            counts[key] = counts.get(key, 0) + 1
            assignments.append(
                Assignment(
                    incident_id=incident_id,
                    resource_id=unit.id,
                    resource_type=unit.type,
                    travel_minutes=matrix.get(unit.id, incident_id),
                )
            )
        if any(count > incidents[i].resources_needed[t] for (i, t), count in counts.items()):
            continue
        unmet = [
            UnmetRequirement(
                incident_id=incident.id,
                resource_type=resource_type,
                quantity=quantity - counts.get((incident.id, resource_type), 0),
                severity=incident.severity,
            )
            for incident in scenario.incidents
            for resource_type, quantity in incident.resources_needed.items()
            if quantity > counts.get((incident.id, resource_type), 0)
        ]
        yield plan_objective(assignments, unmet, scenario, matrix, []).total
