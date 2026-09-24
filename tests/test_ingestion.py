"""Feed parsers and the ingestion worker, driven only by recorded fixtures (never the network)."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from aegisops.api.app import create_app
from aegisops.core.config import Settings
from aegisops.ingestion.cap import CapParseError, cap_to_record, parse_cap
from aegisops.ingestion.feeds import FeedParseError, parse_gdacs, parse_sachet_rss, parse_usgs
from aegisops.ingestion.worker import Poller, build_scheduler
from backend.db.models import Alert

FEEDS = Path(__file__).parent / "fixtures" / "feeds"
IST = timezone(timedelta(hours=5, minutes=30))
SETTINGS = Settings(environment="test")
CAP_BY_GUID = {
    "1790168189341029": "sachet_cap_lightning_bilingual.xml",
    "1790166906028017": "sachet_cap_flood_west_bengal.xml",
    "1790152271184020": "sachet_cap_update_geocodes.xml",
}


def _read(name: str) -> bytes:
    return (FEEDS / name).read_bytes()


# --- CAP 1.2 ---------------------------------------------------------------------------------


def test_real_bilingual_sachet_alert() -> None:
    alert = parse_cap(_read("sachet_cap_lightning_bilingual.xml"))

    assert alert.identifier == "IN-1790168189341029_29"
    assert alert.sender == "Maharashtra-SDMA"
    assert alert.sent == datetime(2026, 9, 23, 18, 26, 29, tzinfo=IST)
    assert (alert.status, alert.msg_type, alert.scope) == ("Actual", "Alert", "Public")
    assert [info.language for info in alert.infos] == ["en-IN", "MR"]
    assert alert.infos[0].event == "Lightning"
    assert alert.infos[0].expires == datetime(2026, 9, 23, 21, 25, tzinfo=IST)
    assert alert.infos[0].areas[0].area_desc == "Chandrapur"


def test_record_summary_uses_the_english_info() -> None:
    record = cap_to_record(_read("sachet_cap_lightning_bilingual.xml"), source_ref="guid-1")

    assert record.headline is not None and record.headline.startswith("Lightning is Very Likely")
    assert (record.source, record.source_ref, record.severity) == ("sachet", "guid-1", "Severe")
    assert record.raw_payload == _read("sachet_cap_lightning_bilingual.xml").decode("utf-8")


def test_update_alert_carries_its_reference_and_geocodes() -> None:
    alert = parse_cap(_read("sachet_cap_update_geocodes.xml"))

    assert alert.msg_type == "Update"
    assert alert.references == [
        ("IMD-Ahmedabad", "IN-1790152271184020_49", "2026-09-23T14:00:45+05:30")
    ]
    geocodes = alert.infos[0].areas[0].geocodes
    assert len(geocodes) == 12
    assert all(name == "LGD District Code" for name, _ in geocodes)


def test_polygon_circle_and_parameters_follow_the_spec() -> None:
    alert = parse_cap(_read("cap_synthetic_polygon_circle.xml"))
    area = alert.infos[0].areas[0]

    assert area.polygons == [
        [(26.85, 80.98), (26.87, 80.98), (26.87, 81.01), (26.85, 81.01), (26.85, 80.98)]
    ]
    assert area.circles == [(26.8505, 80.947, 1.5)]
    assert alert.infos[0].categories == ["Met", "Safety"]
    assert alert.infos[0].parameters == [("Rainfall_mm", "210")]
    record = cap_to_record(_read("cap_synthetic_polygon_circle.xml"))
    assert record.lat == pytest.approx((26.85 + 26.87 + 26.87 + 26.85 + 26.8505) / 5)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (_read("cap_synthetic_missing_identifier.xml"), "identifier"),
        (_read("cap_synthetic_entity_expansion.xml"), "unsafe XML"),
        (b"<alert>not cap</alert>", "not a CAP 1.2"),
        (b"not xml at all", "not well-formed"),
        (
            _read("cap_synthetic_polygon_circle.xml").replace(
                b"<status>Exercise</status>", b"<status>Rumour</status>"
            ),
            "status",
        ),
        (
            _read("cap_synthetic_polygon_circle.xml").replace(
                b"26.85,81.01 26.85,80.98</polygon>", b"26.85,81.01</polygon>"
            ),
            "polygon",
        ),
        (
            _read("cap_synthetic_polygon_circle.xml").replace(
                b"2026-09-23T06:00:00+05:30", b"2026-09-23T06:00:00"
            ),
            "timezone",
        ),
    ],
    ids=["missing-identifier", "entity-expansion", "wrong-root", "garbage", "bad-status",
         "open-polygon", "naive-time"],
)
def test_invalid_cap_is_rejected(document: bytes, message: str) -> None:
    with pytest.raises(CapParseError, match=message):
        parse_cap(document)


# --- RSS, USGS, GDACS ------------------------------------------------------------------------


def test_sachet_rss_items_link_to_cap_documents() -> None:
    items = parse_sachet_rss(_read("sachet_rss_india.xml"))

    assert [item.guid for item in items] == list(CAP_BY_GUID)
    assert all("FetchXMLFile?identifier=" in item.link for item in items)
    assert items[0].published is not None and items[0].published.tzinfo is not None


def test_usgs_features_become_alerts_with_lat_lon_in_the_right_order() -> None:
    records = parse_usgs(_read("usgs_all_day.geojson"))

    first = records[0]
    assert len(records) == 4
    assert (first.identifier, first.severity) == ("aka2026swllkm", "M1.8")
    assert (first.lat, first.lon) == (61.918, -151.189)
    assert first.sent_at == datetime.fromtimestamp(1790167742.534, tz=UTC)


def test_gdacs_events_are_keyed_by_type_event_and_episode() -> None:
    records = parse_gdacs(_read("gdacs_events.json"))

    assert records[0].identifier == "FL-1104121-16"
    assert (records[0].headline, records[0].area_desc, records[0].severity) == (
        "Flood in India", "India", "Orange"
    )
    assert records[0].sent_at == datetime(2026, 8, 9, 1, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("parse", "document"),
    [
        (parse_sachet_rss, b"<html>SACHET portal</html>"),
        (parse_usgs, b'{"type": "Feature"}'),
        (parse_gdacs, b'{"message": "Eventtype is required."}'),
        (parse_usgs, b"<html>"),
    ],
)
def test_unexpected_feed_payloads_are_rejected(parse, document: bytes) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(FeedParseError):
        parse(document)


# --- Worker ----------------------------------------------------------------------------------


class Feeds:
    """Serve recorded fixtures by URL and count requests."""

    def __init__(self, overrides: dict[str, httpx.Response] | None = None) -> None:
        self.requests: list[str] = []
        self.overrides = overrides or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        for fragment, response in self.overrides.items():
            if fragment in url:
                return response
        if url == SETTINGS.ingest_sachet_rss_url:
            return httpx.Response(200, content=_read("sachet_rss_india.xml"))
        if "FetchXMLFile" in url:
            return httpx.Response(200, content=_read(CAP_BY_GUID[request.url.params["identifier"]]))
        if url == SETTINGS.ingest_usgs_url:
            return httpx.Response(200, content=_read("usgs_all_day.geojson"))
        if url == str(httpx.URL(SETTINGS.ingest_gdacs_url)):
            return httpx.Response(200, content=_read("gdacs_events.json"))
        return httpx.Response(404)


@pytest.fixture()
def database(tmp_path: Path) -> str:
    url = f"sqlite:///{tmp_path / 'alerts.db'}"
    config = Config(str(Path(__file__).parents[1] / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    return url


def _poller(url: str, feeds: Feeds) -> Poller:
    return Poller(
        sessionmaker(bind=create_engine(url)),
        SETTINGS,
        client=httpx.Client(transport=httpx.MockTransport(feeds)),
        clock=lambda: datetime(2026, 9, 23, 13, 0, tzinfo=UTC),
    )


def _count(url: str, source: str) -> int:
    with Session(create_engine(url)) as session:
        return session.scalar(
            select(func.count()).select_from(Alert).where(Alert.source == source)
        ) or 0


def test_polling_stores_each_alert_once_with_source_time_and_raw_payload(database: str) -> None:
    feeds = Feeds()
    poller = _poller(database, feeds)

    first = poller.poll_all()
    second = poller.poll_all()

    assert [(r.source, r.inserted) for r in first] == [("sachet", 3), ("usgs", 4), ("gdacs", 4)]
    assert [(r.source, r.inserted, r.duplicates) for r in second] == [
        ("sachet", 0, 3), ("usgs", 0, 4), ("gdacs", 0, 4)
    ]
    assert (_count(database, "sachet"), _count(database, "usgs"), _count(database, "gdacs")) == (
        3, 4, 4
    )
    with Session(create_engine(database)) as session:
        stored = session.scalar(select(Alert).where(Alert.identifier == "IN-1790166906028017_17"))
    assert stored is not None
    assert stored.raw_payload == _read("sachet_cap_flood_west_bengal.xml").decode("utf-8")
    assert stored.fetched_at.replace(tzinfo=UTC) == datetime(2026, 9, 23, 13, 0, tzinfo=UTC)
    assert stored.source_ref == "1790166906028017"


def test_already_stored_cap_documents_are_not_downloaded_again(database: str) -> None:
    feeds = Feeds()
    poller = _poller(database, feeds)

    poller.poll_sachet()
    before = len(feeds.requests)
    poller.poll_sachet()

    assert feeds.requests[before:] == [SETTINGS.ingest_sachet_rss_url]


def test_an_invalid_cap_document_is_skipped_and_the_rest_stored(database: str) -> None:
    feeds = Feeds({"1790168189341029": httpx.Response(200, content=b"<html>oops</html>")})

    result = _poller(database, feeds).poll_sachet()

    assert (result.inserted, result.invalid) == (2, 1)


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503), httpx.Response(200, content=b"<html>SACHET portal</html>")],
    ids=["http-503", "html-instead-of-rss"],
)
def test_a_failing_feed_does_not_stop_the_others(database: str, failure: httpx.Response) -> None:
    feeds = Feeds({"rss_india.xml": failure})

    results = {r.source: r for r in _poller(database, feeds).poll_all()}

    assert results["sachet"].error is not None
    assert results["usgs"].inserted == 4 and results["gdacs"].inserted == 4


def test_scheduler_registers_three_non_overlapping_jobs(database: str) -> None:
    scheduler = build_scheduler(_poller(database, Feeds()), SETTINGS)

    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {"sachet", "usgs", "gdacs"}
    assert all(job.max_instances == 1 and job.coalesce for job in jobs.values())
    assert jobs["gdacs"].trigger.interval == timedelta(minutes=15)


def test_alerts_api_returns_summaries_without_raw_payloads(database: str) -> None:
    _poller(database, Feeds()).poll_all()
    client = TestClient(create_app(Settings(environment="test", database_url=database)))

    everything = client.get("/api/v1/alerts?limit=50").json()
    floods = client.get("/api/v1/alerts?source=gdacs").json()

    assert len(everything) == 11
    assert all("raw_payload" not in alert for alert in everything)
    assert {alert["source"] for alert in floods} == {"gdacs"}
    usgs = next(a for a in everything if a["identifier"] == "aka2026swllkm")
    assert usgs["location"] == {"lat": 61.918, "lon": -151.189}


def test_every_poll_is_recorded_and_drives_feed_health(database: str) -> None:
    from auth_helpers import bearer

    from backend.db.models import FeedPoll

    feeds = Feeds({"rss_india.xml": httpx.Response(503)})
    _poller(database, feeds).poll_all()
    client = TestClient(create_app(Settings(environment="test", database_url=database)),
                        headers=bearer())

    with Session(create_engine(database)) as session:
        polls = {p.source: p for p in session.scalars(select(FeedPoll))}
    health = {f["source"]: f for f in client.get("/api/v1/status").json()["feeds"]}

    assert (polls["sachet"].ok, polls["usgs"].ok, polls["usgs"].inserted) == (False, True, 4)
    assert "HTTPStatusError" in (polls["sachet"].error or "")
    assert health["sachet"]["state"] == "failing"
    assert health["sachet"]["last_error"] == polls["sachet"].error
    # The fixed poll clock is 2026-09-23 13:00 UTC, long before "now": USGS is stale.
    assert health["usgs"]["state"] == "stale"
    assert health["usgs"]["last_ok_at"] == "2026-09-23T13:00:00+00:00"
