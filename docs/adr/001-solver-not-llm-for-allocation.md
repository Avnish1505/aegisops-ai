# 001. A CP-SAT solver allocates units; the LLM does not

Status: Accepted (M1, 2026-09-23)

## Context

The first allocation engine that used a model (`LLMDecisionEngine`, NVIDIA NIM) asked the model
for a whole plan: which unit goes where, and the ETA. Nothing guaranteed the plan was feasible
(units that exist, are available and are used once), that the ETAs were real, or that it was
any good. The earlier safety gate took the model's own status and findings at face value, so a
plan could be wrong and still look approved-ready. Allocation is a small, well-posed
optimisation problem: minimise severity-weighted travel time plus a penalty per unit of unmet
demand, subject to hard rules. Exact solvers do this well.

## Decision

Plans come from OR-Tools CP-SAT over a travel-time matrix (OSRM road times). Operator
constraints are typed (reserve, exclude, priority) and never free text. The solver reports why a
set of constraints is infeasible. Models are used only to read reports, to translate a note into
one proposed constraint that the operator confirms, and to draft message prose. Every number
they produce is re-checked.

The LLM allocation engine remains an experiment arm, for measuring LLM-direct allocation
against the solver. Its output goes through the same verifier, which blocks anything infeasible.

## Consequences

- Plans are optimal for the stated objective, or explained as infeasible, and reproducible
  from the stored inputs.
- The objective must be written down. It is the one definition shared by the solver and the
  verifier (`aegisops/planning/objective.py`), so a reviewer can argue with it.
- The model can still err where it is used (reading, drafting). Those outputs are grounded or
  number-checked, not trusted.
- How much worse LLM-direct allocation is remains to be measured: the experiment is built but
  not run (no live model yet).

## Evidence

- `aegisops/planning/solver.py`; `tests/test_solver.py`
- `aegisops/application/decision_service.py` (every engine goes through `verify`)
- `evals/llm_vs_solver.py`; `tests/test_llm_vs_solver.py` (the harness, checked with an oracle)
