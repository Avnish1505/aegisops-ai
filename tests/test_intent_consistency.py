"""Unit tests for the intent/code consistency pipeline (intent_parser ->
identifier_extractor -> keyword_matcher -> consistency_report).

Exactly five scenarios, per bundle scope: full match, empty scaffold, retry
mismatch, generic cleanup, and partial match. No analyzer logic is changed
here.
"""

from pathlib import Path

from aegisops.integrity_analyzer.ast_parser import parse_source
from aegisops.integrity_analyzer.consistency_report import build_consistency_report
from aegisops.integrity_analyzer.identifier_extractor import extract_identifiers
from aegisops.integrity_analyzer.intent_parser import parse_intent
from aegisops.integrity_analyzer.keyword_matcher import match_keywords
from aegisops.integrity_analyzer.source_loader import load_source_file


def _identifiers_for(tmp_path: Path, source: str) -> set[str]:
    module_path = tmp_path / "module.py"
    module_path.write_text(source, encoding="utf-8")
    parsed = parse_source(load_source_file(module_path))
    return extract_identifiers(parsed)


def test_full_match_scores_one(tmp_path: Path) -> None:
    """Every intent keyword is accounted for in the code: score is a perfect 1.0."""
    identifiers = _identifiers_for(
        tmp_path,
        "def validate_input(data):\n    return True\n\ndef send_email(address):\n    return None\n",
    )
    keywords = parse_intent("Validate input and send email")

    matched, unmatched = match_keywords(keywords, identifiers)
    report = build_consistency_report(matched, unmatched)

    assert unmatched == []
    assert matched == ["validate", "input", "send", "email"]
    assert report["consistency_score"] == 1.0


def test_empty_scaffold_scores_low(tmp_path: Path) -> None:
    """A scaffolded (pass-only) function backs almost none of the claimed intent."""
    identifiers = _identifiers_for(tmp_path, "def process():\n    pass\n")
    keywords = parse_intent("Process the payment and update database records")

    matched, unmatched = match_keywords(keywords, identifiers)
    report = build_consistency_report(matched, unmatched)

    assert matched == ["process"]
    assert unmatched == ["payment", "update", "database", "records"]
    assert report["consistency_score"] == 0.2


def test_retry_mismatch_leaves_retry_unmatched(tmp_path: Path) -> None:
    """Claimed retry behavior with no retry logic in the code is flagged unmatched."""
    identifiers = _identifiers_for(
        tmp_path,
        "def send_request():\n    return call_api()\n\ndef call_api():\n    return True\n",
    )
    keywords = parse_intent("Retry failed requests automatically")

    matched, unmatched = match_keywords(keywords, identifiers)

    assert "retry" in unmatched
    assert "retry" not in matched


def test_generic_cleanup_matches_via_fuzzy_matching(tmp_path: Path) -> None:
    """A differently-spelled identifier ('clean_up') still fuzzy-matches 'cleanup'."""
    identifiers = _identifiers_for(tmp_path, "def clean_up():\n    return None\n")
    keywords = parse_intent("Cleanup the workspace")

    matched, unmatched = match_keywords(keywords, identifiers)

    assert matched == ["cleanup"]
    assert unmatched == ["workspace"]


def test_partial_match_scores_between_zero_and_one(tmp_path: Path) -> None:
    """A mix of matched and unmatched keywords produces a fractional score."""
    identifiers = _identifiers_for(
        tmp_path,
        "def send_email(address):\n    return None\n\ndef noop():\n    return None\n",
    )
    keywords = parse_intent("Send email and delete temporary cache")

    matched, unmatched = match_keywords(keywords, identifiers)
    report = build_consistency_report(matched, unmatched)

    assert matched == ["send", "email"]
    assert unmatched == ["delete", "temporary", "cache"]
    assert report["consistency_score"] == 0.4
