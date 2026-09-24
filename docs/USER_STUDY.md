# User study protocol: old console vs new console

**Status: instrument built; no sessions run.** `reports/user_study.md` reports only what
sessions have produced (none yet).

## Question

When a reviewer must approve or reject response plans, does the new console
(`/plans/<id>`, M3) help them reach the right decision and name what is wrong, and how long do
they take? The comparison is the console as it was before M3 (tag `v0-ui`, served at
`/legacy`).

## Tasks

`aegisops/study/tasks.py` defines two parallel sets of six plans, A and B. Each plan is a
deterministic slice of the Lucknow exercise (five incidents, sixteen units), planned by CP-SAT.
Each set has three error-free plans, which should be approved. The other three each carry one
injected error and should be rejected:

| Error | What is changed | Verifier check that fails | Reason code that counts as caught |
| --- | --- | --- | --- |
| wrong ETA | the longest assignment claims 35% of its road time | `travel_time_matches` | `eta_incorrect` |
| phantom unit | the longest assignment names a unit that does not exist | `unit_exists` (with collateral) | `unit_unavailable_or_unknown` |
| SITREP mismatch | the first ETA in the SITREP is 7.0 min too high | `draft_numbers_match_state` | `sitrep_numbers_wrong` |

Every plan is verified as in production, so **both interfaces show the verifier's findings**
and neither lets a blocked plan be approved. The study measures what the reviewer does with
that information: the right action, the right reason, and the time taken. It does not measure
whether an unaided human spots an error.

## Design

- Within participants. Each participant does one set in each interface: six plans in the first
  interface, then six in the second.
- Counterbalanced by participant number (`session_plan`). Odd numbers start with the old
  console; the set order alternates every two participants (P01: old A → new B; P02: new B →
  old A; P03: old B → new A; P04: new A → old B).
- The participant signs in as an approver (Alice) who did not propose the plans; the plans are
  proposed by `study-proposer`.

## Measures (per plan; `aegisops/study/results.py`)

- `time_to_decision_s`: from opening the plan (the runner records `started_at` just before
  navigating) to the stored disposition. It includes page load, the same in both interfaces.
- `correct`: the recorded action equals the right one (approve an error-free plan, reject an
  injected one).
- `caught` (injected plans only): rejected **and** the reason code names the injected error.

## Running a session

1. Local stack in development mode: `sh scripts/build_legacy.sh`, then the API
   (`AEGISOPS_ENVIRONMENT=development`, the exercise seeded) and `npm run dev`.
2. The moderator opens `/study`, enters the participant code (P01, P02, …; never a name) and
   creates the session. This builds twelve plans (about 10 seconds).
3. Switch the identity to Alice. Hand over. The participant follows the runner: open a plan,
   decide, come back. The moderator does not help with decisions.
4. Afterwards, on `/study`: **Export CSV** saves `user_study.csv`. Commit it as
   `reports/raw/user_study.csv`.
5. `python scripts/analyze_study.py reports/raw/user_study.csv` writes
   `reports/user_study.md` and `reports/user_study.json`.

## Consent and data

Participants are volunteers. Collect verbal consent to record decisions and timings under a
code. Nothing identifies them in the data: the code, twelve decisions, reason codes and times.

## Limits to state with any result

- Small n: a handful of participants cannot support general claims. Report medians, counts and
  the per-participant differences, not significance tests.
- Both interfaces show the verifier, so ceiling effects on `correct` are likely. Time and
  `caught` (naming the error) are the informative measures.
- The participants, the tasks and the moderator all come from the project team's circle, not
  from emergency operations staff.
- The old console differs from the new one in look as well as function, and the study cannot
  separate the two.
