"""Poll NDMA SACHET (CAP 1.2), USGS and GDACS and store new alerts.

    python -m aegisops.ingestion.worker          # run forever on the configured intervals
    python -m aegisops.ingestion.worker --once   # poll every feed once and exit

Why APScheduler, not arq + Redis: the job is three periodic HTTP polls with no fan-out, so a
job queue and its broker would be one more service to run and secure for no capability we use.
Correctness does not depend on exactly-once scheduling: every alert is deduplicated by the
(source, identifier) unique constraint, so an overlapping run, a restart mid-poll or a second
worker replica cannot create duplicates. Jobs use coalesce=True and max_instances=1, so a slow
feed never stacks runs. A queue earns its place once work fans out per alert (for example an
LLM Read step on every CAP message); that is not the case yet.

A failing feed is logged and skipped; it never stops the other feeds or the scheduler.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from aegisops.core.config import Settings
from aegisops.ingestion.cap import CapParseError, cap_to_record
from aegisops.ingestion.feeds import FeedParseError, parse_gdacs, parse_sachet_rss, parse_usgs
from aegisops.ingestion.models import AlertRecord
from aegisops.ingestion.store import StoreResult, known_source_refs, store_alerts

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PollResult:
    source: str
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    invalid: int = 0
    error: str | None = None


class Poller:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings: Settings,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._settings = settings
        self._client = client or httpx.Client(
            timeout=settings.ingest_timeout_s,
            headers={"User-Agent": settings.ingest_user_agent},
            follow_redirects=True,
        )
        self._now = clock or (lambda: datetime.now(UTC))

    def poll_sachet(self) -> PollResult:
        return self._guarded("sachet", self._sachet)

    def poll_usgs(self) -> PollResult:
        return self._guarded(
            "usgs", lambda: self._geojson("usgs", self._settings.ingest_usgs_url, parse_usgs)
        )

    def poll_gdacs(self) -> PollResult:
        return self._guarded(
            "gdacs", lambda: self._geojson("gdacs", self._settings.ingest_gdacs_url, parse_gdacs)
        )

    def poll_all(self) -> list[PollResult]:
        return [self.poll_sachet(), self.poll_usgs(), self.poll_gdacs()]

    def _guarded(self, source: str, poll: Callable[[], PollResult]) -> PollResult:
        try:
            result = poll()
        except (httpx.HTTPError, FeedParseError) as error:
            logger.warning("feed_poll_failed source=%s error=%s", source, error)
            return PollResult(source=source, error=f"{type(error).__name__}: {error}")
        logger.info(
            "feed_polled source=%s fetched=%d inserted=%d duplicates=%d invalid=%d",
            source, result.fetched, result.inserted, result.duplicates, result.invalid,
        )
        return result

    def _get(self, url: str) -> bytes:
        response = self._client.get(url)
        response.raise_for_status()
        return response.content

    def _sachet(self) -> PollResult:
        items = parse_sachet_rss(self._get(self._settings.ingest_sachet_rss_url))
        with self._sessions() as session:
            already = known_source_refs(session, "sachet")
        records: list[AlertRecord] = []
        invalid = 0
        skipped = 0
        for item in items[: self._settings.ingest_max_cap_per_poll]:
            if item.guid in already:
                skipped += 1  # CAP document already stored; do not download it again
                continue
            try:
                records.append(cap_to_record(self._get(item.link), source_ref=item.guid))
            except CapParseError as error:
                invalid += 1
                logger.warning("cap_rejected guid=%s error=%s", item.guid, error)
        stored = self._store(records)
        return PollResult(
            source="sachet",
            fetched=len(items),
            inserted=stored.inserted,
            duplicates=stored.duplicates + skipped,
            invalid=invalid,
        )

    def _geojson(
        self, source: str, url: str, parse: Callable[[bytes], list[AlertRecord]]
    ) -> PollResult:
        records = parse(self._get(url))
        stored = self._store(records)
        return PollResult(
            source=source,
            fetched=len(records),
            inserted=stored.inserted,
            duplicates=stored.duplicates,
        )

    def _store(self, records: list[AlertRecord]) -> StoreResult:
        with self._sessions() as session, session.begin():
            return store_alerts(session, records, fetched_at=self._now())


def build_scheduler(poller: Poller, settings: Settings) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=UTC)
    first_run = datetime.now(UTC)
    for job_id, poll, minutes in (
        ("sachet", poller.poll_sachet, settings.ingest_sachet_interval_min),
        ("usgs", poller.poll_usgs, settings.ingest_usgs_interval_min),
        ("gdacs", poller.poll_gdacs, settings.ingest_gdacs_interval_min),
    ):
        scheduler.add_job(
            poll,
            "interval",
            id=job_id,
            minutes=minutes,
            coalesce=True,
            max_instances=1,
            next_run_time=first_run,
        )
    return scheduler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Poll every feed once and exit.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    poller = Poller(sessionmaker(bind=create_engine(settings.database_url)), settings)
    if args.once:
        for result in poller.poll_all():
            print(result)
        return
    build_scheduler(poller, settings).start()


if __name__ == "__main__":
    main()
