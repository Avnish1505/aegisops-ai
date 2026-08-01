# User Manual

## What this application does

AegisOps AI is a synthetic crisis decision-support demonstration. It draws generated incidents and resources on a coordinate grid, then shows an advisory allocation. It never dispatches resources. Do not enter real incidents, people, locations, or operational data.

## Start the application

Start the API on port 8000 and the Vite frontend as described in the Developer Guide. Open the frontend address shown by Vite. If it reports that it cannot reach the API, confirm the backend is running and that `VITE_API_BASE_URL` points to it.

## Generate and inspect a scenario

1. Enter a non-negative whole number in **Scenario seed** (use `42` for a repeatable example), or leave it blank for a newly generated scenario.
2. Select **Generate scenario**. The grid uses synthetic 0–100 coordinates, not a map.
3. Select an incident or resource marker, or use Enter/Space when focused, to see its details. Colors/shapes indicate incident severity; cyan squares are resources.

## Request and review an advisory

1. Select **Get recommendation**.
2. Review the top status. **Allocation blocked — escalation required** means a critical capability is unmet. It does not mean the system has taken action.
3. Inspect proposed routes, unmet requirements, safety findings, coverage-based advisory confidence, and the decision trace. Hover, focus, or select a route row to highlight it on the grid.
4. Treat every output as advisory. Confidence is allocation coverage, not an outcome forecast.

The **Approve recommendation** and **Reject** controls only update the current browser view. They do not submit, record, authorize, or dispatch anything. Refreshing or generating another scenario clears this local indication.

## If something fails

- A validation message means the seed or request data is invalid; use a whole non-negative seed.
- An API connection message means the frontend cannot reach the backend.
- A blocked result with `NIM_DECISION_UNAVAILABLE` means the optional provider adapter could not safely produce a validated result; escalate to a human reviewer rather than retrying as an operational action.
