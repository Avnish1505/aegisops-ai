import pytest

from aegisops.application.scenario_service import generate_scenario
from aegisops.domain.models import Scenario
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine
from aegisops.planning.constraints import ExcludeUnit, PriorityBoost, ReserveConstraint, Zone
from aegisops.planning.objective import plan_objective
from aegisops.planning.solver import SolverDecisionEngine, SolveStatus, solve
from aegisops.planning.travel import EuclideanProvider


def _scenario(incidents: list[dict[str, object]], resources: list[dict[str, object]]) -> Scenario:
    return Scenario.model_validate(
        {
            "scenario_id": "SCEN-solver",
            "incidents": [
                {"people_affected": 1, "reported_at_min": 0, **incident} for incident in incidents
            ],
            "resources": resources,
        }
    )


def _two_incidents_one_ambulance() -> Scenario:
    return _scenario(
        [
            {"id": "INC-med", "type": "medical", "severity": "medium", "location": [1, 0],
             "resources_needed": {"ambulance": 1}},
            {"id": "INC-crit", "type": "medical", "severity": "critical", "location": [30, 0],
             "resources_needed": {"ambulance": 1}},
        ],
        [{"id": "RES-amb", "type": "ambulance", "location": [0, 0]}],
    )


def _solve(scenario: Scenario, constraints=()):  # type: ignore[no-untyped-def]
    return solve(scenario, EuclideanProvider().matrix(scenario), constraints)


def test_scarce_unit_goes_to_the_higher_severity_incident() -> None:
    result = _solve(_two_incidents_one_ambulance())

    assert result.status == SolveStatus.OPTIMAL
    assert [(a.incident_id, a.resource_id) for a in result.assignments] == [
        ("INC-crit", "RES-amb")
    ]
    assert [(u.incident_id, u.quantity) for u in result.unmet_requirements] == [("INC-med", 1)]


def test_priority_boost_can_change_the_choice() -> None:
    boost = PriorityBoost(incident_id="INC-med", factor=10)

    result = _solve(_two_incidents_one_ambulance(), [boost])

    assert [a.incident_id for a in result.assignments] == ["INC-med"]


def test_excluded_unit_is_never_assigned() -> None:
    result = _solve(_two_incidents_one_ambulance(), [ExcludeUnit(unit_id="RES-amb")])

    assert result.status == SolveStatus.OPTIMAL
    assert result.assignments == []
    assert len(result.unmet_requirements) == 2


def test_reserve_keeps_units_idle_inside_the_zone() -> None:
    scenario = _scenario(
        [{"id": "INC-1", "type": "medical", "severity": "high", "location": [0, 0],
          "resources_needed": {"ambulance": 2}}],
        [
            {"id": "RES-near", "type": "ambulance", "location": [1, 1]},
            {"id": "RES-far", "type": "ambulance", "location": [90, 90]},
        ],
    )
    north = Zone(id="north", min_x=80, min_y=80, max_x=100, max_y=100)

    result = _solve(scenario, [ReserveConstraint(resource_type="ambulance", count=1, zone=north)])

    assert [a.resource_id for a in result.assignments] == ["RES-near"]
    assert result.unmet_requirements[0].quantity == 1


def test_conflicting_reserve_and_exclusion_are_reported_as_infeasible() -> None:
    scenario = _scenario(
        [{"id": "INC-1", "type": "medical", "severity": "low", "location": [0, 0],
          "resources_needed": {"ambulance": 1}}],
        [{"id": "RES-1", "type": "ambulance", "location": [5, 5]}],
    )
    everywhere = Zone(id="all", min_x=0, min_y=0, max_x=100, max_y=100)
    reserve = ReserveConstraint(resource_type="ambulance", count=1, zone=everywhere)
    exclude = ExcludeUnit(unit_id="RES-1")
    unrelated = PriorityBoost(incident_id="INC-1", factor=2)

    result = _solve(scenario, [unrelated, reserve, exclude])

    assert result.status == SolveStatus.INFEASIBLE
    assert result.infeasibility is not None
    assert set(result.infeasibility.conflicting_constraints) == {reserve, exclude}
    assert "only 0 available" in result.infeasibility.message


@pytest.mark.parametrize(
    "constraint",
    [ExcludeUnit(unit_id="RES-ghost"), PriorityBoost(incident_id="INC-ghost", factor=2)],
)
def test_constraints_naming_unknown_entities_are_invalid_input(constraint) -> None:  # type: ignore[no-untyped-def]
    result = _solve(_two_incidents_one_ambulance(), [constraint])

    assert result.status == SolveStatus.INVALID_INPUT
    assert result.infeasibility is not None
    assert result.infeasibility.conflicting_constraints == [constraint]


@pytest.mark.parametrize("seed", range(20))
def test_plans_respect_hard_constraints(seed: int) -> None:
    scenario = generate_scenario(seed=seed)
    resources = {resource.id: resource for resource in scenario.resources}
    incidents = {incident.id: incident for incident in scenario.incidents}

    result = _solve(scenario)

    assert result.status == SolveStatus.OPTIMAL
    used = [a.resource_id for a in result.assignments]
    assert len(used) == len(set(used))
    per_requirement: dict[tuple[str, str], int] = {}
    for assignment in result.assignments:
        resource = resources[assignment.resource_id]
        assert resource.available
        assert resource.type in incidents[assignment.incident_id].resources_needed
        key = (assignment.incident_id, resource.type)
        per_requirement[key] = per_requirement.get(key, 0) + 1
    for (incident_id, resource_type), count in per_requirement.items():
        assert count <= incidents[incident_id].resources_needed[resource_type]


@pytest.mark.parametrize("seed", range(30))
def test_solver_is_never_worse_than_the_greedy_baseline(seed: int) -> None:
    scenario = generate_scenario(seed=seed)
    matrix = EuclideanProvider().matrix(scenario)
    greedy = RuleBasedDecisionEngine().recommend(scenario, matrix)

    optimum = solve(scenario, matrix)
    greedy_objective = plan_objective(
        greedy.assignments, greedy.unmet_requirements, scenario, matrix, []
    ).total

    assert optimum.objective is not None
    assert optimum.objective <= greedy_objective + 1e-6


def test_solve_is_deterministic_for_replay() -> None:
    scenario = generate_scenario(seed=4)

    first = _solve(scenario)
    second = _solve(scenario)

    assert first.assignments == second.assignments
    assert first.objective == second.objective


def test_solver_engine_blocks_with_explanation_when_infeasible() -> None:
    scenario = _two_incidents_one_ambulance()
    everywhere = Zone(id="all", min_x=0, min_y=0, max_x=100, max_y=100)

    result = SolverDecisionEngine().recommend(
        scenario,
        constraints=[ReserveConstraint(resource_type="ambulance", count=2, zone=everywhere)],
    )

    assert result.status.value == "blocked"
    assert result.requires_human_approval is True
    assert any("only 1 available" in line for line in result.decision_trace)
