"""Evaluate the Read and Communicate steps and the end-to-end pipeline.

    python -m evals.fetch_humaid                 # once: fill in HumAID tweet text
    python -m evals.run                          # full eval (needs AEGISOPS_LLM_API_KEY)
    python -m evals.run --smoke                  # 20 reader cases from recorded cassettes (CI)
    python -m evals.run --record-smoke           # re-record those cassettes (needs a key)

Outputs reports/eval_<date>.md and .json (metrics with 95% bootstrap CIs, dataset SHA-256,
model, prompt versions, call counts and cost) and raw model outputs under reports/raw/eval_<date>/.

End-to-end scenarios plan on straight-line travel times so the eval runs without an OSRM server;
the LLM-vs-solver experiment (evals/llm_vs_solver.py) uses OSRM. Every call runs at temperature 0,
the production setting, so pass^5 measures run-to-run consistency on identical inputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aegisops.application.decision_service import DecisionService
from aegisops.communication.reporter import Reporter
from aegisops.core.config import Settings
from aegisops.domain.canonical import sha256_hex
from aegisops.domain.models import Scenario
from aegisops.intake.constraints import ConstraintTranslator
from aegisops.intake.gazetteer import DEFAULT_GAZETTEER, Gazetteer
from aegisops.intake.reader import Reader, to_incident
from aegisops.llm.client import CallRecord, LLMClient, LLMError, LLMOutputError
from aegisops.planning.travel import StraightLineProvider
from evals.metrics import (
    LOCATION_TOLERANCE_KM,
    Estimate,
    bootstrap,
    field_counts,
    field_report,
    location_error_km,
    mean,
    quantile,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "evals" / "data"
ASSEMBLED = DATA / ".cache" / "reports_v1.assembled.jsonl"
CASSETTES = ROOT / "evals" / "cassettes"
SMOKE_EXPECTED = ROOT / "evals" / "smoke_expected.json"
SMOKE_CASES = 20


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(path: Path) -> str:
    return sha256_hex(path.read_text(encoding="utf-8"))


def pmap(function: Callable[[Any], dict[str, Any]], items: Sequence[Any],
         workers: int) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(function, items))


def record_dict(record: CallRecord) -> dict[str, Any]:
    return {"prompt": f"{record.prompt_name}@{record.prompt_version}", "model": record.model,
            "input_tokens": record.input_tokens, "output_tokens": record.output_tokens,
            "latency_s": round(record.latency_s, 4), "cost_usd": record.cost_usd, "ok": record.ok}


# --- Reader ---------------------------------------------------------------------------------
def run_reader(
    reader: Reader, rows: Sequence[dict[str, Any]], workers: int
) -> list[dict[str, Any]]:
    def one(row: dict[str, Any]) -> dict[str, Any]:
        base = {"id": row["id"], "source": row["source"], "slices": row["slices"]}
        try:
            result = reader.read(row["text"])
        except LLMOutputError as error:
            return {**base, "error": "invalid_output", "raw": error.raw, "candidate": None}
        except LLMError as error:
            return {**base, "error": f"llm_error: {error}", "raw": None, "candidate": None}
        candidate = result.candidate.model_dump(mode="json")
        return {**base, "error": None, "candidate": candidate, "call": record_dict(result.record)}

    return pmap(one, rows, workers)


def _dropped_share(pairs: Sequence[tuple[int, int]]) -> float | None:
    total = sum(returned for _, returned in pairs)
    return sum(dropped for dropped, _ in pairs) / total if total else None


def score_reader(
    rows: Sequence[dict[str, Any]], outputs: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    by_id = {row["id"]: row for row in rows}
    scored: list[dict[str, Any]] = []
    geocode_errors: list[float] = []
    returned = dropped = 0
    severity_hits: list[float] = []
    for output in outputs:
        row = by_id[output["id"]]
        candidate = output["candidate"]
        counts = field_counts(row["gold"], candidate, row["labels_available"])
        scored.append({"counts": counts, "slices": row["slices"]})
        if candidate is not None:
            kept = (sum(candidate[k] is not None
                        for k in ("incident_type", "location_text", "people_count"))
                    + len(candidate["needs"]) + len(candidate["signals"]))
            returned += kept + len(candidate["dropped"])
            dropped += len(candidate["dropped"])
            error = location_error_km(row["gold"].get("location"), candidate.get("geocode"))
            if error is not None:
                geocode_errors.append(error)
        if row["gold"].get("severity") is not None:
            predicted = candidate["severity"] if candidate else None
            severity_hits.append(1.0 if predicted == row["gold"]["severity"] else 0.0)
    ungrounded = [
        (len(o["candidate"]["dropped"]),
         sum(o["candidate"][k] is not None for k in ("incident_type", "location_text",
                                                      "people_count"))
         + len(o["candidate"]["needs"]) + len(o["candidate"]["signals"])
         + len(o["candidate"]["dropped"]))
        for o in outputs if o["candidate"] is not None
    ]
    slices: dict[str, Any] = {}
    for name in ("en", "hi", "hinglish", "humaid", "no_location", "injection"):
        subset = [s for s in scored if name in s["slices"]]
        if subset:
            slices[name] = {"n": len(subset), "fields": field_report(subset)}
    return {
        "n": len(outputs),
        "failed_reads": sum(o["candidate"] is None for o in outputs),
        "invalid_output": sum(o["error"] == "invalid_output" for o in outputs),
        "fields": field_report(scored),
        "slices": slices,
        "ungrounded_field_rate": bootstrap(ungrounded, _dropped_share).as_dict(),
        "fields_returned": returned,
        "fields_dropped": dropped,
        "severity_accuracy": bootstrap(severity_hits, mean).as_dict(),
        "geocode_error_km": {
            "median": bootstrap(geocode_errors, lambda s: quantile(s, 0.5)).as_dict(),
            "p90": bootstrap(geocode_errors, lambda s: quantile(s, 0.9)).as_dict(),
            "within_tolerance": bootstrap(
                [1.0 if e <= LOCATION_TOLERANCE_KM else 0.0 for e in geocode_errors], mean
            ).as_dict(),
        },
    }


# --- Constraint notes -----------------------------------------------------------------------
def constraint_correct(gold: dict[str, Any], constraint: dict[str, Any] | None) -> bool:
    if constraint is None or constraint.get("kind") != gold["kind"]:
        return False
    if gold["kind"] == "reserve":
        zone = constraint["zone"]
        place = gold["place"]
        centre = {"lat": (zone["min_lat"] + zone["max_lat"]) / 2,
                  "lon": (zone["min_lon"] + zone["max_lon"]) / 2}
        distance = location_error_km(place, centre)
        return (constraint["resource_type"] == gold["resource_type"]
                and constraint["count"] == gold["count"]
                and distance is not None and distance <= LOCATION_TOLERANCE_KM)
    if gold["kind"] == "exclude_unit":
        return bool(constraint["unit_id"] == gold["unit_id"])
    return bool(constraint["incident_id"] == gold["incident_id"]
                and constraint["factor"] == gold["factor"])


def run_constraints(translator: ConstraintTranslator, notes: Sequence[dict[str, Any]],
                    scenario: Scenario, workers: int) -> list[dict[str, Any]]:
    def one(note: dict[str, Any]) -> dict[str, Any]:
        try:
            result = translator.translate(note["text"], scenario)
        except (LLMError, LLMOutputError) as error:
            return {"id": note["id"], "error": str(error), "proposal": None, "correct": False}
        proposal = result.proposal.model_dump(mode="json")
        return {"id": note["id"], "language": note["language"], "error": None,
                "draft": result.draft.model_dump(mode="json"), "proposal": proposal,
                "correct": constraint_correct(note["gold"], proposal["constraint"]),
                "call": record_dict(result.record)}

    return pmap(one, notes, workers)


# --- End to end -----------------------------------------------------------------------------
def run_e2e(reader: Reader, reporter: Reporter, scenarios: Sequence[dict[str, Any]],
            reports: dict[str, dict[str, Any]], units: list[dict[str, Any]], trials: int,
            workers: int) -> list[dict[str, Any]]:
    service = DecisionService({}, StraightLineProvider())

    def one(job: tuple[dict[str, Any], int]) -> dict[str, Any]:
        spec, trial = job
        calls: list[dict[str, Any]] = []
        incidents = []
        recovered = True
        for position, report_id in enumerate(spec["report_ids"], start=1):
            row = reports[report_id]
            try:
                result = reader.read(row["text"])
            except (LLMError, LLMOutputError):
                recovered = False
                continue
            calls.append(record_dict(result.record))
            candidate = result.candidate
            gold = row["gold"]
            error = location_error_km(
                gold["location"], candidate.geocode.model_dump() if candidate.geocode else None
            )
            type_ok = (candidate.incident_type is not None
                       and candidate.incident_type.value == gold["incident_type"])
            recovered &= type_ok and error is not None and error <= LOCATION_TOLERANCE_KM
            incident = to_incident(candidate, f"INC-E2E-{position}")
            if incident is not None:
                incidents.append(incident)
        base = {"id": spec["id"], "trial": trial, "calls": calls}
        if not incidents:
            return {**base, "pass": False, "recovered": False, "blocking_checks": None,
                    "sitrep_verified": False, "cost_usd": sum(c["cost_usd"] for c in calls)}
        scenario = Scenario.model_validate(
            {"scenario_id": f"SCEN-{spec['id']}",
             "incidents": [i.model_dump(mode="json") for i in incidents], "resources": units}
        )
        outcome = service.decide(scenario)
        drafts = reporter.draft(outcome.result, scenario, outcome.travel_times)
        calls += [record_dict(r) for r in drafts.records]
        sitrep_ok = drafts.sitrep.source == "llm" and drafts.sitrep.numbers_verified
        passed = recovered and not outcome.verification.blocking_check_ids and sitrep_ok
        return {**base, "pass": passed, "recovered": recovered,
                "blocking_checks": outcome.verification.blocking_check_ids,
                "sitrep_source": drafts.sitrep.source, "sitrep_verified": sitrep_ok,
                "sitrep_mismatches": drafts.sitrep.mismatches, "sitrep": drafts.sitrep.document,
                "cap_source": drafts.cap.source, "cap_verified": drafts.cap.numbers_verified,
                "cost_usd": sum(c["cost_usd"] for c in calls)}

    jobs = [(spec, trial) for spec in scenarios for trial in range(1, trials + 1)]
    return pmap(one, jobs, workers)


def score_e2e(outputs: Sequence[dict[str, Any]], trials: int) -> dict[str, Any]:
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for output in outputs:
        by_scenario.setdefault(output["id"], []).append(output)
    all_pass = [1.0 if all(t["pass"] for t in runs) else 0.0 for runs in by_scenario.values()]
    return {
        "scenarios": len(by_scenario),
        "trials": trials,
        f"pass^{trials}": bootstrap(all_pass, mean).as_dict(),
        "pass@1": bootstrap([1.0 if o["pass"] else 0.0 for o in outputs], mean).as_dict(),
        "reports_recovered": bootstrap([1.0 if o["recovered"] else 0.0 for o in outputs],
                                       mean).as_dict(),
        "plans_without_blocking_checks": bootstrap(
            [1.0 if o["blocking_checks"] == [] else 0.0 for o in outputs], mean).as_dict(),
        "sitrep_numeric_match": bootstrap(
            [1.0 if o["sitrep_verified"] else 0.0 for o in outputs], mean).as_dict(),
        "cap_numeric_match": bootstrap(
            [1.0 if o.get("cap_verified") and o.get("cap_source") == "llm" else 0.0
             for o in outputs], mean).as_dict(),
        "cost_per_decision_usd": bootstrap([o["cost_usd"] for o in outputs], mean).as_dict(),
    }


def latency(calls: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_prompt: dict[str, list[float]] = {}
    for call in calls:
        by_prompt.setdefault(call["prompt"], []).append(call["latency_s"])
    everything = [c["latency_s"] for c in calls]
    return {
        "all": {"n": len(everything), "p50_s": quantile(everything, 0.5),
                "p95_s": quantile(everything, 0.95)},
        **{prompt: {"n": len(values), "p50_s": quantile(values, 0.5),
                    "p95_s": quantile(values, 0.95)} for prompt, values in by_prompt.items()},
    }


# --- Report ---------------------------------------------------------------------------------
def fmt(estimate: dict[str, Any], percent: bool = True, digits: int = 1) -> str:
    return Estimate(estimate["value"], estimate["ci95"][0], estimate["ci95"][1],
                    estimate["n"]).fmt(percent, digits)


def markdown(results: dict[str, Any]) -> str:
    meta, reader, notes, e2e = (results["meta"], results["reader"], results["constraints"],
                                results["e2e"])
    pass_key = f"pass^{e2e['trials']}"
    lines = [
        f"# Eval report {meta['date']}",
        "",
        f"Model `{meta['model']}` via `{meta['base_url']}`; prompts "
        + ", ".join(f"`{p}`" for p in meta["prompt_versions"]) + ". Temperature 0.",
        f"Dataset SHA-256: reports `{meta['sha256']['reports']}`, notes "
        f"`{meta['sha256']['notes']}`, e2e `{meta['sha256']['e2e']}`, units "
        f"`{meta['sha256']['units']}`. Bootstrap: 2000 rounds, seed 20260923, 95% percentile CIs.",
        f"LLM calls {meta['calls']}; estimated total cost ${meta['total_cost_usd']:.4f} at "
        f"${meta['price_in']}/${meta['price_out']} per million input/output tokens "
        "(reference price, see ENVIRONMENT.md).",
        "",
        "## Reader (300 reports: 200 synthetic Lucknow, 100 HumAID)",
        "",
        "| Field | Precision | Recall | F1 |",
        "| --- | --- | --- | --- |",
    ]
    for name, scores in reader["fields"].items():
        lines.append(f"| {name} | {fmt(scores['precision'])} | {fmt(scores['recall'])} | "
                     f"{fmt(scores['f1'])} |")
    lines += [
        "",
        f"- Failed reads: {reader['failed_reads']} of {reader['n']} "
        f"(invalid JSON/schema: {reader['invalid_output']}).",
        f"- Ungrounded-field rate (returned fields dropped by grounding): "
        f"{fmt(reader['ungrounded_field_rate'])} ({reader['fields_dropped']} of "
        f"{reader['fields_returned']}).",
        f"- Severity accuracy (deterministic rules over extracted fields vs gold): "
        f"{fmt(reader['severity_accuracy'])}.",
        f"- Geocode error: median {fmt(reader['geocode_error_km']['median'], False, 2)} km, "
        f"p90 {fmt(reader['geocode_error_km']['p90'], False, 2)} km; within "
        f"{LOCATION_TOLERANCE_KM:g} km: {fmt(reader['geocode_error_km']['within_tolerance'])}.",
        "",
        "### Reader F1 by slice",
        "",
        "| Slice | n | type | location | people | needs | signals |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, slice_ in reader["slices"].items():
        cells = [fmt(slice_["fields"][f]["f1"]) if f in slice_["fields"] else "-"
                 for f in ("incident_type", "location", "people_count", "needs", "signals")]
        lines.append(f"| {name} | {slice_['n']} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Constraint translation (50 notes)",
        "",
        f"Accuracy {fmt(notes['accuracy'])}; by kind: "
        + ", ".join(f"{k} {fmt(v)}" for k, v in notes["by_kind"].items()) + ".",
        "",
        f"## End to end ({e2e['scenarios']} scenarios x {e2e['trials']} trials)",
        "",
        "Pass = every report read with the right type and a location within 1 km, a plan with no "
        "failed critical check, and an LLM SITREP whose every number passes the verifier.",
        "",
        f"- pass^{e2e['trials']}: {fmt(e2e[pass_key])}; pass@1 {fmt(e2e['pass@1'])}.",
        f"- Reports recovered: {fmt(e2e['reports_recovered'])}; plans without blocking checks: "
        f"{fmt(e2e['plans_without_blocking_checks'])}.",
        f"- SITREP numeric-match rate: {fmt(e2e['sitrep_numeric_match'])}; CAP text: "
        f"{fmt(e2e['cap_numeric_match'])}.",
        f"- Cost per decision: ${fmt(e2e['cost_per_decision_usd'], False, 5)}.",
        "",
        "## Latency per LLM call",
        "",
        "| Prompt | n | p50 s | p95 s |",
        "| --- | --- | --- | --- |",
    ]
    for prompt, stats in results["latency"].items():
        lines.append(f"| {prompt} | {stats['n']} | {stats['p50_s'] or 0:.2f} | "
                     f"{stats['p95_s'] or 0:.2f} |")
    lines += ["", "Raw outputs: `reports/raw/eval_" + meta["date"] + "/`.", ""]
    return "\n".join(lines)


def build_clients(settings: Settings) -> tuple[LLMClient, Reader, ConstraintTranslator, Reporter]:
    client = LLMClient(settings)
    gazetteer = Gazetteer.load(DEFAULT_GAZETTEER)
    return client, Reader(client, gazetteer), ConstraintTranslator(client, gazetteer), Reporter(
        client)


def smoke_rows() -> list[dict[str, Any]]:
    rows = [r for r in load_jsonl(DATA / "reports_v1.jsonl") if r["source"] == "synthetic_lucknow"]
    return rows[:SMOKE_CASES]


def smoke_summary(
    outputs: Sequence[dict[str, Any]], rows: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    scored = score_reader(rows, outputs)
    return {"failed_reads": scored["failed_reads"],
            "fields_dropped": scored["fields_dropped"],
            "f1": {k: v["f1"]["value"] for k, v in scored["fields"].items()},
            "severity_accuracy": scored["severity_accuracy"]["value"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--record-smoke", action="store_true")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None, help="Debug: first N of each suite.")
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    if args.smoke or args.record_smoke:
        settings = Settings(llm_cassette_mode="record" if args.record_smoke else "replay",
                            llm_cassette_dir=CASSETTES,
                            llm_max_retries=5)
        _, reader, _, _ = build_clients(settings)
        rows = smoke_rows()
        summary = smoke_summary(run_reader(reader, rows, workers=1), rows)
        if args.record_smoke:
            SMOKE_EXPECTED.write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
            print(f"recorded {len(rows)} cassettes; expected summary in {SMOKE_EXPECTED.name}")
            return
        expected = json.loads(SMOKE_EXPECTED.read_text())
        print(json.dumps(summary, indent=1, sort_keys=True))
        if summary != expected:
            sys.exit("smoke eval differs from evals/smoke_expected.json")
        print(f"smoke eval matches ({len(rows)} replayed cases)")
        return

    settings = Settings(llm_max_retries=5)
    client, reader, translator, reporter = build_clients(settings)
    if not client.available:
        sys.exit("No LLM key: set AEGISOPS_LLM_API_KEY (see ENVIRONMENT.md).")
    if not ASSEMBLED.exists():
        sys.exit("Run `python -m evals.fetch_humaid` first to fill in HumAID text.")
    reports = load_jsonl(ASSEMBLED)
    notes = load_jsonl(DATA / "notes_v1.jsonl")
    scenarios = load_jsonl(DATA / "e2e_v1.jsonl")
    exercise = Scenario.model_validate_json((DATA / "lucknow_exercise_v1.json").read_text())
    if args.limit:
        reports, notes, scenarios = reports[:args.limit], notes[:args.limit], scenarios[:args.limit]

    raw = ROOT / "reports" / "raw" / f"eval_{args.date}"
    raw.mkdir(parents=True, exist_ok=True)
    reader_out = run_reader(reader, reports, args.workers)
    notes_out = run_constraints(translator, notes, exercise, args.workers)
    e2e_out = run_e2e(reader, reporter, scenarios, {r["id"]: r for r in reports},
                      [u.model_dump(mode="json") for u in exercise.resources], args.trials,
                      args.workers)
    for name, rows in (("reader", reader_out), ("constraints", notes_out), ("e2e", e2e_out)):
        (raw / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    calls = ([o["call"] for o in reader_out if o.get("call")]
             + [o["call"] for o in notes_out if o.get("call")]
             + [c for o in e2e_out for c in o["calls"]])
    kinds = Counter(note["gold"]["kind"] for note in notes)
    results = {
        "meta": {
            "date": args.date, "model": client.model, "base_url": settings.llm_base_url,
            "prompt_versions": sorted({c["prompt"] for c in calls}),
            "sha256": {"reports": sha(ASSEMBLED), "notes": sha(DATA / "notes_v1.jsonl"),
                       "e2e": sha(DATA / "e2e_v1.jsonl"),
                       "units": sha(DATA / "lucknow_exercise_v1.json")},
            "calls": len(calls), "total_cost_usd": sum(c["cost_usd"] for c in calls),
            "price_in": settings.llm_price_in_usd_per_mtok,
            "price_out": settings.llm_price_out_usd_per_mtok, "limit": args.limit,
        },
        "reader": score_reader(reports, reader_out),
        "constraints": {
            "accuracy": bootstrap(
                [1.0 if o["correct"] else 0.0 for o in notes_out], mean
            ).as_dict(),
            "by_kind": {
                kind: bootstrap(
                    [1.0 if o["correct"] else 0.0 for o, n in zip(notes_out, notes, strict=True)
                     if n["gold"]["kind"] == kind], mean).as_dict()
                for kind in kinds
            },
        },
        "e2e": score_e2e(e2e_out, args.trials),
        "latency": latency(calls),
    }
    out = ROOT / "reports" / f"eval_{args.date}"
    out.with_suffix(".json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(markdown(results), encoding="utf-8")
    print(f"wrote {out}.md and .json; raw outputs in {raw}")


if __name__ == "__main__":
    main()
