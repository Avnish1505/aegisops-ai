"""Render Phase 3 charts from an existing experiment report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CHART_FILENAMES = {
    "coverage": "phase_3_coverage.png",
    "latency": "phase_3_latency.png",
    "blocked_rate": "phase_3_blocked_rate.png",
    "safety_findings": "phase_3_safety_findings.png",
    "adversarial_pass_rate": "phase_3_adversarial_pass_rate.png",
    "provenance_coverage": "phase_3_provenance_coverage.png",
}


def _plot_modules() -> tuple[Any, Any]:
    """Load matplotlib only when chart rendering is requested."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as pyplot
    except ImportError as error:  # pragma: no cover - depends on local installation
        raise RuntimeError(
            "Chart rendering requires matplotlib. Install the project dependencies first."
        ) from error
    return matplotlib, pyplot


def _engine_summaries(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: engine_report["summary"]
        for name, engine_report in report["benchmark_metrics"]["engines"].items()
    }


def _save_bar_chart(
    pyplot: Any,
    output: Path,
    title: str,
    labels: list[str],
    values: list[float],
    ylabel: str,
    *,
    percent: bool = False,
) -> None:
    figure, axis = pyplot.subplots(figsize=(7, 4.5))
    bars = axis.bar(labels, values, color="#2563eb")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    if percent:
        axis.set_ylim(0, 1)
        axis.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    for bar, value in zip(bars, values, strict=True):
        label = f"{value:.1%}" if percent else f"{value:.3f}"
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            label,
            ha="center",
            va="bottom",
        )
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    pyplot.close(figure)


def _render_safety_findings(
    pyplot: Any, output: Path, summaries: dict[str, dict[str, Any]]
) -> None:
    severities = sorted(
        {
            severity
            for summary in summaries.values()
            for severity in summary["safety_findings"]["by_severity"]
        }
    )
    figure, axis = pyplot.subplots(figsize=(7, 4.5))
    bottoms = [0] * len(summaries)
    names = list(summaries)
    for severity in severities:
        values = [
            summary["safety_findings"]["by_severity"].get(severity, 0)
            for summary in summaries.values()
        ]
        axis.bar(names, values, bottom=bottoms, label=severity)
        bottoms = [bottom + value for bottom, value in zip(bottoms, values, strict=True)]
    axis.set_title("Safety Findings by Severity")
    axis.set_ylabel("Findings")
    if severities:
        axis.legend(title="Severity")
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    pyplot.close(figure)


def _render_latency(pyplot: Any, output: Path, summaries: dict[str, dict[str, Any]]) -> None:
    names = list(summaries)
    measures = ("mean", "p50", "p95")
    positions = list(range(len(names)))
    width = 0.24
    figure, axis = pyplot.subplots(figsize=(7, 4.5))
    for index, measure in enumerate(measures):
        values = [summary["latency_ms"][measure] for summary in summaries.values()]
        offsets = [position + (index - 1) * width for position in positions]
        axis.bar(offsets, values, width, label=measure)
    axis.set_title("Benchmark Latency")
    axis.set_ylabel("Milliseconds")
    axis.set_xticks(positions, names)
    axis.legend(title="Metric")
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    pyplot.close(figure)


def render_charts(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Create Phase 3 PNG charts from values already present in *report*."""
    _, pyplot = _plot_modules()
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = _engine_summaries(report)
    names = list(summaries)
    charts = {name: output_dir / filename for name, filename in CHART_FILENAMES.items()}

    _save_bar_chart(
        pyplot, charts["coverage"], "Benchmark Coverage", names,
        [summary["coverage"] for summary in summaries.values()], "Coverage", percent=True,
    )
    _render_latency(pyplot, charts["latency"], summaries)
    _save_bar_chart(
        pyplot, charts["blocked_rate"], "Blocked Recommendation Rate", names,
        [summary["blocked_rate"] for summary in summaries.values()], "Blocked rate", percent=True,
    )
    _render_safety_findings(pyplot, charts["safety_findings"], summaries)

    adversarial = report["adversarial_test_summary"]
    _save_bar_chart(
        pyplot, charts["adversarial_pass_rate"], "Adversarial Pass Rate", ["golden suite"],
        [adversarial["passed"] / adversarial["checks"] if adversarial["checks"] else 0.0],
        "Pass rate", percent=True,
    )

    provenance = report.get("provenance_statistics")
    if provenance is not None:
        _save_bar_chart(
            pyplot, charts["provenance_coverage"], "Provenance Coverage", ["assignments"],
            [provenance["assignment_citation_rate"]], "Citation coverage", percent=True,
        )
    else:
        charts.pop("provenance_coverage")
    return charts


def markdown_summary(charts: dict[str, Path], output_dir: Path) -> str:
    """Render a compact Markdown index for the generated charts."""
    lines = ["# Phase 3 evaluation visualizations", ""]
    for chart_name, chart_path in charts.items():
        title = chart_name.replace("_", " ").title()
        lines.append(f"- {title}: ![]({chart_path.relative_to(output_dir)})")
    return "\n".join(lines) + "\n"


def write_visualization_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write charts and their Markdown index to ``output_dir``."""
    charts = render_charts(report, output_dir)
    (output_dir / "phase_3_visualization_summary.md").write_text(
        markdown_summary(charts, output_dir), encoding="utf-8"
    )
    return charts


def main() -> None:
    """Render Phase 3 visualizations from an existing experiment-report JSON file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Existing experiment_report.json file.")
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    charts = write_visualization_report(report, args.output_dir)
    print(f"Wrote {len(charts)} charts and phase_3_visualization_summary.md to {args.output_dir}")


if __name__ == "__main__":
    main()
