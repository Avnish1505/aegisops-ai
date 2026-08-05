"""Detect functions whose body is only a scaffold marker, never an implementation.

A function is flagged when its entire body is exactly one of:

- ``pass``
- ``...``
- a docstring, and nothing else
- ``raise NotImplementedError()`` (with or without a call/message)

No other body shapes are classified.
"""

from __future__ import annotations

import ast

from aegisops.integrity_analyzer.models import ParsedModule, ScaffoldClassification, ScaffoldFinding


def detect_scaffolded_functions(parsed: ParsedModule) -> list[ScaffoldFinding]:
    """Return a finding for every function/method in ``parsed`` that is only scaffolded."""
    findings: list[ScaffoldFinding] = []
    for node in ast.walk(parsed.tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        classification = _classify_body(node.body)
        if classification is not None:
            findings.append(
                ScaffoldFinding(
                    function=node.name,
                    line=node.lineno,
                    classification=classification,
                    file=parsed.source.path,
                )
            )
    return findings


def _classify_body(body: list[ast.stmt]) -> ScaffoldClassification | None:
    """Classify a function body as a scaffold marker, or return ``None`` if implemented."""
    if len(body) != 1:
        return None
    (statement,) = body

    if isinstance(statement, ast.Pass):
        return ScaffoldClassification.PASS

    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
        value = statement.value.value
        if value is Ellipsis:
            return ScaffoldClassification.ELLIPSIS
        if isinstance(value, str):
            return ScaffoldClassification.DOCSTRING_ONLY
        return None

    if isinstance(statement, ast.Raise) and _is_not_implemented_error(statement.exc):
        return ScaffoldClassification.NOT_IMPLEMENTED

    return None


def _is_not_implemented_error(exc: ast.expr | None) -> bool:
    """Return ``True`` for ``raise NotImplementedError`` or ``raise NotImplementedError(...)``."""
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"
