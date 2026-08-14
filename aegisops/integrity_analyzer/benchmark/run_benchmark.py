"""Score the Implementation Integrity Analyzer against a labeled scenario corpus.

Run as: ``python -m aegisops.integrity_analyzer.benchmark.run_benchmark``

What "the analyzer" means here
-------------------------------
This harness treats "the analyzer" as the union of the three detector
modules built so far, run over each scenario file and combined into one
per-file verdict:

- ``scaffold_detector.detect_scaffolded_functions`` -> ``"scaffolded"`` if it
  finds anything.
- ``wiring_checker.check_safety_wiring`` -> the ``failure_mode`` of each
  finding it produces (``"defined_but_never_called"`` /
  ``"guarded_op_bypasses_gate"``), using the ``safety_critical_names`` and
  ``operation_keywords`` recorded per scenario in ``labels.json``.
- the intent/code consistency pipeline (``intent_parser`` ->
  ``identifier_extractor`` -> ``keyword_matcher`` -> ``consistency_report``)
  -> ``"intent_mismatch"`` if the consistency score falls below
  :data:`INTENT_CONSISTENCY_THRESHOLD`.

That threshold, and the decision to use each scenario file's own module
docstring as its "intent" text, are choices made by *this benchmark*, not by
the intent-consistency module itself: ``consistency_report.build_consistency_report``
only ever produces a continuous score, never a flag. Turning that score into
a binary "mismatch or not" decision is a harness-level policy, so it lives
here rather than pretending to be a fourth built-in detector.

None of the three detector modules are modified, patched, or monkeypatched
by this file — it only calls their public functions.

Scoring methodology
--------------------
Ground truth in ``labels.json`` is a list of *expected* finding categories
per file (empty list == "clean"). The naive baseline can only ever produce a
single binary signal ("a configured name is missing from the text" or not),
so for a fair head-to-head, both approaches are scored as **file-level binary
classifiers**: did this approach raise *any* concern about this file, or not?
Per-category detail (which specific findings each approach produced) is kept
in the per-scenario table and in ``results.json`` for transparency, but is
not separately counted in the headline confusion matrix.

Honesty note
------------
The five "hard" scenarios are labeled with the *ideal* ground truth, not
with whatever the analyzer happens to output. Several are expected, and
documented in ``labels.json``, to make the analyzer wrong in one direction or
the other (false positive or false negative) because of limitations the
detector modules already disclose in their own docstrings (no aliasing, no
transitive call resolution, no decorator awareness, no control-flow
analysis). This script does not special-case, exclude, or re-weight those
scenarios to hide that — they count against the analyzer's metrics exactly
like any other scenario.
"""

from __future__ import annotations

import ast
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

from aegisops.integrity_analyzer.api import analyze_file
from aegisops.integrity_analyzer.benchmark.naive_baseline import naive_grep_baseline
from aegisops.integrity_analyzer.consistency_report import build_consistency_report
from aegisops.integrity_analyzer.identifier_extractor import extract_identifiers
from aegisops.integrity_analyzer.intent_parser import parse_intent
from aegisops.integrity_analyzer.keyword_matcher import match_keywords
from aegisops.integrity_analyzer.scaffold_detector import detect_scaffolded_functions
from aegisops.integrity_analyzer.wiring_checker import check_safety_wiring

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
LABELS_PATH = SCENARIOS_DIR / "labels.json"
RESULTS_PATH = Path(__file__).parent / "results.json"

# Harness-level decision boundary for turning a continuous consistency score
# into a binary "intent_mismatch" flag. See module docstring.
INTENT_CONSISTENCY_THRESHOLD = 0.4

INTENT_MISMATCH_FINDING = "intent_mismatch"
SCAFFOLDED_FINDING = "scaffolded"


class ScenarioLabel(TypedDict):
    """One entry from ``labels.json``: a scenario file's ground truth and config.

    ``labels.json`` entries may carry additional documentation-only keys
    (``known_limitation``, ``note``) that this harness never reads; they are
    intentionally omitted here.
    """

    category: str
    description: str
    expected_findings: list[str]
    safety_critical_names: list[str]
    operation_keywords: list[str]


class ConsistencyReport(TypedDict):
    """The shape returned by ``consistency_report.build_consistency_report``."""

    matched_keywords: list[str]
    unmatched_keywords: list[str]
    consistency_score: float


@dataclass(frozen=True)
class ScenarioResult:
    """One scenario's ground truth alongside both approaches' verdicts."""

    filename: str
    category: str
    description: str
    expected_findings: list[str]
    analyzer_findings: list[str]
    baseline_findings: list[str]

    @property
    def expected_positive(self) -> bool:
        return bool(self.expected_findings)

    @property
    def analyzer_positive(self) -> bool:
        return bool(self.analyzer_findings)

    @property
    def baseline_positive(self) -> bool:
        return bool(self.baseline_findings)


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0

    def precision(self) -> float | None:
        denom = self.true_positives + self.false_positives
        return (self.true_positives / denom) if denom else None

    def recall(self) -> float | None:
        denom = self.true_positives + self.false_negatives
        return (self.true_positives / denom) if denom else None

    def mcc(self) -> float:
        tp, fp, fn, tn = (
            self.true_positives,
            self.false_positives,
            self.false_negatives,
            self.true_negatives,
        )
        denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        if denom == 0:
            return 0.0
        return (tp * tn - fp * fn) / denom

    def as_dict(self) -> dict[str, object]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": self.precision(),
            "recall": self.recall(),
            "mcc": round(self.mcc(), 4),
        }


def load_labels() -> dict[str, ScenarioLabel]:
    """Load the scenario ground truth from ``labels.json``."""
    raw: object = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    return cast(dict[str, ScenarioLabel], raw)


