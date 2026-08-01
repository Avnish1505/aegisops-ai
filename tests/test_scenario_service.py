from aegisops.application.scenario_service import generate_scenario


def test_seeded_scenarios_are_reproducible() -> None:
    first = generate_scenario(seed=42).model_dump(mode="json")
    second = generate_scenario(seed=42).model_dump(mode="json")

    assert first == second
    assert len({incident["id"] for incident in first["incidents"]}) == len(first["incidents"])
    assert len({resource["id"] for resource in first["resources"]}) == len(first["resources"])
