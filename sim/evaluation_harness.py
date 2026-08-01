"""Evaluate both decision engines against reusable golden scenarios."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from aegisops.domain.models import DecisionResult, Scenario
from aegisops.infrastructure.llm_decision_engine import LLMDecisionEngine
from aegisops.infrastructure.retrieval_engine import RetrievalEngine
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine
from sim.golden_scenarios import EngineExpectation, GoldenScenario, golden_scenarios


def _unmet_units(result: DecisionResult) -> int:
    return sum(requirement.quantity for requirement in result.unmet_requirements)


def _validate_safety_contract(scenario: Scenario, result: DecisionResult) -> list[str]:
    """Return provider-independent safety regressions for a decision result."""
    regressions: list[str] = []
    resources = {resource.id: resource for resource in scenario.resources}
    incidents = {incident.id: incident for incident in scenario.incidents}
    assigned_resource_ids = [assignment.resource_id for assignment in result.assignments]

    if not result.requires_human_approval:
        regressions.append("recommendation does not require human approval")
    if len(assigned_resource_ids) != len(set(assigned_resource_ids)):
        regressions.append("a resource was assigned more than once")
    for assignment in result.assignments:
        resource = resources.get(assignment.resource_id)
        incident = incidents.get(assignment.incident_id)
        if resource is None:
            regressions.append(f"assignment references unknown resource {assignment.resource_id}")
        elif not resource.available:
            regressions.append(f"assignment uses unavailable resource {assignment.resource_id}")
        if incident is None:
            regressions.append(f"assignment references unknown incident {assignment.incident_id}")
        elif resource is not None and (
            assignment.resource_type != resource.type
            or resource.type not in incident.resources_needed
        ):
            regressions.append(f"assignment has an unrequested resource type for {incident.id}")
    return regressions


def _validate_rule_expectation(result: DecisionResult, expected: EngineExpectation) -> list[str]:
    """Compare deterministic baseline output with its golden expectation."""
    regressions: list[str] = []
    assigned_ids = tuple(assignment.resource_id for assignment in result.assignments)
    finding_codes = {finding.code for finding in result.safety_findings}
    if result.status != expected.status:
        regressions.append(f"expected status {expected.status.value}, got {result.status.value}")
    if assigned_ids != expected.assignment_ids:
        regressions.append(f"expected assignments {expected.assignment_ids}, got {assigned_ids}")
    if _unmet_units(result) != expected.unmet_units:
        regressions.append(
            f"expected {expected.unmet_units} unmet units, got {_unmet_units(result)}"
        )
    if not set(expected.required_finding_codes) <= finding_codes:
        regressions.append("required safety finding is missing")
    if result.advisory_confidence != expected.coverage:
        regressions.append(
            f"expected coverage {expected.coverage}, got {result.advisory_confidence}"
        )
    return regressions


def detect_regressions(
    golden: GoldenScenario, engine_name: str, result: DecisionResult
) -> list[str]:
    """Detect output-contract and golden-output regressions without changing engines."""
    regressions = _validate_safety_contract(golden.scenario, result)
    if golden.must_block and result.status.value != "blocked":
        regressions.append("critical unmet capability did not produce a blocked recommendation")
    if engine_name == "rule_based":
        regressions.extend(_validate_rule_expectation(result, golden.rule_based_expectation))
    return regressions


def _scenario_result(
    golden: GoldenScenario, engine_name: str, result: DecisionResult
) -> dict[str, Any]:
    regressions = detect_regressions(golden, engine_name, result)
    return {
        "scenario": golden.name,
        "scenario_id": golden.scenario.scenario_id,
        "passed": not regressions,
        "regressions": regressions,
        "metrics": {
            "assignments": len(result.assignments),
            "unmet_units": _unmet_units(result),
            "safety_findings": len(result.safety_findings),
            "blocked": result.status.value == "blocked",
            "coverage": result.advisory_confidence,
        },
        "decision": result.model_dump(mode="json"),
    }


def evaluate(scenarios: Iterable[GoldenScenario] | None = None) -> dict[str, Any]:
    """Evaluate the rule baseline and configured NIM engine on golden scenarios."""
    suite = tuple(scenarios or golden_scenarios())
    knowledge_dir = Path(__file__).parents[1] / "knowledge"
    engines = {
        "rule_based": RuleBasedDecisionEngine(),
        "llm_rag": LLMDecisionEngine(RetrievalEngine(knowledge_dir)),
    }
    evaluations: dict[str, list[dict[str, Any]]] = {name: [] for name in engines}
    for golden in suite:
        for engine_name, engine in engines.items():
            evaluations[engine_name].append(
                _scenario_result(golden, engine_name, engine.recommend(golden.scenario))
            )

    engines_report = {}
    for engine_name, results in evaluations.items():
        regression_count = sum(len(result["regressions"]) for result in results)
        engines_report[engine_name] = {
            "summary": {
                "scenarios": len(results),
                "passed": sum(result["passed"] for result in results),
                "failed": sum(not result["passed"] for result in results),
                "regressions": regression_count,
            },
            "results": results,
        }
    return {
        "suite": "golden_scenarios_v1",
        "passed": all(
            result["passed"]
            for engine_report in engines_report.values()
            for result in engine_report["results"]
        ),
        "engines": engines_report,
    }


def markdown_summary(report: dict[str, Any]) -> str:
    """Render the evaluation pass/fail state as a concise Markdown summary."""
    lines = [
        "# Engine evaluation summary",
        "",
        f"Suite: `{report['suite']}`",
        "",
        "| Engine | Passed | Failed | Regressions |",
        "| --- | ---: | ---: | ---: |",
    ]
    for engine_name, engine_report in report["engines"].items():
        summary = engine_report["summary"]
        lines.append(
            f"| {engine_name} | {summary['passed']} | {summary['failed']} | "
            f"{summary['regressions']} |"
        )
    lines.extend(["", "## Regression details", ""])
    for engine_name, engine_report in report["engines"].items():
        failed = [result for result in engine_report["results"] if not result["passed"]]
        if not failed:
            lines.append(f"- {engine_name}: none")
            continue
        for result in failed:
            lines.append(
                f"- {engine_name} / {result['scenario']}: "
                + "; ".join(result["regressions"])
            )
    return "\n".join(lines) + "\n"


def _write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    """Run the golden suite and emit JSON plus an optional Markdown summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, help="Optional path for the JSON report.")
    parser.add_argument(
        "--markdown-output", type=Path, help="Optional path for the Markdown summary."
    )
    args = parser.parse_args()
    report = evaluate()
    json_report = json.dumps(report, indent=2) + "\n"
    if args.json_output:
        _write_output(args.json_output, json_report)
    if args.markdown_output:
        _write_output(args.markdown_output, markdown_summary(report))
    print(json_report, end="")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