def run_analyzer(path: Path, config: ScenarioLabel) -> list[str]:
    """Run the scaffold detector, wiring checker, and intent-consistency check on one file."""
    parsed = analyze_file(path)
    findings: list[str] = []

    if detect_scaffolded_functions(parsed):
        findings.append(SCAFFOLDED_FINDING)

    wiring_findings = check_safety_wiring(
        parsed,
        safety_critical_names=config["safety_critical_names"],
        operation_keywords=config["operation_keywords"],
    )
    findings.extend(sorted({finding.failure_mode.value for finding in wiring_findings}))

    intent_text = ast.get_docstring(parsed.tree) or ""
    if intent_text.strip():
        keywords = parse_intent(intent_text)
        identifiers = extract_identifiers(parsed)
        matched, unmatched = match_keywords(keywords, identifiers)
        report = cast(ConsistencyReport, build_consistency_report(matched, unmatched))
        if report["consistency_score"] < INTENT_CONSISTENCY_THRESHOLD:
            findings.append(INTENT_MISMATCH_FINDING)

    return findings


def run_scenario(filename: str, config: ScenarioLabel) -> ScenarioResult:
    path = SCENARIOS_DIR / filename
    analyzer_findings = run_analyzer(path, config)
    baseline_findings = naive_grep_baseline(path, config["safety_critical_names"])

    return ScenarioResult(
        filename=filename,
        category=config["category"],
        description=config["description"],
        expected_findings=list(config["expected_findings"]),
        analyzer_findings=analyzer_findings,
        baseline_findings=baseline_findings,
    )


def score(results: list[ScenarioResult], *, predicted: str) -> ConfusionMatrix:
    """Build a confusion matrix for one approach ('analyzer' or 'baseline')."""
    tp = fp = fn = tn = 0
    for result in results:
        actual = result.expected_positive
        guess = result.analyzer_positive if predicted == "analyzer" else result.baseline_positive
        if actual and guess:
            tp += 1
        elif not actual and guess:
            fp += 1
        elif actual and not guess:
            fn += 1
        else:
            tn += 1
    return ConfusionMatrix(
        true_positives=tp, false_positives=fp, false_negatives=fn, true_negatives=tn
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def print_per_scenario_table(results: list[ScenarioResult]) -> None:
    header = f"{'Scenario':<42} {'Category':<14} {'Expected':<10} {'Analyzer':<10} {'Baseline':<10}"
    print(header)
    print("-" * len(header))
    for result in results:
        expected = "positive" if result.expected_positive else "clean"
        analyzer = "positive" if result.analyzer_positive else "clean"
        baseline = "positive" if result.baseline_positive else "clean"
        marker = " " if analyzer == expected else " *"
        print(
            f"{result.filename:<42} {result.category:<14} {expected:<10} "
            f"{analyzer:<10} {baseline:<10}{marker}"
        )
    print("(* marks a scenario where the analyzer's verdict disagrees with ground truth)")


def print_comparison_table(baseline: ConfusionMatrix, analyzer: ConfusionMatrix) -> None:
    rows = [
        ("True Positives", baseline.true_positives, analyzer.true_positives),
        ("False Positives", baseline.false_positives, analyzer.false_positives),
        ("False Negatives", baseline.false_negatives, analyzer.false_negatives),
        ("True Negatives", baseline.true_negatives, analyzer.true_negatives),
        ("Precision", _fmt(baseline.precision()), _fmt(analyzer.precision())),
        ("Recall", _fmt(baseline.recall()), _fmt(analyzer.recall())),
        ("MCC", f"{baseline.mcc():.3f}", f"{analyzer.mcc():.3f}"),
    ]
    header = f"{'Metric':<18} {'Naive Baseline':<16} {'Analyzer':<16}"
    print(header)
    print("-" * len(header))
    for label, base_value, analyzer_value in rows:
        print(f"{label:<18} {str(base_value):<16} {str(analyzer_value):<16}")


def build_results_payload(
    results: list[ScenarioResult], baseline: ConfusionMatrix, analyzer: ConfusionMatrix
) -> dict[str, object]:
    return {
        "scenario_count": len(results),
        "intent_consistency_threshold": INTENT_CONSISTENCY_THRESHOLD,
        "scenarios": [
            {
                "filename": r.filename,
                "category": r.category,
                "description": r.description,
                "expected_findings": r.expected_findings,
                "analyzer_findings": r.analyzer_findings,
                "baseline_findings": r.baseline_findings,
                "expected_positive": r.expected_positive,
                "analyzer_positive": r.analyzer_positive,
                "baseline_positive": r.baseline_positive,
                "analyzer_correct": r.analyzer_positive == r.expected_positive,
                "baseline_correct": r.baseline_positive == r.expected_positive,
            }
            for r in results
        ],
        "metrics": {
            "naive_baseline": baseline.as_dict(),
            "analyzer": analyzer.as_dict(),
        },
    }


def main() -> None:
    labels = load_labels()
    results = [run_scenario(filename, config) for filename, config in labels.items()]

    by_category: dict[str, int] = {}
    for result in results:
        by_category[result.category] = by_category.get(result.category, 0) + 1

    print("Implementation Integrity Analyzer -- Benchmark Results")
    print("=" * 56)
    print(
        f"Scenarios: {len(results)} "
        f"({by_category.get('true_positive', 0)} true-positive, "
        f"{by_category.get('clean', 0)} clean, "
        f"{by_category.get('hard', 0)} hard)"
    )
    print()
    print_per_scenario_table(results)
    print()

    baseline_matrix = score(results, predicted="baseline")
    analyzer_matrix = score(results, predicted="analyzer")
    print_comparison_table(baseline_matrix, analyzer_matrix)

    payload = build_results_payload(results, baseline_matrix, analyzer_matrix)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
