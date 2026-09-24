"""Console read endpoints and the SSE stream."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from auth_helpers import REJECT, bearer
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.api.console import (
    TicketBook,
    current_cursor,
    feed_health,
    new_messages,
    stream_messages,
)
from aegisops.core.config import Settings
from backend.db.models import FeedPoll


def _app() -> TestClient:
    return TestClient(create_app(Settings(environment="test", database_url="sqlite://")))


def _sessions(client: TestClient):  # type: ignore[no-untyped-def]
    return client.app.state.session_factory  # type: ignore[attr-defined]


def test_status_reports_feeds_model_and_pending_approvals() -> None:
    client = _app()
    operator, approver = bearer("olive", "operator"), bearer("bob", "approver")
    first = client.post("/api/v1/decisions", json={"seed": 3}, headers=operator).json()
    client.post("/api/v1/decisions", json={"seed": 4}, headers=operator)
    client.post(f"/api/v1/decisions/{first['decision_id']}/disposition",
                json={**REJECT, "reason": "test"}, headers=approver)

    body = client.get("/api/v1/status", headers=bearer("v", "viewer")).json()

    assert [f["state"] for f in body["feeds"]] == ["no_data", "no_data", "no_data"]
    assert body["model"]["configured"] is False
    pending = client.get("/api/v1/decisions?pending=true", headers=operator).json()
    assert body["pending_approvals"] == len(pending)
    assert first["decision_id"] not in {d["decision_id"] for d in pending}


def test_status_needs_a_token() -> None:
    assert _app().get("/api/v1/status").status_code == 401


@pytest.mark.parametrize(
    ("polls", "state"),
    [
        ([(0, True)], "ok"),
        ([(60, True)], "stale"),  # 60 min > 3 x 5 min interval
        ([(0, True), (-1, False)], "failing"),  # the newest poll failed
    ],
)
def test_feed_health_states(polls: list[tuple[int, bool]], state: str) -> None:
    client = _app()
    now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    with _sessions(client)() as session, session.begin():
        for minutes_ago, ok in polls:
            session.add(FeedPoll(source="sachet", polled_at=now - timedelta(minutes=minutes_ago),
                                 ok=ok, error=None if ok else "boom", fetched=0, inserted=0))
    with _sessions(client)() as session:
        sachet = feed_health(session, Settings(environment="test"), now)[0]

    assert sachet["state"] == state


def test_decision_list_filters_and_summarises() -> None:
    client = _app()
    operator = bearer("olive", "operator")
    made = client.post("/api/v1/decisions", json={"seed": 3}, headers=operator).json()

    rows = client.get("/api/v1/decisions", headers=operator).json()
    blocked = client.get("/api/v1/decisions?status=blocked", headers=operator).json()

    assert rows[0]["decision_id"] == made["decision_id"]
    assert rows[0]["proposer_sub"] == "olive"
    assert rows[0]["disposition"] is None
    assert all(row["status"] == "blocked" for row in blocked)


def test_events_filter_by_decision_newest_first() -> None:
    client = _app()
    operator = bearer("olive", "operator")
    one = client.post("/api/v1/decisions", json={"seed": 3}, headers=operator).json()
    client.post("/api/v1/decisions", json={"seed": 4}, headers=operator)

    events = client.get(f"/api/v1/events?decision_id={one['decision_id']}",
                        headers=operator).json()

    assert [e["type"] for e in events] == ["verification_completed", "decision_created"]
    assert events[0]["prev_hash"] == events[1]["hash"]


def test_stream_tickets_are_single_use_and_expire() -> None:
    now = [0.0]
    book = TicketBook(ttl_s=30, clock=lambda: now[0])
    first, second = book.issue("olive"), book.issue("olive")

    assert book.redeem(first) == "olive"
    assert book.redeem(first) is None
    now[0] = 31
    assert book.redeem(second) is None
    assert book.redeem("made-up") is None


def test_stream_rejects_a_bad_ticket_and_issues_real_ones_to_signed_in_users() -> None:
    client = _app()

    assert client.get("/api/v1/stream?ticket=nope").status_code == 401
    assert client.post("/api/v1/stream/ticket").status_code == 401
    issued = client.post("/api/v1/stream/ticket", headers=bearer()).json()
    assert issued["expires_in"] == 30 and len(issued["ticket"]) > 20


def test_new_messages_name_audit_events_and_advance_the_cursor() -> None:
    client = _app()
    with _sessions(client)() as session:
        cursor = current_cursor(session)
    client.post("/api/v1/decisions", json={"seed": 3}, headers=bearer())

    with _sessions(client)() as session:
        first = new_messages(session, cursor)
        again = new_messages(session, cursor)

    assert [name for _, name, _ in first] == ["decision.created", "decision.verified"]
    assert again == []


def test_stream_sends_ready_then_new_events_as_sse_frames() -> None:
    client = _app()
    sessions = _sessions(client)
    checks = {"n": 0}

    async def disconnected() -> bool:
        checks["n"] += 1
        if checks["n"] == 1:
            # Something happens after the client connected.
            client.post("/api/v1/decisions", json={"seed": 3}, headers=bearer())
        return checks["n"] > 2

    async def collect() -> list[str]:
        return [frame async for frame in stream_messages(sessions, disconnected, poll_s=0)]

    frames = asyncio.run(collect())

    assert frames[0].startswith("id: ready\nevent: ready\n")
    names = [f.split("\n")[1] for f in frames[1:]]
    assert names == ["event: decision.created", "event: decision.verified"]
    assert all(f.endswith("\n\n") for f in frames)



def test_labels_name_incidents_by_reported_place_and_units_by_facility() -> None:
    import json
    from pathlib import Path

    from backend.db.models import Facility

    exercise = json.loads(
        (Path(__file__).parents[1] / "evals" / "data" / "lucknow_exercise_v1.json").read_text()
    )
    client = _app()
    with _sessions(client)() as session, session.begin():
        session.add(Facility(osm_type="node", osm_id=6621697164, kind="hospital",
                             name="Test District Hospital", location=(26.84, 80.94), tags={}))

    labels = client.post("/api/v1/labels", json=exercise, headers=bearer("v", "viewer")).json()

    assert labels["incidents"]["INC-LKO-01"] == "Charbagh"
    # The nearest OSM place is "Sector - 15"; the report names Indira Nagar, 2 km or less away.
    assert labels["incidents"]["INC-LKO-16"] == "Indira Nagar"
    assert labels["units"]["RES-AMB-n6621697164-1"] == "Test District Hospital"


def test_decisions_filter_by_scenario() -> None:
    client = _app()
    operator = bearer("olive", "operator")
    made = client.post("/api/v1/decisions", json={"seed": 3}, headers=operator).json()
    client.post("/api/v1/decisions", json={"seed": 4}, headers=operator)

    rows = client.get(f"/api/v1/decisions?scenario_id={made['scenario_id']}",
                      headers=operator).json()

    assert {row["scenario_id"] for row in rows} == {made["scenario_id"]}


def test_routes_are_straight_lines_without_a_road_network() -> None:
    client = _app()
    operator = bearer("olive", "operator")
    decision = client.post("/api/v1/decisions", json={"seed": 3}, headers=operator).json()

    routes = client.get(f"/api/v1/decisions/{decision['decision_id']}/routes",
                        headers=operator).json()

    assert len(routes) == len(decision["assignments"]) > 0
    assert {r["geometry"] for r in routes} == {"straight_line"}
    assert all(len(r["coordinates"]) == 2 for r in routes)


def test_osrm_routes_use_road_geometry_and_fall_back_on_error() -> None:
    import httpx

    from aegisops.domain.models import Location
    from aegisops.planning.osrm import OSRMProvider

    calls: list[str] = []

    def osrm(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "80.950000" in request.url.path:
            return httpx.Response(503)
        line = [[80.92, 26.83], [80.93, 26.84], [80.94, 26.85]]
        return httpx.Response(200, json={
            "code": "Ok", "routes": [{"geometry": {"type": "LineString", "coordinates": line}}]})

    provider = OSRMProvider("http://osrm", client=httpx.Client(transport=httpx.MockTransport(osrm)))
    road = provider.route(Location(lat=26.83, lon=80.92), Location(lat=26.85, lon=80.94))
    again = provider.route(Location(lat=26.83, lon=80.92), Location(lat=26.85, lon=80.94))
    failed = provider.route(Location(lat=26.83, lon=80.92), Location(lat=26.85, lon=80.95))

    assert road.geometry == "road" and len(road.coordinates) == 3
    assert again == road and len(calls) == 2  # the second road request came from the cache
    assert calls[0].startswith("/route/v1/driving/80.920000,26.830000;")
    assert failed.geometry == "straight_line" and "HTTPStatusError" in (failed.reason or "")


def test_alert_areas_keep_cap_polygons_and_circles() -> None:
    from pathlib import Path

    from aegisops.api.console import alert_areas
    from aegisops.ingestion.cap import cap_to_record

    fixture = Path(__file__).parent / "fixtures" / "feeds" / "cap_synthetic_polygon_circle.xml"
    record = cap_to_record(fixture.read_bytes())

    areas = alert_areas(record.parsed)

    assert areas and areas[0]["polygons"] and areas[0]["circles"]
    lat, lon = areas[0]["polygons"][0][0]
    assert 20 < lat < 30 and 75 < lon < 85  # CAP order is lat,lon; Lucknow is ~26.8 N, 80.9 E


def test_reports_serves_the_newest_of_each_kind_and_lists_superseded(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    (tmp_path / "fault_injection.json").write_text(json.dumps({"faults_caught": 650}))
    (tmp_path / "eval_2026-09-01.json").write_text(json.dumps({"meta": {"date": "2026-09-01"}}))
    (tmp_path / "eval_2026-09-24.json").write_text(json.dumps({"meta": {"date": "2026-09-24"}}))
    (tmp_path / "old.json").write_text(json.dumps({"_superseded": "keyless run"}))
    client = TestClient(create_app(Settings(environment="test", database_url="sqlite://",
                                            reports_dir=tmp_path)))

    body = client.get("/api/v1/reports").json()

    assert body["fault_injection"]["data"] == {"faults_caught": 650}
    assert body["eval"]["file"] == "reports/eval_2026-09-24.json"
    assert body["llm_vs_solver"] is None and body["user_study"] is None
    assert body["superseded"] == [{"file": "reports/old.json", "note": "keyless run"}]


def test_committed_reports_are_readable() -> None:
    body = _app().get("/api/v1/reports").json()

    assert body["fault_injection"]["data"]["faults_caught"] == 650
    assert any(s["file"] == "reports/phase_4_experiment_report.json" for s in body["superseded"])
