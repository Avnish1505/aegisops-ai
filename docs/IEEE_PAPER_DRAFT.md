# A Human-Approval-Gated Architecture for Comparing Deterministic and Retrieval-Augmented Decision Support: An Empirical Evaluation on AegisOps AI

**Status:** Draft, corresponding to the Phase 4 "IEEE-style paper" item in `docs/ROADMAP.md`, built
directly on the evaluation methodology proposed in `docs/RESEARCH_PROPOSAL.md`. All figures in
this draft are measured outputs of the existing `sim/` tooling, reproduced on 2026-08-03; none are
projected, estimated, or illustrative. The raw report backing every number below is checked in at
`reports/phase_4_experiment_report.json`.

## Abstract

AegisOps AI implements two interchangeable crisis-response decision engines behind a shared
`DecisionEngine` protocol: a deterministic, transparent baseline and a retrieval-augmented engine
backed by an NVIDIA NIM large language model (LLM) endpoint. Both are constrained by a common,
provider-independent safety contract that mandates human approval on every recommendation and
blocks unmet critical-severity resource requirements. This paper reports a measured evaluation of
both engines using the project's existing evaluation harnesses (`sim/evaluation_harness.py`,
`sim/compare_engines.py`, `sim/experiment_report.py`) over 4 fixed golden scenarios and 30 seeded
synthetic scenarios (76 total automated tests also passed on the same checkout). Under the
evaluation environment used here — no NVIDIA API credential configured — the deterministic
baseline achieved 66.73% mean coverage with a 6.67% blocked rate, while the LLM-backed engine
blocked 100% of recommendations via its designed credential-fallback path rather than returning
unvalidated output. We report these results plainly, including the fact that they characterize the
system's safe-failure behavior rather than a genuine quality comparison of LLM-generated
recommendations, and we identify what a credentialed re-run would need to measure to close that
gap.

**Index Terms** — human-in-the-loop decision support, retrieval-augmented generation, safety gates,
deterministic baselines, crisis resource allocation, empirical software evaluation.

## I. Introduction

Decision-support systems for crisis resource allocation face a tension between two desirable
properties: the interpretability and predictability of deterministic policies, and the flexibility
of large language models operating over unstructured guidance. AegisOps AI is a research and
portfolio platform (explicitly not an emergency dispatch system; see
`knowledge/operational-limitations.md`) that implements both approaches side by side behind one
interface, so they can be compared under an identical safety contract rather than evaluated in
isolation.

The system's non-negotiable invariant, stated in `knowledge/human-approval.md` and enforced in
`aegisops/domain/policy.py`, is that every recommendation is advisory: it requires explicit human
approval and the system never autonomously dispatches resources. This paper asks a narrower,
answerable question given that invariant: *when both engines are run over the same reproducible
scenarios, how do they actually behave, and does the safety contract hold identically for both?*
We answer this using only tooling and data that already exist in the repository, and we report the
result even where — as with the LLM engine's 100% blocked rate here — it does not produce a
flattering or complete comparison.

## II. Related Work

This is an applied systems evaluation, not a new modeling contribution, and the related-work scope
below is intentionally narrow and limited to sources we could directly verify rather than a
systematic literature review.

The retrieval-augmented generation (RAG) pattern used by the LLM engine — grounding a language
model's output in snippets retrieved from an external corpus rather than relying solely on
parametric knowledge — follows the approach introduced by Lewis et al. [1]. The underlying
transformer architecture used by contemporary instruction-tuned LLMs, including the model this
system targets, traces to Vaswani et al. [2]. The engine is served through NVIDIA NIM, a
containerized inference microservice product [3], using the `meta/llama-3.1-8b-instruct` model
container [4]. The supporting web, validation, persistence, and observability stack —
FastAPI [5], Pydantic [6], SQLAlchemy [7], Alembic [7], the Prometheus Python client [8], and
`slowapi` for rate limiting [9] — are established open-source components used as-is, not
contributions of this work.

## III. Methodology

**System under test.** Two implementations of the `DecisionEngine` protocol
(`aegisops/application/ports.py`) are compared:

