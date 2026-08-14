"""Detect safety-critical functions that are defined but never wired into execution.

An AI coding agent will often write a guard — a gate, a validator, a
human-approval check — and then forget to actually call it from the code path
it was meant to protect. The guard exists, reads convincingly, and is simply
never wired in. This module looks for exactly that failure, from the AST of a
single file, using two heuristics:

- ``DEFINED_BUT_NEVER_CALLED``: a function named in the caller-supplied set of
  "safety-critical" names is defined in the file but its name never appears
  in any *other* function's call set. Nothing in the file ever invokes it.
- ``GUARDED_OP_BYPASSES_GATE``: a function whose own name, or the name of
  something it calls, matches a caller-supplied "critical operation" keyword
  (e.g. ``dispatch``, ``allocate``, ``execute``, ``commit``) never calls any
  of the safety-critical functions. The dangerous operation runs unguarded.

Both the safety-critical function names and the operation keywords are
supplied by the caller; nothing is hardcoded here.

Limitations (read before trusting a clean report)
---------------------------------------------------
This is intra-file static analysis only, built from a simple name-based call
map (``ast.Call`` nodes keyed by enclosing function). It has real, deliberate
gaps:

- **No cross-module call resolution.** A safety-critical function that is
  defined here but only ever called from another file is indistinguishable
  from one that is never called at all, and will be misreported as
  ``DEFINED_BUT_NEVER_CALLED``. Likewise, a guarded operation that calls its
  gate via an import from elsewhere in this codebase will not be credited.
- **No dynamic dispatch.** Calls made through a variable holding a function
  reference, ``getattr(obj, name)()``, decorator-swapped implementations, or
  a callback/handler registry are not resolved back to the name being
  invoked, and so are invisible to both checks.
- **No aliasing.** If a safety-critical function is rebound to another name
  (``gate = validate_safety_gate``) and called through that alias, the call
  is not attributed to the original name.
- **No control-flow or ordering analysis.** ``GUARDED_OP_BYPASSES_GATE``
  checks only whether a safety-critical function's name appears *anywhere*
  in the operation function's call set — not whether it actually executes,
  or executes before the critical operation. A gate called only inside a
  branch that never runs, or called after the dangerous operation, still
  counts as "wired in" by this heuristic.
- **No name-collision handling.** If two functions in the file share the
  same name (e.g. same-named methods on different classes), the call map
  keeps only the most recently walked one; the others are silently
  overwritten.

Treat findings as a lead for a human reviewer to confirm, not as proof that a
gate is (or is not) actually enforced.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from aegisops.integrity_analyzer.models import ParsedModule


class WiringFailureMode(StrEnum):
    """Which of the two wiring failures a :class:`WiringFinding` reports."""

    DEFINED_BUT_NEVER_CALLED = "defined_but_never_called"
    GUARDED_OP_BYPASSES_GATE = "guarded_op_bypasses_gate"


@dataclass(frozen=True)
class WiringFinding:
    """One safety-critical wiring failure found in a file."""

    function: str
    line: int
    failure_mode: WiringFailureMode
    reason: str
    file: Path


def check_safety_wiring(
    parsed: ParsedModule,
    *,
    safety_critical_names: Iterable[str],
    operation_keywords: Iterable[str],
) -> list[WiringFinding]:
    """Check ``parsed`` for unwired safety gates and gate-bypassing operations.

    ``safety_critical_names`` is the set of function names considered guards
    (gates, validators, approval checks). ``operation_keywords`` is the set
    of substrings identifying a "critical operation" (matched, case
    -insensitively, against an operation function's own name and the names
    it calls). See the module docstring for the exact rules and their
    limitations.
    """
    safety_critical_names = list(safety_critical_names)
    operation_keywords = list(operation_keywords)
    call_map = _build_call_map(parsed.tree)

    findings = _find_never_called(call_map, safety_critical_names, parsed.source.path)
    findings.extend(
        _find_bypassed_gates(
            call_map, safety_critical_names, operation_keywords, parsed.source.path
        )
    )
    return findings


def _build_call_map(tree: ast.Module) -> dict[str, tuple[int, set[str]]]:
    """Map each function name to its definition line and the set of names it calls.

    Calls made inside a nested function are folded into the enclosing
    function's call set, since this map is built per top-level ``ast.walk``
    over each function's own subtree (see module limitations).
    """
    call_map: dict[str, tuple[int, set[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        calls: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                calls.update(_called_name(inner))
        call_map[node.name] = (node.lineno, calls)
    return call_map


def _called_name(call: ast.Call) -> tuple[str, ...]:
    """Return the called function's name, for ``foo()`` and ``obj.method()`` shapes."""
    if isinstance(call.func, ast.Name):
        return (call.func.id,)
    if isinstance(call.func, ast.Attribute):
        return (call.func.attr,)
    return ()


def _find_never_called(
    call_map: dict[str, tuple[int, set[str]]],
    safety_critical_names: list[str],
    file: Path,
) -> list[WiringFinding]:
    """Flag safety-critical functions whose name is defined but called nowhere else."""
    findings: list[WiringFinding] = []
    for name in safety_critical_names:
        if name not in call_map:
            continue  # not defined in this file; nothing to check
        line, _ = call_map[name]
        called_elsewhere = any(
            name in calls for other_name, (_, calls) in call_map.items() if other_name != name
        )
        if called_elsewhere:
            continue
        findings.append(
            WiringFinding(
                function=name,
                line=line,
                failure_mode=WiringFailureMode.DEFINED_BUT_NEVER_CALLED,
                reason=(
                    f"'{name}' is defined as a safety-critical function but is never "
                    "called by any other function in this file."
                ),
                file=file,
            )
        )
    return findings


def _find_bypassed_gates(
    call_map: dict[str, tuple[int, set[str]]],
    safety_critical_names: list[str],
    operation_keywords: list[str],
    file: Path,
) -> list[WiringFinding]:
    """Flag critical-operation functions that never call a safety-critical function."""
    safety_set = set(safety_critical_names)
    findings: list[WiringFinding] = []
    for name, (line, calls) in call_map.items():
        if name in safety_set:
            continue  # the gate itself is not a guarded operation
        matched_keywords = _matched_operation_keywords(name, calls, operation_keywords)
        if not matched_keywords:
            continue
        if calls & safety_set:
            continue  # at least one safety-critical function is called
        findings.append(
            WiringFinding(
                function=name,
                line=line,
                failure_mode=WiringFailureMode.GUARDED_OP_BYPASSES_GATE,
                reason=(
                    f"'{name}' matches critical-operation keyword(s) "
                    f"{', '.join(matched_keywords)} but never calls a safety-critical "
                    f"function ({', '.join(sorted(safety_set))}) in its body."
                ),
                file=file,
            )
        )
    return findings


def _matched_operation_keywords(
    name: str, calls: set[str], operation_keywords: list[str]
) -> list[str]:
    """Return the operation keywords found in ``name`` or the names in ``calls``."""
    haystacks = [name.lower(), *(call.lower() for call in calls)]
    return [
        keyword
        for keyword in operation_keywords
        if any(keyword.lower() in haystack for haystack in haystacks)
    ]
