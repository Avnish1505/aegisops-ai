"""Scoring and bootstrap confidence intervals for the eval harness.

Every interval is a 95% percentile bootstrap over the evaluated items (reports, notes or
scenarios), resampled with replacement ``BOOTSTRAP_ROUNDS`` times from a fixed seed, so re-running
on the same outputs gives the same numbers.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from aegisops.domain.models import Location
from aegisops.domain.policy import haversine_km

BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 20260923
LOCATION_TOLERANCE_KM = 1.0
FIELDS = ("incident_type", "location", "people_count", "needs", "signals")


@dataclass(frozen=True)
class Estimate:
    value: float | None
    low: float | None
    high: float | None
    n: int

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "ci95": [self.low, self.high], "n": self.n}

    def fmt(self, percent: bool = True, digits: int = 1) -> str:
        if self.value is None:
            return "n/a"
        scale = 100 if percent else 1
        unit = "%" if percent else ""
        return (
            f"{self.value * scale:.{digits}f}{unit} "
            f"[{(self.low or 0) * scale:.{digits}f}, {(self.high or 0) * scale:.{digits}f}]"
        )


def bootstrap(items: Sequence[Any], statistic: Callable[[Sequence[Any]], float | None],
              rounds: int = BOOTSTRAP_ROUNDS, seed: int = BOOTSTRAP_SEED) -> Estimate:
    if not items:
        return Estimate(None, None, None, 0)
    point = statistic(items)
    rng = random.Random(seed)
    samples = []
    for _ in range(rounds):
        value = statistic([items[rng.randrange(len(items))] for _ in items])
        if value is not None:
            samples.append(value)
    if point is None or not samples:
        return Estimate(point, None, None, len(items))
    samples.sort()
    return Estimate(point, samples[int(0.025 * len(samples))],
                    samples[min(len(samples) - 1, int(0.975 * len(samples)))], len(items))


def quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


# --- Reader field scoring -------------------------------------------------------------------
def location_error_km(
    gold: dict[str, Any] | None, predicted: dict[str, Any] | None
) -> float | None:
    if gold is None or predicted is None:
        return None
    return haversine_km(Location(lat=gold["lat"], lon=gold["lon"]),
                        Location(lat=predicted["lat"], lon=predicted["lon"]))


def field_counts(gold: dict[str, Any], candidate: dict[str, Any] | None,
                 labelled: Sequence[str]) -> dict[str, Counter[str]]:
    """Per-field true/false positives and false negatives for one report.

    A failed read (no candidate) predicts nothing. A wrong scalar value is both a false positive
    and a false negative. Location is correct within ``LOCATION_TOLERANCE_KM`` of the gold point.
    """
    counts: dict[str, Counter[str]] = {name: Counter() for name in FIELDS if name in labelled}
    candidate = candidate or {}

    def scalar(name: str, gold_value: Any, predicted: Any, correct: bool) -> None:
        if name not in counts:
            return
        if predicted is not None and correct:
            counts[name]["tp"] += 1
            return
        if predicted is not None:
            counts[name]["fp"] += 1
        if gold_value is not None:
            counts[name]["fn"] += 1

    predicted_type = (candidate.get("incident_type") or {}).get("value")
    scalar("incident_type", gold.get("incident_type"), predicted_type,
           predicted_type is not None and predicted_type == gold.get("incident_type"))
    error = location_error_km(gold.get("location"), candidate.get("geocode"))
    scalar("location", gold.get("location"), candidate.get("geocode"),
           error is not None and error <= LOCATION_TOLERANCE_KM)
    predicted_people = (candidate.get("people_count") or {}).get("value")
    scalar("people_count", gold.get("people_count"), predicted_people,
           predicted_people is not None and predicted_people == gold.get("people_count"))
    for name, gold_items, predicted_items in (
        ("needs",
         Counter((n["resource_type"], n["quantity"]) for n in gold.get("needs", [])),
         Counter((n["resource_type"], n["quantity"]) for n in candidate.get("needs", []))),
        ("signals",
         Counter(gold.get("signals", [])),
         Counter(s["signal"] for s in candidate.get("signals", []))),
    ):
        if name in counts:
            counts[name]["tp"] += sum((gold_items & predicted_items).values())
            counts[name]["fp"] += sum((predicted_items - gold_items).values())
            counts[name]["fn"] += sum((gold_items - predicted_items).values())
    return counts


def prf(counts: Sequence[Counter[str]]) -> tuple[float | None, float | None, float | None]:
    tp = sum(c["tp"] for c in counts)
    fp = sum(c["fp"] for c in counts)
    fn = sum(c["fn"] for c in counts)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and precision + recall else None)
    return precision, recall, f1


def field_report(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """rows: [{"counts": {field: Counter}}]; returns P/R/F1 with CIs per field."""
    report: dict[str, dict[str, Any]] = {}
    for name in FIELDS:
        scored = [row["counts"][name] for row in rows if name in row["counts"]]
        if not scored:
            continue
        report[name] = {
            "precision": bootstrap(scored, lambda s: prf(s)[0]).as_dict(),
            "recall": bootstrap(scored, lambda s: prf(s)[1]).as_dict(),
            "f1": bootstrap(scored, lambda s: prf(s)[2]).as_dict(),
        }
    return report


def mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None
