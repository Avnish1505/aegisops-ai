# Research Proposal: Safety-Contract Evaluation of a Deterministic Baseline vs. a Retrieval-Augmented LLM Decision Engine

This proposal is scoped entirely to capabilities already implemented in this repository
(Phase 1–3 of `docs/ROADMAP.md`). It does not propose new engines, new data sources, or any
production/dispatch capability — consistent with `knowledge/operational-limitations.md`, this
remains a research and portfolio platform, not an emergency dispatch system. It corresponds to
the "research proposal" deliverable listed under Phase 4 of `docs/ROADMAP.md`.

## Problem Statement

AegisOps AI already implements two interchangeable decision engines behind the same
`DecisionEngine` protocol (`aegisops/application/ports.py`): a deterministic, transparent
baseline (`aegisops/infrastructure/rule_based_engine.py`, policy in
`aegisops/domain/policy.py`) and a retrieval-augmented LLM engine backed by NVIDIA NIM
(`aegisops/infrastructure/llm_decision_engine.py`), grounded in a local knowledge corpus via
`aegisops/infrastructure/retrieval_engine.py`. Both are required to satisfy the same safety
contract: every recommendation must set `requires_human_approval: true`, must not double-assign
a resource, and must raise a safety finding (`aegisops/domain/models.py::SafetyFinding`) and
block on unmet critical/high-severity requirements (`aegisops/domain/policy.py::evaluate_safety_gates`).

What is missing is a rigorous, reproducible account of how these two implementations actually
compare under that shared contract: whether the LLM path preserves the same safety invariants as
the deterministic baseline, how often and why it safely blocks rather than guesses, and what it
costs operationally (latency, availability) relative to the baseline. The project already has the
tooling to answer this (`sim/evaluation_harness.py`, `sim/compare_engines.py`,
`sim/experiment_report.py`) and a first-pass artifact (`reports/phase_3_visualization_summary.md`),
but no standing research plan ties these together into a repeatable study with defined objectives,
metrics, and pass/fail criteria.

## Objectives

- **O1 — Behavioral comparison.** Characterize where the rule-based baseline and the LLM/RAG
  engine agree and diverge on coverage, unmet-requirement handling, and blocking behavior across
  the existing golden scenarios (`sim/golden_scenarios.py`) and seeded scenario generation
  (`sim/scenario_generator.py`).
- **O2 — Safety-contract parity.** Verify that the safety contract enforced independently of
  provider (`sim/evaluation_harness.py::_validate_safety_contract`) — mandatory human approval, no
  duplicate assignments, no invalid resource/incident references — holds identically for both
  engines, not just for the baseline it was originally written against.
- **O3 — Operational cost.** Quantify the latency distribution (already computed as percentiles in
  `sim/compare_engines.py::_percentile`) and the blocked-fallback rate of the LLM engine
  (`aegisops/infrastructure/llm_decision_engine.py::_blocked_result`, triggered by missing
  `NVIDIA_API_KEY` or provider response validation failure) relative to the always-available
  deterministic baseline.
- **O4 — Grounding and robustness.** Use the retrieval provenance already returned by
  `RetrievalEngine.retrieve_evidence` (`Evidence.source`, `Evidence.confidence`) and the existing
  adversarial test summary (`sim/experiment_report.py::_adversarial_test_summary`) to assess how
  well LLM recommendations are grounded in the local knowledge corpus versus how often they must
  be blocked as unsafe or invalid.

## Methodology

The study reuses existing tooling exclusively — no new engine, dataset, or capability is
introduced:

1. **Fixed regression suite.** Run both engines against every scenario in
   `sim/golden_scenarios.golden_scenarios()` via `sim/evaluation_harness.evaluate()`, which already
   reports per-engine pass/fail against hand-authored expectations and provider-independent safety
   regressions.
2. **Seeded comparative runs.** Run both engines across a range of seeds using
   `sim/compare_engines.py`, which already generates reproducible scenarios via
   `aegisops/application/scenario_service.generate_scenario` and records coverage, unmet
   requirements, safety findings by severity, and latency for each run.
3. **Blocked-fallback exercise.** Run the LLM engine under the two conditions it already handles
   explicitly — no `NVIDIA_API_KEY` set, and a forced provider validation failure — to record how
   often and under what circumstances it takes the safe path defined in
   `_blocked_result` instead of returning an unvalidated recommendation.
4. **Provenance capture.** For every LLM recommendation, retain the `Evidence` records already
   attached via `retrieve_evidence`, to compute what fraction of recommendations cite corpus
   sources versus operate without supporting evidence.
5. **Report assembly.** Combine the above using `sim/experiment_report.py`, and render the result
   with `sim/visualization.py`, following the same coverage/latency/blocked-rate/safety-finding/
   adversarial-pass-rate/provenance-coverage charts already produced for
   `reports/phase_3_visualization_summary.md`.

Reproducibility is inherent to the existing tooling: golden scenarios are fixed and named,
seeded scenarios are deterministic given a seed, and the LLM engine already accepts a
`prompt_version` parameter (`aegisops/infrastructure/prompt_templates.py`) so results can be
re-run and diffed across prompt revisions without code changes.

## Evaluation Plan

- **Acceptance basis.** The study's own findings must reproduce under the existing test suite —
  `pytest tests/test_evaluation_harness.py tests/test_decision_engine.py
  tests/test_llm_decision_engine.py tests/test_security.py` — before being reported as valid.
- **Primary metrics** (all already computed by existing tooling, none newly defined):
  coverage/`advisory_confidence`, unmet-requirement count and unit total, safety-finding counts by
  severity, blocked rate, latency percentiles (p50/p95), and adversarial pass rate.
- **Hard gate.** Any scenario where an engine's output fails
  `_validate_safety_contract` — missing human approval, a duplicated or invalid assignment — is a
  disqualifying failure regardless of any other metric. This mirrors
  `knowledge/safety-gates.md` and `knowledge/human-approval.md`: the human-approval invariant is
  non-negotiable and is not something a favorable coverage number can offset.
- **Baseline-relative framing.** The deterministic engine's golden-scenario expectations remain
  ground truth throughout; the LLM engine is scored on divergence from that baseline, not treated
  as an independent oracle.
- **Change detection.** Because scenarios are seed- or fixture-derived, the same evaluation can be
  re-run after any prompt, model, or retrieval corpus change to detect regressions before they
  reach the safety-gate tests already in `tests/test_evaluation_harness.py`.

## Expected Contributions

- A reproducible, safety-contract-first methodology for comparing a deterministic baseline against
  an LLM/RAG-based decision engine implemented behind a shared protocol — applicable to any
  human-in-the-loop advisory system, not specific to this codebase.
- An empirical (not projected) account of where the two currently implemented engines agree and
  diverge on coverage, blocking behavior, and safety findings.
- A quantified blocked-fallback rate for the LLM engine under credential and validation failure,
  informing whether the existing "block rather than guess" design in
  `llm_decision_engine.py` is sufficient as implemented, or needs a documented follow-up.
- A regenerable report (via `sim/experiment_report.py` and `sim/visualization.py`) that produces
  the same class of artifact as `reports/phase_3_visualization_summary.md` for any future
  prompt/model version, without additional tooling.
- A concrete, evidence-backed input to the Phase 4 "IEEE-style paper" item in `docs/ROADMAP.md`,
  since this proposal only formalizes evaluation of what Phases 1–3 already built.