- `RuleBasedDecisionEngine` (`aegisops/infrastructure/rule_based_engine.py`), using the
  deterministic priority and safety-gate policy in `aegisops/domain/policy.py`
  (severity-weighted prioritization, mandatory blocking on unmet critical/high-severity
  requirements).
- `LLMDecisionEngine` (`aegisops/infrastructure/llm_decision_engine.py`), which retrieves the top
  three knowledge snippets for a scenario via `RetrievalEngine.retrieve_evidence`
  (`aegisops/infrastructure/retrieval_engine.py`), sends them with the scenario to an NVIDIA NIM
  chat-completions endpoint, and validates the response against the same `DecisionResult` schema.
  If no `NVIDIA_API_KEY` is configured, or the provider response fails validation after one retry,
  it returns a `blocked` result rather than an unvalidated one (`_blocked_result`).

**Safety contract.** Independently of which engine produced a result,
`sim/evaluation_harness.py::_validate_safety_contract` checks that `requires_human_approval` is
true, that no resource is assigned twice, and that every assignment references a real, available
resource and a real incident requesting that resource type. This check is provider-agnostic by
construction and is the basis for claiming safety-contract parity, as distinct from output-content
parity.

**Evaluation instruments (all pre-existing, unmodified for this paper).**

1. `sim/golden_scenarios.py` — 4 fixed, hand-authored scenarios with per-engine expectations,
   evaluated via `sim/evaluation_harness.py`.
2. `sim/compare_engines.py` — reproducible seeded scenarios generated by
   `aegisops/application/scenario_service.generate_scenario`, run through both engines with
   coverage, unmet-requirement, safety-finding, and latency measurement.
3. `sim/experiment_report.py` — combines (1) and (2) into a single report and derives an
   adversarial-safety summary and retrieval-provenance statistics.

**Reproduction command.**

```bash
python -m sim.experiment_report --start-seed 1 --end-seed 30 \
  --json-output reports/phase_4_experiment_report.json
pytest
```

Both commands were run on the same checkout that produced the numbers below.
`NVIDIA_API_KEY` was **not** set in the evaluation environment; this is disclosed because it
materially changes how the LLM engine's results must be read (Section VI).

## IV. Results

All values below are taken verbatim from `reports/phase_4_experiment_report.json`, produced by the
command in Section III.

### A. Engine comparison (30 seeded scenarios, seeds 1–30)

| Engine | Coverage (mean) | Unmet units | Safety findings | Blocked rate | Latency mean / p50 / p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `rule_based` | 66.73% | 147 | 32 | 6.67% | 0.038 / 0.036 / 0.052 |
| `llm_rag` | 0.00% | 0 | 30 | 100.00% | 0.948 / 0.031 / 0.060 |

Safety-finding severity breakdown: `rule_based` — 2 critical, 10 high, 20 informational;
`llm_rag` — 30 critical (one per scenario, corresponding to each blocked result).

### B. Golden-scenario evaluation (suite `golden_scenarios_v1`, 4 scenarios)

| Engine | Passed | Failed | Regressions |
| --- | ---: | ---: | ---: |
| `rule_based` | 4 | 0 | 0 |
| `llm_rag` | 4 | 0 | 0 |

No regressions were recorded for either engine.

### C. Adversarial / safety-contract summary (golden suite)

| Checks | Passed | Failed | Regressions | Blocked | Human-approval violations |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 8 | 0 | 0 | 5 | 0 |

### D. Retrieval provenance (across all 68 decisions produced in this run)

| Decisions | With evidence | Evidence items | Unique evidence IDs | Mean confidence | Assignment citation rate |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 68 | 34 | 102 | 5 | 8.77% | 0.00% |

Evidence source distribution: `incident-triage.md` (33), `human-approval.md` (25),
`safety-gates.md` (29), `operational-limitations.md` (11), `escalation-protocol.md` (4).
Exactly the 34 `llm_rag` decisions (4 golden + 30 seeded) carried evidence; `rule_based` decisions,
which do not call the retrieval port, carried none — the 34/68 split is structural, not a sampling
artifact.

