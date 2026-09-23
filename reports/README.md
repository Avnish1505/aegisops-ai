# Reports

| Report | What it measures | Status |
| --- | --- | --- |
| [fault_injection.md](fault_injection.md) | Verifier: 13 fault classes × 50 scenarios, false blocks on clean plans | Current; CI checks it is up to date (`scripts/fault_report.py --check`) |
| `eval_<date>.md` / `.json` | Reader, constraint translation, SITREP numeric match, end-to-end pass^5, latency, cost (`evals/run.py`) | Not generated yet: needs a live LLM key |
| `llm_vs_solver.md` / `.json` | LLM-direct allocation vs CP-SAT on 100 OSRM scenarios (`evals/llm_vs_solver.py`) | Not generated yet: needs a live LLM key |
| [phase_4_experiment_report.json](phase_4_experiment_report.json), [phase_3_visualization_summary.md](phase_3_visualization_summary.md) and `phase_3_*.png` | Earlier engine comparison | **Superseded.** Generated with no LLM key, so the LLM engine was blocked on 30/30 scenarios by its fallback path; it says nothing about a model |

Raw model outputs for each run go under `raw/`.
