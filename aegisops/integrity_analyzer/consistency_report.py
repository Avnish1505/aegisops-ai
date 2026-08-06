"""Build a consistency report from matched/unmatched intent keywords.

This is a standalone stage: it takes the ``(matched, unmatched)`` split
produced by ``keyword_matcher.match_keywords`` and reduces it to a report
with a single consistency score.

Heuristic, not semantic analysis
---------------------------------
This report is a **heuristic** signal, not semantic program analysis. The
underlying match is text-based — substring containment and
``difflib.get_close_matches`` fuzzy matching between an intent's keywords and
a module's identifier names (see ``keyword_matcher.py``). It has no
understanding of program behavior, control flow, or data flow: a matched
keyword only means a similarly-named identifier exists somewhere in the
module, not that the code actually does what the intent describes, and an
unmatched keyword does not prove the capability is missing (e.g. it may be
implemented under a differently-worded name). The consistency score should
be read as a rough, best-effort proxy — useful for surfacing likely gaps to a
human reviewer — never as proof of correctness or incorrectness.
"""

from __future__ import annotations


def build_consistency_report(matched: list[str], unmatched: list[str]) -> dict[str, object]:
    """Build a consistency report from a keyword-matching split.

    Returns a dict with:

    - ``matched_keywords``: the matched keywords, unchanged
    - ``unmatched_keywords``: the unmatched keywords, unchanged
    - ``consistency_score``: ``len(matched) / (len(matched) + len(unmatched))``,
      i.e. the fraction of intent keywords accounted for in the code. When
      there are no keywords at all (nothing was claimed), the score is
      ``1.0`` — vacuously consistent, since there is nothing to contradict.

    This score is heuristic (see module docstring), not a measure of
    semantic correctness.
    """
    total = len(matched) + len(unmatched)
    consistency_score = (len(matched) / total) if total else 1.0

    return {
        "matched_keywords": list(matched),
        "unmatched_keywords": list(unmatched),
        "consistency_score": consistency_score,
    }
