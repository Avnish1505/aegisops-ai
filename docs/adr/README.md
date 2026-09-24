# Architecture decision records

Each record gives the context, the decision, what it costs, and the file or test that shows it
holds. Status is one of Proposed, Accepted, Superseded.

| No. | Decision | Status |
| --- | --- | --- |
| [001](001-solver-not-llm-for-allocation.md) | A CP-SAT solver allocates units; the LLM does not | Accepted |
| [002](002-verifier-as-pure-functions.md) | The verifier is pure functions over data | Accepted |
| [003](003-hash-chained-audit-log.md) | Every step is an append-only, hash-chained event | Accepted |
| [004](004-separation-of-duties.md) | The proposer can never approve; approving needs the approver role | Accepted |
