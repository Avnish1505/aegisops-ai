"""Summarise the user study: per-interface medians, correct and catch rates, paired comparison.

    python scripts/analyze_study.py reports/raw/user_study.csv

Reads the CSV exported from /study (aegisops/study/results.py) and writes reports/user_study.md
and reports/user_study.json. The analysis is descriptive: with the small samples a study like
this produces, it reports counts, medians and each participant's paired difference, and computes
an exact sign test only when at least MIN_FOR_TEST participants finished both interfaces. It
makes no claim the numbers do not show.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from math import comb
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UIS = ("legacy", "console")
UI_NAME = {"legacy": "old console (v0-ui)", "console": "new console (M3)"}
MIN_FOR_TEST = 5


def load(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row["action"]]  # decided tasks only


def _rate(hits: list[bool]) -> dict[str, Any]:
    return {"k": sum(hits), "n": len(hits), "value": sum(hits) / len(hits) if hits else None}


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def sign_test(differences: list[float]) -> float | None:
    """Two-sided exact sign test on non-zero differences; None below MIN_FOR_TEST."""
    nonzero = [d for d in differences if d != 0]
    if len(nonzero) < MIN_FOR_TEST:
        return None
    n, k = len(nonzero), sum(d > 0 for d in nonzero)
    tail = sum(comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2**n
    return min(1.0, 2 * tail)


def analyse(rows: list[dict[str, str]]) -> dict[str, Any]:
    by_ui: dict[str, list[dict[str, str]]] = {ui: [r for r in rows if r["ui"] == ui] for ui in UIS}
    per_ui = {}
    for ui, ui_rows in by_ui.items():
        injected = [r for r in ui_rows if r["injected_error"]]
        times = [float(r["time_to_decision_s"]) for r in ui_rows if r["time_to_decision_s"]]
        per_ui[ui] = {
            "decisions": len(ui_rows),
            "participants": len({r["participant"] for r in ui_rows}),
            "median_time_s": _median(times),
            "time_quartiles_s": statistics.quantiles(times, n=4) if len(times) >= 2 else None,
            "correct": _rate([r["correct"] == "True" for r in ui_rows]),
            "caught": _rate([r["caught"] == "True" for r in injected]),
            "caught_by_error": {
                error: _rate([r["caught"] == "True" for r in injected
                              if r["injected_error"] == error])
                for error in sorted({r["injected_error"] for r in injected})
            },
        }
    Rows = list[dict[str, str]]
    participants: dict[str, dict[str, Rows]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        participants[row["participant"]][row["ui"]].append(row)
    paired = []
    for participant, uis in sorted(participants.items()):
        if not all(uis.get(ui) for ui in UIS):
            continue
        medians = {ui: _median([float(r["time_to_decision_s"]) for r in uis[ui]
                                if r["time_to_decision_s"]]) for ui in UIS}
        caught = {ui: sum(r["caught"] == "True" for r in uis[ui]) for ui in UIS}
        paired.append({
            "participant": participant,
            "first_ui": min(uis[UIS[0]] + uis[UIS[1]], key=lambda r: int(r["order"]))["ui"],
            "median_time_legacy_s": medians["legacy"],
            "median_time_console_s": medians["console"],
            "difference_s": None if None in medians.values()
            else round(medians["console"] - medians["legacy"], 1),  # type: ignore[operator]
            "caught_legacy": caught["legacy"],
            "caught_console": caught["console"],
        })
    differences = [p["difference_s"] for p in paired if p["difference_s"] is not None]
    return {
        "report": "user_study",
        "participants": len(participants),
        "paired_participants": len(paired),
        "per_ui": per_ui,
        "paired": paired,
        "paired_summary": {
            "median_difference_s": _median(differences),
            "faster_in_console": sum(d < 0 for d in differences),
            "faster_in_legacy": sum(d > 0 for d in differences),
            "sign_test_p": sign_test(differences),
            "min_participants_for_test": MIN_FOR_TEST,
        },
    }


def _pct(rate: dict[str, Any]) -> str:
    return "n/a" if rate["value"] is None else f"{rate['k']}/{rate['n']} ({rate['value']:.0%})"


def _s(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f} s"


def markdown(result: dict[str, Any], source: str) -> str:
    n, paired = result["participants"], result["paired_participants"]
    lines = [
        "# User study: old console vs new console",
        "",
        f"Source: `{source}` (exported from `/study`), analysed by `scripts/analyze_study.py`. "
        "Protocol: [docs/USER_STUDY.md](../docs/USER_STUDY.md).",
        "",
        f"**n = {n} participant(s), {paired} with both interfaces.** This is a small, "
        "non-representative sample from the project's circle, not emergency-operations staff. "
        "Nothing here generalises beyond these sessions.",
        "",
        "| Measure | " + " | ".join(UI_NAME[ui] for ui in UIS) + " |",
        "| --- | --- | --- |",
    ]
    per_ui = result["per_ui"]
    for label, cell in (
        ("Decisions recorded", lambda ui: str(per_ui[ui]["decisions"])),
        ("Median time to decision", lambda ui: _s(per_ui[ui]["median_time_s"])),
        ("Correct action", lambda ui: _pct(per_ui[ui]["correct"])),
        ("Injected errors caught (rejected with the right reason code)",
         lambda ui: _pct(per_ui[ui]["caught"])),
    ):
        lines.append(f"| {label} | " + " | ".join(cell(ui) for ui in UIS) + " |")
    errors = sorted({e for ui in UIS for e in per_ui[ui]["caught_by_error"]})
    for error in errors:
        lines.append(f"| … {error.replace('_', ' ')} | " + " | ".join(
            _pct(per_ui[ui]["caught_by_error"].get(error, {"k": 0, "n": 0, "value": None}))
            for ui in UIS) + " |")
    summary = result["paired_summary"]
    lines += [
        "",
        "## Paired comparison (per participant, median time per interface)",
        "",
        "| Participant | First interface | Old console | New console | New − old "
        "| Caught (old / new) |",
        "| --- | --- | --- | --- | --- | --- |",
        *[
            f"| {p['participant']} | {UI_NAME[p['first_ui']]} | {_s(p['median_time_legacy_s'])} | "
            f"{_s(p['median_time_console_s'])} | {_s(p['difference_s'])} | "
            f"{p['caught_legacy']} / {p['caught_console']} |"
            for p in result["paired"]
        ],
        "",
        f"Median paired difference (new − old): {_s(summary['median_difference_s'])}; faster in "
        f"the new console: {summary['faster_in_console']}, in the old: "
        f"{summary['faster_in_legacy']}.",
        (f"Exact two-sided sign test on the paired differences: p = {summary['sign_test_p']:.3f}."
         if summary["sign_test_p"] is not None else
         f"No significance test: fewer than {MIN_FOR_TEST} participants with non-zero paired "
         "differences."),
        "",
        "Both interfaces show the verifier's findings, so a high 'correct' rate in both is "
        "expected; time and naming the error are the informative measures. Interface look and "
        "function differ together and are not separated.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "user_study")
    args = parser.parse_args()
    if not args.csv.exists():
        sys.exit(f"{args.csv} not found: export it from /study first.")
    rows = load(args.csv)
    if not rows:
        sys.exit("No decided tasks in the CSV; nothing to analyse.")
    result = analyse(rows)
    resolved = args.csv.resolve()
    source = str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(args.csv)
    result["source"] = source
    args.out.with_suffix(".json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    args.out.with_suffix(".md").write_text(markdown(result, source), encoding="utf-8")
    print(f"wrote {args.out}.md and .json (n = {result['participants']})")


if __name__ == "__main__":
    main()
