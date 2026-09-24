"""Fill in HumAID tweet text for evals/data/reports_v1.jsonl, which stores tweet IDs only.

    python -m evals.fetch_humaid

Downloads the public HumAID event-wise set 1 (Alam et al., ICWSM 2021; crisisnlp.qcri.org), which
publishes tweet ID, text and label, and writes evals/data/.cache/reports_v1.assembled.jsonl with the
text filled in. Tweet text is not committed to this repository.
"""

from __future__ import annotations

import csv
import io
import json
import tarfile
from pathlib import Path

import httpx

URL = "https://crisisnlp.qcri.org/data/humaid/HumAID_data_events_set1_47K.tar.gz"
DATA = Path(__file__).parent / "data"
CACHE = DATA / ".cache"
ASSEMBLED = CACHE / "reports_v1.assembled.jsonl"


def tweet_texts(archive: bytes) -> dict[str, str]:
    texts: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile() and member.name.endswith(".tsv"):
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                rows = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8"), delimiter="\t")
                for row in rows:
                    texts[row["tweet_id"]] = row["tweet_text"]
    return texts


def assemble(texts: dict[str, str]) -> list[dict[str, object]]:
    rows = [json.loads(line) for line in (DATA / "reports_v1.jsonl").read_text().splitlines()]
    missing = []
    for row in rows:
        if row["source"] == "humaid":
            text = texts.get(str(row["tweet_id"]))
            if text is None:
                missing.append(row["tweet_id"])
            row["text"] = text
    if missing:
        raise SystemExit(f"{len(missing)} HumAID tweets not found in the archive: {missing[:5]}")
    return rows


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    archive_path = CACHE / "HumAID_data_events_set1_47K.tar.gz"
    if not archive_path.exists():
        response = httpx.get(URL, follow_redirects=True, timeout=120)
        response.raise_for_status()
        archive_path.write_bytes(response.content)
    rows = assemble(tweet_texts(archive_path.read_bytes()))
    ASSEMBLED.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )
    print(f"wrote {ASSEMBLED} ({len(rows)} reports)")


if __name__ == "__main__":
    main()
