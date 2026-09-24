"""Read the demo triage reports once with the configured model and store the readings.

    AEGISOPS_LLM_API_KEY=... python scripts/record_demo_reads.py

Writes backend/demo_reads.json (candidate + model, prompt version, tokens, latency, cost per
report, keyed by the report's SHA-256), which the demo seed loads so visitors never call a model.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from aegisops.core.config import Settings
from aegisops.domain.canonical import sha256_hex
from aegisops.intake.gazetteer import DEFAULT_GAZETTEER, Gazetteer
from aegisops.intake.reader import Reader
from aegisops.llm.client import LLMClient
from backend.demo_intake import READS, REPORTS


def main() -> None:
    client = LLMClient(Settings(llm_max_retries=5))
    if not client.available:
        sys.exit("No LLM key: set AEGISOPS_LLM_API_KEY (see ENVIRONMENT.md).")
    reader = Reader(client, Gazetteer.load(DEFAULT_GAZETTEER))
    reads = {}
    for text in json.loads(REPORTS.read_text("utf-8"))["reports"]:
        result = reader.read(text)
        reads[sha256_hex(text)] = {
            "candidate": result.candidate.model_dump(mode="json"),
            "read_meta": {
                "model": result.record.model,
                "prompt_version": result.record.prompt_version,
                "input_tokens": result.record.input_tokens,
                "output_tokens": result.record.output_tokens,
                "latency_s": round(result.record.latency_s, 3),
                "cost_usd": result.record.cost_usd,
            },
        }
        print(f"read {len(reads)}: dropped={result.candidate.dropped}")
    READS.write_text(json.dumps({
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": client.model,
        "reads": reads,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {READS}")


if __name__ == "__main__":
    main()
