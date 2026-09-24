"""scripts/analyze_study.py on hand-made fixture rows (test data, not study results)."""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from analyze_study import analyse, sign_test  # noqa: E402

from aegisops.study.results import CSV_FIELDS  # noqa: E402


def _row(participant: str, ui: str, order: int, seconds: float, error: str = "",
         caught: str = "", correct: str = "True") -> dict[str, str]:
    row = dict.fromkeys(CSV_FIELDS, "")
    row.update(participant=participant, participant_number=participant[1:], ui=ui,
               order=str(order), task=f"T{order}", injected_error=error,
               expected_action="reject" if error else "approve",
               action="reject" if error else "approve", correct=correct, caught=caught,
               time_to_decision_s=str(seconds), decision_id=str(order))
    return row


def _participant(code: str, legacy_first: bool, legacy_s: float, console_s: float,
                 caught_console: str = "True") -> list[dict[str, str]]:
    first, second = ("legacy", "console") if legacy_first else ("console", "legacy")
    times = {"legacy": legacy_s, "console": console_s}
    caught = {"legacy": "False", "console": caught_console}
    rows = []
    for offset, ui in ((0, first), (6, second)):
        rows.append(_row(code, ui, offset + 1, times[ui]))
        rows.append(_row(code, ui, offset + 2, times[ui], error="wrong_eta", caught=caught[ui]))
    return rows


def test_medians_rates_and_paired_differences() -> None:
    rows = _participant("P01", True, 40.0, 30.0) + _participant("P02", False, 50.0, 55.0, "False")

    result = analyse(rows)

    assert result["participants"] == 2 and result["paired_participants"] == 2
    assert result["per_ui"]["legacy"]["median_time_s"] == 45.0
    assert result["per_ui"]["console"]["caught"] == {"k": 1, "n": 2, "value": 0.5}
    assert [p["difference_s"] for p in result["paired"]] == [-10.0, 5.0]
    assert [p["first_ui"] for p in result["paired"]] == ["legacy", "console"]
    assert result["paired_summary"]["sign_test_p"] is None  # n < 5: no test


def test_sign_test_needs_five_nonzero_pairs_and_is_exact() -> None:
    assert sign_test([-1, -2, -3, -4]) is None
    assert sign_test([-1, -2, -3, -4, -5, 0]) == pytest.approx(2 / 32)
    assert sign_test([-1, 1, -1, 1, -1, 1]) == pytest.approx(1.0)


def test_command_writes_markdown_that_states_n(tmp_path: Path) -> None:
    source = tmp_path / "study.csv"
    with source.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(_participant("P01", True, 40.0, 30.0))

    subprocess.run([sys.executable, "scripts/analyze_study.py", str(source), "--out",
                    str(tmp_path / "user_study")], check=True, cwd=Path(__file__).parents[1])

    text = (tmp_path / "user_study.md").read_text()
    assert "n = 1 participant(s), 1 with both interfaces" in text
    assert "No significance test" in text
    assert (tmp_path / "user_study.json").exists()
