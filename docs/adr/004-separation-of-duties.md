# 004. The proposer can never approve; approving needs the approver role

Status: Accepted (M1, 2026-09-23; reason codes added in M3)

## Context

A human in the loop is only a control if the human is independent of the proposal. One person
proposing and approving their own plan is one decision, not two.

## Decision

- Each decision stores the token subject that proposed it.
- Approving needs the `approver` role, and the proposer's subject gets 409 "proposer cannot
  approve". A blocked plan returns 409 for everyone.
- Both approve and reject need a reason code that fits the action (`other` needs text), stored
  on the approval and in the hashed event. Approval also needs an explicit confirmation step in
  the console.
- The console gives Approve and Reject the same size and style, and says why Approve is
  unavailable.

## Consequences

- A demo or test needs at least two identities (operator and approver, or two approvers).
- The rule is enforced by the server; the console only explains it.
- Reason codes make decisions comparable; the user study relies on them to count caught errors.

## Evidence

- `tests/test_auth.py::test_proposer_cannot_approve_their_own_decision`
- `tests/test_plan_review_api.py` (reason codes)
- `e2e/flow.spec.ts` (approval by a second user; the proposer sees the refusal)
