# Two-minute demo

Public sandbox: **URL added after deployment** (API on Railway, console on Vercel; see
[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#public-demo-railway-api--osrm-vercel-console)).
Everything you change is wiped at the next hourly reset. The exercise and its reports are
fictional; the places, roads and facilities are OpenStreetMap data for Lucknow.

Open it in a desktop browser at 1440×900 or larger. Press `?` at any time for the shortcuts.

## 0:00 Sign in as the operator (10 s)

Choose **Demo operator**. The status bar shows `EXERCISE`, the SACHET / USGS / GDACS feed state,
`LLM off` (the demo calls no model), pending approvals, the live-stream state, when the sandbox
resets, and the time in IST.

## 0:10 Operations board (25 s)

- The left queue is ordered by severity (◆ critical, ▲ high, ● medium, ○ low: shape, colour
  and word), then by shortfall, then oldest first. Each row gives the place first, then the ID,
  its age, and what the current plan does for it.
- Press `J` twice. The inspector shows the source report, the fields, and the nearest capable
  units with road ETAs from OSRM.
- The map colours only what is abnormal: red and amber incidents, amber alert areas. Roads,
  units and routes stay grey.

## 0:35 Triage a report (35 s)

- Go to **Triage** (or `⌘K`, then "triage"). Pick the **Kaiserbagh bus stand** report.
- If the demo has recorded readings, each field's quote is marked in the text and any dropped
  field says why. Otherwise the report is "Not read" and you enter the fields yourself.
- Set **Flood**, search the place "qaisar", enter **30** people, add a need of **2 boats**, and
  tick **trapped**. The severity the rules give is **High (R4)**; you edit facts, never severity.
- **Confirm and add to exercise**, then **Plan the exercise now**.

## 1:10 Review the plan (30 s)

- Every ETA in the assignments comes from the stored OSRM matrix. A unit that failed a check
  shows the check on its row.
- The verifier checklist lists failures first. The SITREP marks any number that does not match
  the plan.
- **Approve** is disabled with *Approving needs the approver role*. Approve and Reject have the
  same size and style.

## 1:40 Approve as someone else (20 s)

- Open the identity menu (or `⌘K`, then "act as") and switch to **Demo approver**.
- Press `A`, choose a reason code, **Continue**, then **Confirm approval**.
- Open **Audit trail**. It shows the proposal, the verification and your decision, each hashed
  onto the previous event. **Re-verify stored inputs** recomputes the verdict from the stored
  record alone.

To see separation of duties refuse an approval: as **Demo approver**, re-plan the exercise from
the board. The new plan says *Proposer cannot approve: you proposed this plan*.

## What the demo does not show

- No live model: LLM steps show recorded readings or "not read", and no LLM accuracy is claimed
  (see **Evals**).
- Travel times are OSRM free-flow car times: no traffic, closures or flooding.
- A sandbox with two fixed identities is not an authentication system; no OIDC sign-in is built.
