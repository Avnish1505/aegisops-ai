# Eval datasets v1

| File | Rows | What |
| --- | --- | --- |
| `reports_v1.jsonl` | 300 | 200 synthetic Lucknow field reports + 100 HumAID tweets (IDs and mapped labels only) |
| `notes_v1.jsonl` | 50 | Operator constraint notes with gold constraints (30 reserve, 10 exclude, 10 priority) |
| `e2e_v1.jsonl` | 50 | End-to-end scenarios: three synthetic reports each, planned against the Lucknow units |
| `lucknow_exercise_v1.json` | 1 | The Lucknow exercise scenario (20 incidents, 45 units at OSM facilities) |
| `spotcheck_v1.md` | 30 | Random sample of synthetic reports for human label review |

Built by `python -m evals.build_dataset` (deterministic, seed 20260923). HumAID text is filled in
by `python -m evals.fetch_humaid` into `evals/data/.cache/` (gitignored); the eval report records
the SHA-256 of the assembled file.

## Synthetic Lucknow reports (200)

- **How they were made.** Rendered from 47 templates written for this project by an AI assistant
  (Claude), in English (75), Hinglish, i.e. Hindi in Latin script (78), and Hindi in Devanagari
  (47). Types: flood 78, medical 54, structural collapse 34, fire 29, non-incident 5. Slots are
  filled with real Lucknow places and landmarks from the OSM gazetteer
  (`aegisops/intake/lucknow_gazetteer.json`), people counts written as digits, number words,
  Devanagari digits or approximations ("lagbhag 25", "करीब ४०"), and requested unit quantities.
  All 200 texts are distinct: the generator redraws any duplicate, because repeated items would
  make the bootstrap intervals narrower than the data supports.
- **Where the labels come from.** Every gold label is the slot value the template was filled
  with, so labels are correct by construction; nobody annotated the text after the fact. Gold
  severity is the deterministic rule set (`aegisops/intake/severity.py`) applied to the gold
  fields, so severity accuracy measures how extraction errors propagate, not whether the rules
  are right.
- **Slices.** `en`, `hi`, `hinglish`; `no_location` (15 reports with no place); `injection`
  (6 reports containing an instruction aimed at the model); 5 non-incident messages.
- **Limits.** Templated text is far less varied than real reports: the same phrasing recurs,
  spelling is clean, and there is one incident per report. Scores on this set are an upper bound
  on real-world performance.
- **Human review.** `spotcheck_v1.md` holds a 30-report random sample for the maintainer to check.

## HumAID tweets (100)

HumAID (Alam et al., "HumAID: Human-Annotated Disaster Incidents Data from Twitter", ICWSM 2021,
https://crisisnlp.qcri.org/humaid_dataset). 40 from `srilanka_floods_2017`, 30 from
`maryland_floods_2018`, 30 from `hurricane_harvey_2017` test splits, stratified by class. Only
tweet IDs and our mapped labels are stored here; tweet text is downloaded from the HumAID release
at eval time.

Label mapping (only these fields are scored for HumAID rows):

| HumAID class | incident_type | signals |
| --- | --- | --- |
| requests_or_urgent_needs, infrastructure_and_utility_damage, displaced_people_and_evacuations, caution_and_advice | flood | - |
| injured_or_dead_people | flood | injured |
| missing_or_found_people | flood | missing_person |
| rescue_volunteering_or_donation_effort, sympathy_and_support, other_relevant_information, not_humanitarian | none (not an incident report) | - |

This mapping is ours, not HumAID's; it treats the events' flooding as the incident type and only
calls a tweet an incident report when its humanitarian class describes harm, need or danger.

## Operator notes (50) and end-to-end scenarios (50)

Notes are templated the same way (reserve notes in English, Hinglish and Hindi; exclude and
priority notes naming unit and incident IDs from the Lucknow exercise). A reserve translation is
correct when kind, unit type and count match and the zone is centred within 1 km of the named
place. End-to-end scenarios draw three located, non-injection synthetic reports each.

## Licences

Place names and coordinates: (c) OpenStreetMap contributors, ODbL 1.0. HumAID: cite the paper
above; tweet text is not redistributed from this repository.
