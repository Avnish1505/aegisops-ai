# The gate that trusted the model

*Draft. Every number below links to the committed report it comes from. Where there is no report
yet, the draft says so instead of guessing.*

AegisOps is a research platform that turns messy flood reports from a fictional Lucknow
exercise into response plans that a person approves. The first version of its "AI decision
engine" did what many do: it sent the scenario to a large language model, asked for a plan in
JSON, and checked the plan before showing it.

The check looked thorough. `validate_llm_recommendation` rejected units that did not exist,
units used twice, unavailable units, the wrong unit type and more units than an incident
needed. Anything it rejected became a critical finding, and critical findings blocked the plan.

It had two holes, and both were about trust.

## What the gate believed

**Travel times.** Each assignment carried a `travel_minutes` claim, and the gate copied it
through untouched. A plan could say an ambulance was four minutes away when the geometry said
twenty. The operator would see four.

**Citations.** The model was asked to cite the retrieved guidance behind each assignment. When
its citations pointed at nothing real, a "legacy fallback" attached *every* retrieved document to
the assignment instead. An uncited guess arrived looking like the best-sourced line in the plan.

Neither was malicious code. Each was a reasonable default: take the number you were given; don't
leave a field empty. But each let the model's output reach an operator unverified, which the
project exists to prevent. Commit
[`7c2e7e1`](https://github.com/Avnish1505/aegisops-ai/commit/7c2e7e1) recomputes every claimed
travel time (a gap over the tolerance blocks the plan) and drops citations of evidence that was
never retrieved.

That fixed two symptoms. The design question was why a gate should believe anything.

## A verifier that believes nothing

The replacement ([ADR 002](../adr/002-verifier-as-pure-functions.md)) is one pure function:
`verify(plan, scenario, reference_plan, travel_times, …)`. It takes data and returns named checks.

- It does no I/O, calls no model and reads no clock.
- It recomputes every ETA from the stored travel matrix.
- It checks units, availability, duplicates, capability, quantities, critical coverage and the
  operator's constraints.
- It compares the plan's objective with the CP-SAT optimum for the same inputs.
- It checks every number in the SITREP against the plan, and flags report text that reads like
  an instruction.

Every engine goes through it: the solver, the greedy baseline and the model. Because it is pure,
a stored decision can be verified again from the database alone, and a value edited behind the
system's back shows up as a differing check.

Two further decisions took the model out of the job it was worst suited for:

- **Allocation is now a solver's job**
  ([ADR 001](../adr/001-solver-not-llm-for-allocation.md)). OR-Tools CP-SAT minimises
  severity-weighted travel time over OSRM road times, with typed constraints, and says why when
  constraints cannot all hold.
- **The model reads and writes.** It turns a Hinglish field report into typed fields, each
  quoted from the report (a field whose quote is not in the report is dropped). It drafts SITREP
  prose, whose numbers are checked like everything else.

## Proving the checks catch what they claim

A verifier that has never failed a test proves nothing. The fault-injection suite
([report](../../reports/fault_injection.md)) takes clean solver plans and breaks them one way at a
time: a unit that does not exist, a unit used twice, a wrong ETA, a dropped critical incident, a
fabricated citation, a SITREP number that disagrees with the plan, an approval flag turned off,
an injected instruction.

- Every fault class was caught on every scenario:
  [13/13 classes, 650/650 injected faults](../../reports/fault_injection.md).
- The other direction matters as much, because a verifier that blocks everything is useless:
  clean plans falsely blocked, [0/50](../../reports/fault_injection.md).

The report is regenerated in CI and the build fails if the committed copy is stale.

## LLM-direct allocation vs the solver

This is the section the project was built to fill, and it is empty.

The harness is done ([`evals/llm_vs_solver.py`](../../evals/llm_vs_solver.py)). It runs Lucknow
scenarios on recorded OSRM road times and puts both arms through the same verifier. It reports
feasibility, the optimality gap and verifier findings per plan, with bootstrap intervals. Its
scoring is tested against an oracle model that returns the solver's own plan.

What it has not had is a live model: no API key was available while it was built. So there is no
result, and none is claimed. When it runs, the output lands in `reports/llm_vs_solver.md`, and
this section will quote it, including if the model does better than expected.

## What did not work

- **A report that measured nothing.** An earlier comparison showed the LLM engine blocked on
  every scenario ([30 of 30](../../reports/phase_4_experiment_report.json)). It was produced
  with no model key, so it measured the fallback path, not a model. It is now marked superseded
  ([reports/README.md](../../reports/README.md)).
- **Evaluation data that repeated itself.** The first synthetic report set contained the same
  text more than once. Duplicates make bootstrap intervals look tighter than the data supports.
  The generator now redraws them; it was caught before any evaluation ran.
- **Bugs the oracle found.** Testing the eval harness against a model that answers from the gold
  labels turned up three bugs before any real model was involved:
  - a distance of zero treated as missing;
  - one-digit quotes rejected;
  - short Devanagari place names left out of the gazetteer.
- **Checks limited to what data can decide.** SITREP numbers must follow a fixed phrasing, so a
  correct number phrased differently fails as unattributed. Instruction detection is
  pattern-based and will miss a paraphrase. Road times are free-flow: OSRM knows nothing about a
  flooded street.
- **People, not yet.** A timed user study comparing the old and new console is built
  ([protocol](../USER_STUDY.md)); no sessions have been run.

## What carries over

Most "AI safety" in small systems is a check that assumes the model got the easy parts right.
Treat every model output as a claim. Recompute what can be recomputed, from inputs you stored.
Give the job to a tool that is correct by construction where one exists. Then break your own
checks on purpose and publish how often they catch it, and how often they cry wolf.
