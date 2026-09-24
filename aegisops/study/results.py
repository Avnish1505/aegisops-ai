"""Score study tasks and write the CSV the analysis script reads (scripts/analyze_study.py).

time_to_decision_s: from the moment the participant opened the plan (the runner calls /start
just before navigating) to the stored disposition. correct: the action matches the task's right
answer. caught (injected tasks only): rejected with the reason code that names the error.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

CSV_FIELDS = (
    "participant", "participant_number", "order", "ui", "task", "injected_error",
    "expected_action", "action", "reason_code", "correct", "caught", "time_to_decision_s",
    "started_at", "decided_at", "decision_id",
)


@dataclass(frozen=True, slots=True)
class TaskResult:
    participant: str
    participant_number: int
    order: int
    ui: str
    task: str
    injected_error: str | None
    expected_action: str
    action: str | None
    reason_code: str | None
    correct: bool | None
    caught: bool | None
    time_to_decision_s: float | None
    started_at: str | None
    decided_at: str | None
    decision_id: int


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def score(
    *,
    participant: str,
    participant_number: int,
    order: int,
    ui: str,
    task: str,
    injected_error: str | None,
    expected_action: str,
    expected_reason: str | None,
    decision_id: int,
    started_at: datetime | None,
    action: str | None,
    reason_code: str | None,
    decided_at: datetime | None,
) -> TaskResult:
    start, end = _aware(started_at), _aware(decided_at)
    decided = action is not None
    return TaskResult(
        participant=participant,
        participant_number=participant_number,
        order=order,
        ui=ui,
        task=task,
        injected_error=injected_error,
        expected_action=expected_action,
        action=action,
        reason_code=reason_code,
        correct=(action == expected_action) if decided else None,
        caught=(action == "reject" and reason_code == expected_reason)
        if decided and injected_error else None,
        time_to_decision_s=round((end - start).total_seconds(), 1) if start and end else None,
        started_at=start.isoformat() if start else None,
        decided_at=end.isoformat() if end else None,
        decision_id=decision_id,
    )


def to_csv(rows: Iterable[TaskResult]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: "" if v is None else v for k, v in asdict(row).items()})
    return buffer.getvalue()