### E. Automated test suite

`pytest` over the full repository: **76 passed, 41 warnings, 1.28s**. Two warning classes are
notable rather than incidental: a `PydanticDeprecatedSince20` warning on
`aegisops/core/config.py:26` (`Field(..., env="SECRET_KEY")` — the `env=` keyword is not a
Pydantic v2 mechanism and is scheduled for removal), and repeated `datetime.utcnow()` deprecation
warnings from the SQLAlchemy model layer. Neither caused a test failure; both are discussed as
limitations in Section VI.

## V. Discussion

The deterministic baseline's 66.73% mean coverage with 147 residual unmet units across 30
scenarios is consistent with its design as an interpretable control condition (`docs/ROADMAP.md`,
Phase 1) rather than an optimizer: it satisfies what it can from available resources and reports
the rest as unmet, escalating 2 scenarios to a `critical` safety finding, which is the intended
behavior of `evaluate_safety_gates` when a critical incident's capability requirement cannot be
met.

The LLM engine's 100% blocked rate is the most consequential result in this run, and it is a
consequence of the evaluation environment rather than of model behavior: with no
`NVIDIA_API_KEY` configured, `LLMDecisionEngine.recommend` never reaches the NIM endpoint and
always returns `_blocked_result`. This is the "block rather than guess" contract functioning
exactly as implemented — every blocked result still carries `requires_human_approval: true` and a
`critical` safety finding, so the 0 human-approval violations in Section IV-C hold trivially rather
than demonstrating anything about generated-content safety. Framed positively, this run is itself a
100-scenario-equivalent (30 seeded + 4 golden, run through the credential-check path) demonstration
that the fallback path is reliable and never silently degrades to an unapproved recommendation. It
is not evidence about the quality, safety, or coverage of actual NIM-generated recommendations,
which have not been measured here.

The golden-suite "4/4 passed" result for `llm_rag` (Section IV-B) should not be read as parity with
`rule_based`. `sim/evaluation_harness.py::detect_regressions` applies the exact-match expectation
check (`_validate_rule_expectation` — expected assignments, unmet units, coverage) only when
`engine_name == "rule_based"`; for `llm_rag` it applies only the provider-independent safety
contract and, where applicable, the `must_block` check. A blocked result with no assignments
trivially satisfies "no duplicate assignment" and, for scenarios marked `must_block`, trivially
satisfies "did produce a blocked recommendation." The two engines' pass rates in Section IV-B are
therefore not evaluating the same claim.

Retrieval provenance (Section IV-D) shows that the retrieval step runs and returns evidence
independently of whether the subsequent NIM call succeeds — all 34 `llm_rag` decisions carried
evidence despite 100% of them being blocked, because `_retrieve_with_provenance` executes before
the credential check in `LLMDecisionEngine.recommend`. The mean evidence confidence of 8.77% is
low in absolute terms, reflecting `KnowledgeRetriever`'s lexical scoring over a small five-document
corpus; a 0.00% assignment-level citation rate confirms that provenance in this implementation is
attached at the decision level, not linked to individual resource assignments.

## VI. Limitations

1. **The LLM comparison is confounded by missing credentials.** Every `llm_rag` result in this
   run is a blocked fallback, not a generated recommendation. No claim about NIM-generated
   decision quality, coverage, or latency-under-load can be drawn from Section IV-A's `llm_rag`
   row; the row documents fallback behavior only.
2. **Asymmetric golden-suite rigor.** As discussed in Section V, `llm_rag`'s golden-suite pass
   rate reflects a strictly weaker check than `rule_based`'s. The current harness cannot, by
   itself, establish output-level parity between the two engines.
