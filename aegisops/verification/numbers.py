"""Read numeric claims back out of a text draft and compare them with the plan's state.

A draft is split into lines, and lines into clauses (``;`` or sentence end). Each number must be
attributed to the keyword directly before it (at most two tokens back, within its clause). The
keyword, the resource ID in the clause and the incident ID on the line decide which fact the
number claims. A number with no attributable keyword fails: an unverifiable number never
reaches an operator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from aegisops.domain.models import DecisionResult, ResourceType, Scenario, Severity
from aegisops.planning.objective import plan_coverage
from aegisops.planning.travel import TravelTimeMatrix

TOKEN = re.compile(r"[A-Za-z0-9_-]+(?:\.\d+)?")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
CLAUSE_BREAK = re.compile(r";|\.(?=\s|$)")
KEYWORDS = {"incidents", "critical", "available", "assigned", "unmet", "coverage", "eta"}
MAX_KEYWORD_DISTANCE = 2


@dataclass(frozen=True, slots=True)
class NumberMismatch:
    line: int
    written: str
    expected: str | None  # None when the number could not be attributed to any fact
    claim: str

    def describe(self) -> str:
        if self.expected is None:
            return f"line {self.line}: {self.written} is not attributable to a known fact"
        return f"line {self.line}: {self.claim} is {self.expected}, draft says {self.written}"


def number_mismatches(
    text: str, plan: DecisionResult, scenario: Scenario, travel_times: TravelTimeMatrix
) -> list[NumberMismatch]:
    incident_ids = {incident.id for incident in scenario.incidents}
    resource_ids = {resource.id for resource in scenario.resources}
    identifiers = incident_ids | resource_ids | {scenario.scenario_id}
    type_names = {resource_type.value for resource_type in ResourceType}
    facts = _global_facts(plan, scenario)
    unmet = {
        (item.incident_id, item.resource_type.value): item.quantity
        for item in plan.unmet_requirements
    }

    mismatches: list[NumberMismatch] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        line_tokens = TOKEN.findall(line)
        line_incident = next((token for token in line_tokens if token in incident_ids), None)
        for clause in CLAUSE_BREAK.split(line):
            tokens = TOKEN.findall(clause)
            resource = next((token for token in tokens if token in resource_ids), None)
            for index, token in enumerate(tokens):
                if token in identifiers or not NUMBER.fullmatch(token):
                    continue
                keyword = _keyword_before(tokens, index)
                expected: Decimal | int | None = None
                claim = keyword or "number"
                if keyword == "eta" and resource and line_incident:
                    expected_minutes = travel_times.get(resource, line_incident)
                    expected = None if expected_minutes is None else Decimal(str(expected_minutes))
                    claim = f"ETA {resource}->{line_incident}"
                elif keyword == "unmet" and line_incident:
                    following = tokens[index + 1] if index + 1 < len(tokens) else ""
                    if following in type_names:
                        expected = unmet.get((line_incident, following), 0)
                        claim = f"unmet {following} at {line_incident}"
                elif keyword in facts and not (keyword == "unmet" and line_incident):
                    expected = facts[keyword]
                if expected is None:
                    mismatches.append(NumberMismatch(line_number, token, None, claim))
                elif not _equal_at_written_precision(token, expected):
                    mismatches.append(NumberMismatch(line_number, token, str(expected), claim))
    return mismatches


def _global_facts(plan: DecisionResult, scenario: Scenario) -> dict[str, Decimal | int]:
    return {
        "incidents": len(scenario.incidents),
        "critical": sum(incident.severity == Severity.CRITICAL for incident in scenario.incidents),
        "available": sum(resource.available for resource in scenario.resources),
        "assigned": len(plan.assignments),
        "unmet": sum(item.quantity for item in plan.unmet_requirements),
        "coverage": Decimal(str(plan_coverage(plan.assignments, scenario))) * 100,
    }


def _keyword_before(tokens: list[str], index: int) -> str | None:
    for back in range(1, MAX_KEYWORD_DISTANCE + 1):
        if index - back < 0:
            return None
        candidate = tokens[index - back].lower()
        if candidate in KEYWORDS:
            return candidate
    return None


def _equal_at_written_precision(written: str, expected: Decimal | int) -> bool:
    """True when ``written`` is a correct rounding of ``expected`` to the digits it shows."""
    places = len(written.split(".")[1]) if "." in written else 0
    half_unit = Decimal(1).scaleb(-places) / 2
    return abs(Decimal(written) - Decimal(str(expected))) <= half_unit + Decimal("1e-9")
