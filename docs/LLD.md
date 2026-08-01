# Low-Level Design (LLD)

## Domain contracts

`Scenario` has a stable ID, 1–100 `Incident` values, 0–500 `Resource` values, and a synthetic start minute. IDs are 1–64 characters matching `[A-Za-z0-9_-]+`; unknown fields are forbidden. Incident types are medical, fire, structural collapse, flood, and hazmat. Resource types are ambulance, fire unit, rescue team, and hazmat unit.

`DecisionResult` contains the selected engine name, a status (`requires_human_approval` or `blocked`), assignments, unmet requirements, safety findings, confidence, trace, optional evidence IDs, and approval fields. Approval validation enforces that approved/rejected results have an approver and timestamp; rejection also needs a reason. Current engines return the default pending fields.

## Allocation algorithm

For each incident ordered by `priority_score` descending and ID ascending:

1. Calculate `severity_weight × (1 + people_affected / 10) + min(reported_at_min, 120) / 120`.
2. For each requested resource type, select only available resources of that type.
3. Sort candidates by Euclidean grid distance divided by `eta_speed`, then by resource ID.
4. Allocate up to the required quantity and remove every allocated resource from the available map.
5. Record any remainder as an unmet requirement.

The engine blocks only for unmet critical requirements. It reports a high-priority finding for unmet high requirements; if no such findings exist, it records `HUMAN_APPROVAL_REQUIRED`. Coverage is `1 - unmet_quantity / (assignment_count + unmet_quantity)`, clamped to 0–1 and rounded to two decimals.

## Retrieval and provider behavior

`KnowledgeRetriever` tokenizes lower-cased alphanumeric words, hashes tokens into a normalized 256-dimensional vector, and uses an in-memory FAISS inner-product index. `RetrievalEngine` returns the top three document contents. The NIM engine sends scenario JSON plus those snippets to NVIDIA's chat-completions endpoint, requires JSON-only output, validates it as a `DecisionResult`, confirms matching scenario ID and human approval, and retries once after an HTTP or validation failure. Failure returns `NIM_DECISION_UNAVAILABLE` and `blocked`.

## HTTP details

The `ScenarioDecisionRequest` accepts `scenario`, `seed` (0–2,147,483,647), and a retained compatibility field `max_turns` (1–20); `max_turns` does not affect the implemented engines. `engine` is a query parameter with `rule_based` default or `llm_rag`. `/health`, `/scenario`, and `/simulate` are undocumented compatibility aliases.
