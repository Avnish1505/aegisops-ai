"""Build a single research report from the existing simulation harnesses."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from statistics import mean
from typing import Any

from sim.compare_engines import (
    compare_seeds,
)
from sim.compare_engines import (
    markdown_summary as comparison_markdown_summary,
)
from sim.evaluation_harness import (
    evaluate,
)
from sim.evaluation_harness import (
    markdown_summary as evaluation_markdown_summary,
)


def _decisions(
    comparison: dict[str, Any], evaluation: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    """Yield decisions already produced by the comparison and evaluation harnesses."""
    for engine_report in comparison["engines"].values():
        yield from (run["decision"] for run in engine_report["runs"])
    for engine_report in evaluation["engines"].values():
        yield from (result["decision"] for result in engine_report["results"])


def _adversarial_test_summary(evaluation: dict[str, Any]) -> dict[str, Any]:
    """Summarise safety-contract outcomes from the golden evaluation suite."""
    results = [
        result
        for engine_report in evaluation["engines"].values()
        for result in engine_report["results"]
    ]
    regressions = [
        regression for result in results for regression in result["regressions"]
    ]
    return {
        "scope": "golden-suite safety-contract checks",
        "checks": len(results),
        "passed": sum(result["passed"] for result in results),
        "failed": sum(not result["passed"] for result in results),
        "regressions": len(regressions),
        "blocked_recommendations": sum(result["metrics"]["blocked"] for result in results),
        "human_approval_violations": sum(
            "human approval" in regression for regression in regressions
        ),
    }


def _provenance_statistics(
    comparison: dict[str, Any], evaluation: dict[str, Any]
) -> dict[str, Any]:
    """Aggregate evidence and citation coverage across existing harness output."""
    decisions = list(_decisions(comparison, evaluation))
    evidence = [item for decision in decisions for item in decision["evidence"]]
    assignments = [
        assignment for decision in decisions for assignment in decision["assignments"]
    ]
    sources = Counter(item["source"] for item in evidence)
    cited_assignments = sum(bool(assignment["evidence_ids"]) for assignment in assignments)
    return {
        "decisions": len(decisions),
        "decisions_with_evidence": sum(bool(decision["evidence"]) for decision in decisions),
        "evidence_items": len(evidence),
        "unique_evidence_ids": len({item["id"] for item in evidence}),
        "sources": dict(sorted(sources.items())),
        "mean_evidence_confidence": round(mean(item["confidence"] for item in evidence), 4)
        if evidence
        else 0.0,
        "assignments": len(assignments),
        "assignments_with_citations": cited_assignments,
        "assignment_citation_rate": round(cited_assignments / len(assignments), 4)
        if assignments
        else 0.0,
    }


def build_experiment_report(seeds: Iterable[int]) -> dict[str, Any]:
    """Run the unchanged harnesses and combine their outputs into one report."""
    seed_values = list(seeds)
    if not seed_values:
        raise ValueError("seeds must contain at least one value")

    comparison = compare_seeds(seed_values)
    evaluation = evaluate()
    return {
        "report_version": "bundle_14_v1",
        "benchmark_metrics": comparison,
        "evaluation_results": evaluation,
        "adversarial_test_summary": _adversarial_test_summary(evaluation),
        "provenance_statistics": _provenance_statistics(comparison, evaluation),
    }


def markdown_report(report: dict[str, Any]) -> str:
    """Render the combined report as Markdown for research documentation."""
    adversarial = report["adversarial_test_summary"]
    provenance = report["provenance_statistics"]
    comparison = comparison_markdown_summary(report["benchmark_metrics"])
    evaluation = evaluation_markdown_summary(report["evaluation_results"])
    lines = [
        "# AegisOps experiment report",
        "",
        "## Benchmark metrics",
        "",
        comparison.replace("# Engine comparison summary", "### Engine comparison").rstrip(),
        "",
        "## Evaluation results",
        "",
        evaluation.replace("# Engine evaluation summary", "### Engine evaluation").rstrip(),
        "",
        "## Adversarial test summary",
        "",
        f"Scope: {adversarial['scope']}.",
        "",
        "| Checks | Passed | Failed | Regressions | Blocked | Approval violations |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {adversarial['checks']} | {adversarial['passed']} | "
            f"{adversarial['failed']} | {adversarial['regressions']} | "
            f"{adversarial['blocked_recommendations']} | "
            f"{adversarial['human_approval_violations']} |"
        ),
        "",
        "## Provenance statistics",
        "",
        (
            "| Decisions | With evidence | Evidence items | Unique evidence | Mean confidence | "
            "Citation rate |"
        ),
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {provenance['decisions']} | {provenance['decisions_with_evidence']} | "
            f"{provenance['evidence_items']} | {provenance['unique_evidence_ids']} | "
            f"{provenance['mean_evidence_confidence']:.2%} | "
            f"{provenance['assignment_citation_rate']:.2%} |"
        ),
        "",
        "Evidence sources:",
        "",
    ]
    lines.extend(
        f"- {source}: {count}" for source, count in provenance["sources"].items()
    )
    if not provenance["sources"]:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_reports(report: dict[str, Any], json_output: Path, markdown_output: Path) -> None:
    """Write the JSON and Markdown forms of an experiment report."""
    for output in (json_output, markdown_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_output.write_text(markdown_report(report), encoding="utf-8")


def main() -> None:
    """Run the default benchmark and write both research-report formats."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-seed", type=int, default=0, help="First inclusive benchmark seed.")
    parser.add_argument("--end-seed", type=int, default=29, help="Last inclusive benchmark seed.")
    parser.add_argument(
        "--json-output", type=Path, default=Path("experiment_report.json"), help="JSON report path."
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("experiment_report.md"),
        help="Markdown report path.",
    )
    args = parser.parse_args()
    if args.start_seed > args.end_seed:
        parser.error("--start-seed must not be greater than --end-seed")

    report = build_experiment_report(range(args.start_seed, args.end_seed + 1))
    write_reports(report, args.json_output, args.markdown_output)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
