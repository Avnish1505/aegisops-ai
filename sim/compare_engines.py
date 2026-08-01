"""Evaluate rule-based and NIM RAG decisions across reproducible scenarios."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from aegisops.application.scenario_service import generate_scenario
from aegisops.domain.models import DecisionResult
from aegisops.infrastructure.llm_decision_engine import LLMDecisionEngine
from aegisops.infrastructure.retrieval_engine import RetrievalEngine
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine


def _percentile(values: list[float], percentile: float) -> float:
    """Return an interpolated percentile without adding a numerical dependency."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _result_metrics(result: DecisionResult, latency_ms: float) -> dict[str, Any]:
    """Extract comparison metrics without changing either engine's result."""
    findings_by_severity = Counter(finding.severity for finding in result.safety_findings)
    return {
        "coverage": result.advisory_confidence,
        "unmet_requirements": {
            "entries": len(result.unmet_requirements),
            "units": sum(requirement.quantity for requirement in result.unmet_requirements),
        },
        "safety_findings": {
            "total": len(result.safety_findings),
            "by_severity": dict(sorted(findings_by_severity.items())),
        },
        "blocked": result.status.value == "blocked",
        "latency_ms": round(latency_ms, 3),
    }


def _aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-scenario measurements for one engine."""
    metrics = [run["metrics"] for run in runs]
    latencies = [metric["latency_ms"] for metric in metrics]
    findings_by_severity: Counter[str] = Counter()
    for metric in metrics:
        findings_by_severity.update(metric["safety_findings"]["by_severity"])

    return {
        "scenarios": len(runs),
        "coverage": round(mean(metric["coverage"] for metric in metrics), 4),
        "unmet_requirements": {
            "entries": sum(metric["unmet_requirements"]["entries"] for metric in metrics),
            "units": sum(metric["unmet_requirements"]["units"] for metric in metrics),
        },
        "safety_findings": {
            "total": sum(metric["safety_findings"]["total"] for metric in metrics),
            "by_severity": dict(sorted(findings_by_severity.items())),
        },
        "blocked_rate": round(
            sum(metric["blocked"] for metric in metrics) / len(metrics) if metrics else 0.0,
            4,
        ),
        "latency_ms": {
            "mean": round(mean(latencies), 3) if latencies else 0.0,
            "p50": round(_percentile(latencies, 0.5), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
        },
    }


def compare_seeds(seeds: Iterable[int]) -> dict[str, Any]:
    """Run both unchanged engines for every seed and collect their measurements."""
    seed_values = list(seeds)
    knowledge_dir = Path(__file__).parents[1] / "knowledge"
    engines = {
        "rule_based": RuleBasedDecisionEngine(),
        "llm_rag": LLMDecisionEngine(RetrievalEngine(knowledge_dir)),
    }
    engine_runs: dict[str, list[dict[str, Any]]] = {name: [] for name in engines}

    for seed in seed_values:
        scenario = generate_scenario(seed=seed)
        for name, engine in engines.items():
            started_at = perf_counter()
            result = engine.recommend(scenario)
            latency_ms = (perf_counter() - started_at) * 1_000
            engine_runs[name].append(
                {
                    "seed": seed,
                    "scenario_id": scenario.scenario_id,
                    "metrics": _result_metrics(result, latency_ms),
                    "decision": result.model_dump(mode="json"),
                }
            )

    return {
        "seed_range": {
            "start": min(seed_values),
            "end": max(seed_values),
            "count": len(seed_values),
        },
        "engines": {
            name: {"summary": _aggregate(runs), "runs": runs}
            for name, runs in engine_runs.items()
        },
    }


def markdown_summary(report: dict[str, Any]) -> str:
    """Render a concise human-readable counterpart to the JSON report."""
    seed_range = report["seed_range"]
    lines = [
        "# Engine comparison summary",
        "",
        (
            f"Seeds: {seed_range['start']}-{seed_range['end']} "
            f"({seed_range['count']} scenarios)"
        ),
        "",
        (
            "| Engine | Coverage | Unmet units | Safety findings | Blocked rate | "
            "Mean / p50 / p95 latency (ms) |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, engine_report in report["engines"].items():
        summary = engine_report["summary"]
        latency = summary["latency_ms"]
        lines.append(
            f"| {name} | {summary['coverage']:.2%} | "
            f"{summary['unmet_requirements']['units']} | "
            f"{summary['safety_findings']['total']} | "
            f"{summary['blocked_rate']:.2%} | "
            f"{latency['mean']:.3f} / {latency['p50']:.3f} / {latency['p95']:.3f} |"
        )
    lines.extend(["", "Safety-finding severity totals:", ""])
    for name, engine_report in report["engines"].items():
        findings = engine_report["summary"]["safety_findings"]["by_severity"]
        rendered = ", ".join(f"{severity}: {count}" for severity, count in findings.items())
        lines.append(f"- {name}: {rendered or 'none'}")
    return "\n".join(lines) + "\n"


def _write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    """Evaluate seeds 0-29 by default and emit JSON plus an optional Markdown report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-seed", type=int, default=0, help="First inclusive scenario seed.")
    parser.add_argument("--end-seed", type=int, default=29, help="Last inclusive scenario seed.")
    parser.add_argument("--json-output", type=Path, help="Optional path for the JSON report.")
    parser.add_argument(
        "--markdown-output", type=Path, help="Optional path for the Markdown summary."
    )
    args = parser.parse_args()
    if args.start_seed > args.end_seed:
        parser.error("--start-seed must not be greater than --end-seed")

    seeds = list(range(args.start_seed, args.end_seed + 1))
    report = compare_seeds(seeds)
    json_report = json.dumps(report, indent=2) + "\n"
    summary = markdown_summary(report)
    if args.json_output:
        _write_output(args.json_output, json_report)
    if args.markdown_output:
        _write_output(args.markdown_output, summary)
    print(json_report, end="")


if __name__ == "__main__":
    main()
