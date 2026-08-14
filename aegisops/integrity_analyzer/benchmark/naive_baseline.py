"""A deliberately naive baseline: does the safety-critical name appear at all?

No AST, no parsing, no call graph — just ``name in raw_text``. This exists so
the benchmark has something honest to compare the analyzer against: a
baseline that a reviewer might reach for first ("grep for the gate name"),
and that plausibly looks reasonable until you notice what it actually can't
distinguish.

Specifically, this baseline cannot tell a *definition* from a *call*: a
function's own ``def validate_safety_gate(...):`` line already contains the
string ``"validate_safety_gate"``, so once a gate is defined anywhere in the
file, this baseline considers it "present" and never raises a wiring concern
about it — regardless of whether anything actually calls it. It has no
concept of scaffolding, call graphs, or intent at all, so it structurally
cannot detect the scaffolded-function or intent-mismatch failure modes; it
can only ever say "a configured name is completely missing from this file's
text", which is a much weaker claim than "this name is never called".
"""

from __future__ import annotations

from pathlib import Path

MISSING_GATE_FINDING = "missing_gate"


def naive_grep_baseline(path: Path, safety_critical_names: list[str]) -> list[str]:
    """Flag ``MISSING_GATE_FINDING`` if any name in ``safety_critical_names`` is
    completely absent from the file's raw text; otherwise return no findings.

    If ``safety_critical_names`` is empty, there is nothing to grep for, so
    this always returns no findings — this baseline has no way to flag a
    scaffolded function or an intent mismatch, by design.
    """
    if not safety_critical_names:
        return []

    text = path.read_text(encoding="utf-8")
    missing = [name for name in safety_critical_names if name not in text]
    return [MISSING_GATE_FINDING] if missing else []
