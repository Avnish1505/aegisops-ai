# 002. The verifier is pure functions over data

Status: Accepted (M1, 2026-09-23)

## Context

A safety check that does I/O, calls a model or reads a clock can give a different answer when
the same decision is looked at again, and it cannot be replayed. The check that mattered most,
"is this plan safe to show as approvable?", had depended on the engine's own claims.

## Decision

`verify(plan, scenario, *, reference_plan, travel_times, constraints, evidence, text_drafts,
policy)` is a pure function. It takes data and returns a `VerificationReport` of 19 named
checks, each with a severity, and a verdict. Any failed critical check blocks the plan. It does
not touch the network, the database, a model or the clock. Everything it needs, including the
travel matrix and the CP-SAT reference, is computed before it runs and stored with the
decision.

## Consequences

- The same stored record always gives the same report.
  `POST /api/v1/decisions/{id}/reverify` runs it again from the database alone, and a value
  edited in the database shows up as a differing check.
- Fault injection can test each check in isolation: mutate a clean plan and assert that the
  expected check fails.
- Checks are limited to what can be decided from data. For example, SITREP numbers are checked
  against a keyword grammar, and a number phrased differently fails as unattributed rather than
  being understood. Instruction detection is pattern-based.

## Evidence

- `aegisops/verification/verifier.py`; `tests/test_verifier.py`
- `reports/fault_injection.md`: 13/13 fault classes caught on every scenario, 650/650 faults,
  0/50 clean plans falsely blocked
- `aegisops/application/replay.py`;
  `tests/test_plan_review_api.py::test_reverify_catches_a_travel_time_edited_in_the_database`
