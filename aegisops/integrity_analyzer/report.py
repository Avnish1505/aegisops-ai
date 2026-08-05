"""Render scaffold findings as structured reports.

Bundle 3 turns a list of :class:`ScaffoldFinding` into a report, in two
formats: a plain Python dict and a JSON string. No detection rules or CLI
are introduced here.
"""

from __future__ import annotations

import json

from aegisops.integrity_analyzer.models import ScaffoldFinding


def build_report(findings: list[ScaffoldFinding]) -> dict[str, object]:
    """Build a structured report, as a plain Python dict, from scaffold findings."""
    return {
        "total_findings": len(findings),
        "findings": [_finding_to_dict(finding) for finding in findings],
    }


def json_report(report: dict[str, object], *, indent: int | None = 2) -> str:
    """Render a report built by :func:`build_report` as a JSON string."""
    return json.dumps(report, indent=indent)


def _finding_to_dict(finding: ScaffoldFinding) -> dict[str, object]:
    """Convert one finding into JSON-safe primitives (``Path`` and enum included)."""
    return {
        "function": finding.function,
        "line": finding.line,
        "classification": finding.classification.value,
        "file": str(finding.file),
    }
