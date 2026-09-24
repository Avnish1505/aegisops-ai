"""The audit event chain detects any edit to an event, or to the records events describe."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from auth_helpers import REJECT, bearer
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine, text

from aegisops.api.app import create_app
from aegisops.audit.event_log import GENESIS_HASH, event_hash
from aegisops.core.config import Settings

EVENT_COLUMNS = {
    "ts": "'2020-01-01T00:00:00+00:00'",
    "actor": "'mallory'",
    "type": "'decision_deleted'",
    "payload": "'{\"decision_id\": 999}'",
    "prev_hash": "'" + "f" * 64 + "'",
    "hash": "'" + "e" * 64 + "'",
}


def _client_with_history(tmp_path: Path) -> tuple[TestClient, str]:
    url = f"sqlite:///{tmp_path / 'chain.db'}"
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    client = TestClient(
        create_app(Settings(environment="test", database_url=url)), headers=bearer()
    )
    first = client.post("/api/v1/decisions", json={"seed": 3}).json()["decision_id"]
    client.post("/api/v1/decisions", json={"seed": 4})
    client.post(
        f"/api/v1/decisions/{first}/disposition",
        json={**REJECT, "reason": "Needs another look."},
    )
    return client, url


def _execute(url: str, sql: str) -> None:
    with create_engine(url).begin() as connection:
        connection.execute(text(sql))


def test_untouched_chain_verifies(tmp_path: Path) -> None:
    client, _ = _client_with_history(tmp_path)

    report = client.get("/api/v1/audit/verify").json()

    assert report == {
        "ok": True,
        "events_checked": 5,
        "head_hash": report["head_hash"],
        "first_broken": None,
    }
    assert len(report["head_hash"]) == 64


@pytest.mark.parametrize("column", sorted(EVENT_COLUMNS))
@pytest.mark.parametrize("event_id", [1, 3, 5])
def test_editing_any_event_column_is_detected_at_that_event(
    tmp_path: Path, column: str, event_id: int
) -> None:
    client, url = _client_with_history(tmp_path)

    _execute(url, f"UPDATE events SET {column} = {EVENT_COLUMNS[column]} WHERE id = {event_id}")

    report = client.get("/api/v1/audit/verify").json()
    assert report["ok"] is False
    assert report["first_broken"]["event_id"] == event_id


def test_deleting_an_event_is_detected_at_the_next_one(tmp_path: Path) -> None:
    client, url = _client_with_history(tmp_path)

    _execute(url, "DELETE FROM events WHERE id = 2")

    report = client.get("/api/v1/audit/verify").json()
    assert report["first_broken"]["event_id"] == 3


def test_flipping_a_decision_status_in_the_database_is_detected(tmp_path: Path) -> None:
    client, url = _client_with_history(tmp_path)

    _execute(
        url,
        "UPDATE decisions SET status = CASE WHEN status = 'blocked' "
        "THEN 'requires_human_approval' ELSE 'blocked' END WHERE id = 2",
    )

    broken = client.get("/api/v1/audit/verify").json()["first_broken"]
    assert broken["event_id"] == 3  # decision 2's decision_created event
    assert "decisions row 2" in broken["reason"]


def test_flipping_an_approval_in_the_database_is_detected(tmp_path: Path) -> None:
    client, url = _client_with_history(tmp_path)

    _execute(url, "UPDATE approvals SET approved = 1 WHERE id = 1")

    broken = client.get("/api/v1/audit/verify").json()["first_broken"]
    assert broken["event_id"] == 5
    assert "approvals row 1" in broken["reason"]


def test_chain_starts_at_genesis_and_links(tmp_path: Path) -> None:
    _, url = _client_with_history(tmp_path)

    with create_engine(url).connect() as connection:
        rows = connection.execute(text("SELECT id, prev_hash, hash FROM events ORDER BY id")).all()

    assert rows[0].prev_hash == GENESIS_HASH
    assert all(rows[i].prev_hash == rows[i - 1].hash for i in range(1, len(rows)))


@settings(max_examples=100, deadline=None)
@given(
    payload=st.dictionaries(st.text(max_size=8), st.integers() | st.text(max_size=8), max_size=4),
    field=st.sampled_from(["id", "ts", "actor", "type", "payload"]),
)
def test_any_field_change_changes_the_hash(payload: dict[str, object], field: str) -> None:
    base = {"event_id": 7, "ts": "t", "actor": "a", "event_type": "x", "payload": payload}
    changed = dict(base)
    key = {"id": "event_id", "type": "event_type"}.get(field, field)
    changed[key] = (
        base[key] + 1
        if isinstance(base[key], int)
        else {**payload, "__tampered__": 1}
        if key == "payload"
        else f"{base[key]}!"
    )

    assert event_hash(GENESIS_HASH, **base) != event_hash(GENESIS_HASH, **changed)  # type: ignore[arg-type]
