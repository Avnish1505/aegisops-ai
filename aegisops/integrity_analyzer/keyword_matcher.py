"""Match intent keywords against extracted identifiers.

This is a standalone stage: it takes the capability keywords produced by
``intent_parser.parse_intent`` and the identifier set produced by
``identifier_extractor.extract_identifiers`` and decides which keywords are
accounted for in the code. A keyword matches if it is a substring match
against some identifier, or a close (fuzzy) match per
``difflib.get_close_matches``. No scoring, reporting, or CLI is introduced
here — only the matched/unmatched split.
"""

from __future__ import annotations

from difflib import get_close_matches

DEFAULT_CUTOFF = 0.6


def match_keywords(
    keywords: list[str],
    identifiers: set[str],
    *,
    cutoff: float = DEFAULT_CUTOFF,
) -> tuple[list[str], list[str]]:
    """Split ``keywords`` into ``(matched, unmatched)`` against ``identifiers``.

    A keyword matches if either is true, compared case-insensitively:

    - it is a substring of an identifier, or an identifier is a substring of it
    - it is a close match to some identifier, per
      ``difflib.get_close_matches(keyword, identifiers, cutoff=cutoff)``

    Order from ``keywords`` is preserved in both output lists.
    """
    normalized_identifiers = [identifier.lower() for identifier in identifiers]

    matched: list[str] = []
    unmatched: list[str] = []
    for keyword in keywords:
        if _has_substring_match(keyword, normalized_identifiers) or _has_close_match(
            keyword, normalized_identifiers, cutoff
        ):
            matched.append(keyword)
        else:
            unmatched.append(keyword)

    return matched, unmatched


def _has_substring_match(keyword: str, identifiers: list[str]) -> bool:
    """Return ``True`` if ``keyword`` and some identifier contain one another."""
    return any(keyword in identifier or identifier in keyword for identifier in identifiers)


def _has_close_match(keyword: str, identifiers: list[str], cutoff: float) -> bool:
    """Return ``True`` if ``keyword`` fuzzily matches some identifier."""
    return bool(get_close_matches(keyword, identifiers, n=1, cutoff=cutoff))
