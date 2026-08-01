from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine
from sim.evaluation_harness import detect_regressions, evaluate, markdown_summary
from sim.golden_scenarios import golden_scenarios


def test_golden_scenarios_are_reusable_and_have_unique_names() -> None:
    first = golden_scenarios()
    second = golden_scenarios()

    assert len(first) == 4
    assert [scenario.name for scenario in first] == [scenario.name for scenario in second]
    assert len({scenario.name for scenario in first}) == len(first)


def test_rule_based_engine_passes_all_golden_expectations() -> None:
    for golden in golden_scenarios():
        result = RuleBasedDecisionEngine().recommend(golden.scenario)

        assert detect_regressions(golden, "rule_based", result) == []


def test_regression_detector_rejects_missing_human_approval() -> None:
    golden = golden_scenarios()[0]
    unsafe_result = RuleBasedDecisionEngine().recommend(golden.scenario).model_copy(
        update={"requires_human_approval": False}
    )

    assert "recommendation does not require human approval" in detect_regressions(
        golden, "rule_based", unsafe_result
    )


def test_harness_evaluates_both_engines_and_renders_summary() -> None:
    report = evaluate()
    summary = markdown_summary(report)

    assert set(report["engines"]) == {"rule_based", "llm_rag"}
    assert report["engines"]["rule_based"]["summary"]["failed"] == 0
    assert "# Engine evaluation summary" in summary