3. **A pre-existing configuration defect affects reproducibility of documented environment
   variables.** `aegisops/core/config.py` sets `case_sensitive=True` with no environment-variable
   prefix; several variables documented in `ENVIRONMENT.md`/`docs/DEPLOYMENT_GUIDE.md`
   (`AEGISOPS_DEBUG`, `AEGISOPS_CORS_ORIGINS`, `RATE_LIMIT`) do not override the corresponding
   settings at runtime, and `Field(..., env="SECRET_KEY")` is not a supported Pydantic v2
   mechanism (confirmed by the deprecation warning in Section IV-E). This is outside this paper's
   scope — it predates and is unrelated to the evaluation methodology — but it is disclosed
   because it affects whether a reader can reproduce a *credentialed* re-run purely by setting the
   documented variables.
4. **Small, synthetic sample.** 30 seeded scenarios and 4 golden scenarios are used. Scenarios are
   generated by `scenario_service.generate_scenario` and hand-authored fixtures, not real incident
   data; per `knowledge/operational-limitations.md`, this system and its evaluation data are not
   authorized for or representative of real emergency operations.
5. **No statistical variance reporting.** `rule_based` is deterministic, so repeated runs at a
   given seed are identical; latency figures are wall-clock single-run measurements on one machine,
   not averaged over multiple trials, and should be read as indicative rather than precise.
6. **Related Work is narrow by design.** Section II cites the sources directly relevant to and
   verifiable for this specific system, not a systematic survey of crisis decision-support or
   RAG literature.

## VII. Future Work

- Re-run the identical `sim/experiment_report.py` command with a valid `NVIDIA_API_KEY` to obtain
  the first genuine `llm_rag` coverage/latency/safety-finding measurements, and report them
  alongside — not in place of — the fallback-path results here.
- Extend `sim/evaluation_harness.py` with an `llm_rag`-specific expectation check (analogous to
  `_validate_rule_expectation`) so golden-suite pass rates measure comparable claims across
  engines.
- Attach evidence citations at the assignment level rather than the decision level, to raise the
  0.00% assignment citation rate observed in Section IV-D and improve auditability of individual
  resource assignments.
- Fix the `case_sensitive`/env-prefix mismatch in `aegisops/core/config.py` identified in
  Limitation 3, so documented deployment environment variables take effect as described.
- Widen the seeded evaluation beyond 30 scenarios and, once the LLM path is credentialed and
  therefore potentially non-deterministic, report variance across repeated runs.
- Carry out the broader literature review scoped in `docs/RESEARCH_PROPOSAL.md` once credentialed
  results are available to discuss against it.

## References

[1] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis,
    W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-Augmented Generation for
    Knowledge-Intensive NLP Tasks," in *Advances in Neural Information Processing Systems*, vol.
    33, 2020, pp. 9459–9474.

[2] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, Ł. Kaiser, and
    I. Polosukhin, "Attention Is All You Need," in *Advances in Neural Information Processing
    Systems*, vol. 30, 2017, pp. 5998–6008. Available: https://arxiv.org/abs/1706.03762

[3] NVIDIA Corporation, "NVIDIA NIM Microservices for Accelerated AI Inference." Available:
    https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/

[4] NVIDIA Corporation, "Llama-3.1-8B-Instruct NIM," NGC Catalog. Available:
    https://catalog.ngc.nvidia.com/orgs/nim/teams/meta/containers/llama-3.1-8b-instruct

[5] S. Ramírez, "FastAPI." Available: https://fastapi.tiangolo.com/

[6] Pydantic Services Inc., "Pydantic Documentation." Available: https://docs.pydantic.dev/latest/

[7] M. Bayer, "SQLAlchemy" and "Alembic." Available: https://www.sqlalchemy.org/ and
    https://alembic.sqlalchemy.org/

[8] Prometheus Authors, "Prometheus Python Client." Available:
    https://github.com/prometheus/client_python

[9] L. Savaete, "slowapi: A rate limiter for Starlette and FastAPI." Available:
    https://github.com/laurentS/slowapi

[10] AegisOps AI project documentation: `docs/ROADMAP.md`, `docs/SECURITY_THREAT_MODEL.md`,
     `docs/RESEARCH_PROPOSAL.md`, `knowledge/human-approval.md`, `knowledge/safety-gates.md`,
     `knowledge/operational-limitations.md`, `knowledge/incident-triage.md`,
     `knowledge/escalation-protocol.md` (internal, this repository).
