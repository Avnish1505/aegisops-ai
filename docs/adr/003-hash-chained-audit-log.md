# 003. Every step is an append-only, hash-chained event

Status: Accepted (M1, 2026-09-23)

## Context

An insert-only audit table by convention proves nothing. Rows can be edited or deleted with
direct database access, and no one would know. A replayable decision needs its record, and the
record of who did what, to be tamper-evident.

## Decision

Every step appends an event to one chain:

- a proposal, its verification and a disposition;
- drafts and re-verification;
- each intake step and study session.

Each event stores `prev_hash` and `hash = sha256(prev_hash || canonical JSON of id, time, actor,
type, payload)`. Events that create a decision or approval row also carry a hash of that row, so
editing the row breaks the chain. `GET /api/v1/audit/verify` walks the chain and reports the
first broken link.

## Consequences

- Editing or deleting any event, or editing a hashed decision or approval row, is detected.
- Deleting the newest event cannot be detected from inside the database. That needs a head hash
  kept somewhere else, and the console says so.
- Appends are serialised through the chain head (fine at this scale).
- The public demo's hourly reset restarts the chain at genesis; that is what a sandbox does.

## Evidence

- `aegisops/audit/event_log.py`; `tests/test_event_chain.py`
- `src/features/audit/Audit.tsx` (chain status and re-verification in the console)
