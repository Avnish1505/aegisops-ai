"""Extract identifiers from a parsed Python module using ``ast.walk``.

This is a standalone stage: it walks an already-parsed AST and collects the
names that describe what the code *does* — function definitions, calls,
imports, assigned variables, and classes — into a single set. Nothing here
compares those names against an intent or produces a score; that is later
work.
"""

from __future__ import annotations

import ast

from aegisops.integrity_analyzer.models import ParsedModule


def extract_identifiers(parsed: ParsedModule) -> set[str]:
    """Return the unique set of identifiers found in ``parsed``.

    Collects, via a single ``ast.walk`` pass over the module tree:

    - function names (``def``/``async def``)
    - called function names (``foo()`` and ``obj.method()``)
    - imported names (``import x``, ``from x import y``, honoring ``as``)
    - variable names (assignment targets)
    - class names
    """
    identifiers: set[str] = set()

    for node in ast.walk(parsed.tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            identifiers.add(node.name)
        elif isinstance(node, ast.ClassDef):
            identifiers.add(node.name)
        elif isinstance(node, ast.Call):
            identifiers.update(_called_name(node))
        elif isinstance(node, ast.Import):
            identifiers.update(_imported_names(node))
        elif isinstance(node, ast.ImportFrom):
            identifiers.update(_imported_from_names(node))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            identifiers.add(node.id)

    return identifiers


def _called_name(call: ast.Call) -> tuple[str, ...]:
    """Return the called function's name, for ``foo()`` and ``obj.method()`` shapes."""
    if isinstance(call.func, ast.Name):
        return (call.func.id,)
    if isinstance(call.func, ast.Attribute):
        return (call.func.attr,)
    return ()


def _imported_names(node: ast.Import) -> tuple[str, ...]:
    """Return the bound names from ``import x``/``import x as y`` (dotted paths trimmed)."""
    return tuple(alias.asname or alias.name.split(".")[0] for alias in node.names)


def _imported_from_names(node: ast.ImportFrom) -> tuple[str, ...]:
    """Return the bound names from ``from x import y``/``from x import y as z``."""
    return tuple(alias.asname or alias.name for alias in node.names)
