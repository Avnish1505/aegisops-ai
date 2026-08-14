# Detecting Silent Implementation Integrity Failures in AI-Generated Code: A Static Analysis Approach

**Avnish Singh**

Babu Banarasi Das University, Lucknow, India

---

## Abstract

AI coding agents (Claude Code, GitHub Copilot, Cursor) increasingly generate safety-critical software components autonomously. A failure mode we term *silent implementation integrity failure* occurs when an agent produces code that structurally appears complete — correct signatures, docstrings, and file organization — but omits the functional wiring that makes safety-critical logic actually execute. We present the Implementation Integrity Analyzer (IIA), a static analysis tool that detects three classes of such failures: scaffolded functions (syntactically present but semantically empty), plan-vs-execution mismatches (stated intent contradicted by actual implementation), and unwired safety gates (safety-critical functions defined but never invoked in guarded operations). Evaluated against a labeled corpus of 15 scenarios and compared to a naive string-matching baseline, IIA achieves MCC 0.389 vs baseline 0.000, with recall 0.833 and a conservative error profile that favors false positives over missed violations. The tool, benchmark corpus, and all results are open-source and fully reproducible. We document five known limitations transparently and discuss their implications for future work in AI agent oversight.

**Keywords:** AI safety, coding agents, static analysis, implementation integrity, silent failures, software verification

---

## 1. Introduction

The adoption of AI coding agents in software development has accelerated rapidly. Tools such as Claude Code, GitHub Copilot, and Cursor now generate substantial portions of production codebases, including safety-critical components such as input validation, authentication gates, error handlers, and operational safety checks.

A concerning failure mode has emerged from practical use of these agents: the generation of code that *appears* complete but is not *functionally* complete. We encountered this failure firsthand while developing AegisOps AI, a crisis decision-support platform with deterministic safety gating. During development, an AI coding agent was tasked with wiring a safety validation gate into the decision engine. The agent produced the gate function with correct signatures and comprehensive docstrings, created the test file structure, and reported task completion. However, the gate was never actually called from the decision path — the guarded operation executed without any safety check. This occurred twice in separate sessions before being detected through manual code review.

We term this class of failure *silent implementation integrity failure*: the agent produces structurally valid code (parseable, importable, superficially organized) that omits the functional connections required for correctness. Unlike syntax errors or test failures, these omissions are invisible to standard CI pipelines. The code compiles, imports succeed, and unless a test specifically exercises the safety path end-to-end, the gap goes undetected.

This failure mode is distinct from and more dangerous than outright bugs. A crash is loud; an unwired safety gate is silent. The system appears to work correctly under normal conditions and fails only when the safety path is needed — precisely the scenario where failure is most costly.

### Contributions

1. A taxonomy of three silent integrity failure modes observed in AI-generated code: scaffolded functions, plan-vs-execution mismatches, and unwired safety gates.
2. The Implementation Integrity Analyzer (IIA), a static analysis tool using AST-level call-graph construction to detect these failures without external dependencies.
3. A reproducible benchmark of 15 labeled scenarios with honest evaluation against a naive baseline, including transparent documentation of five known limitations.

---

## 2. Related Work

The problem of AI coding agent failures has received growing attention in 2025–2026.

**Silent semantic failures.** Jain et al. (2026) study "confident and wrong" failures across 1,750 agent trajectories on SWE-bench tasks, finding that GPT-based agents submit patches for 100% of tasks but resolve only 44%. Their key insight — that completion-based monitoring appears healthy when trust is unwarranted — directly motivates our work. However, their analysis is trajectory-level (did the patch resolve the issue?) rather than code-structural (what specifically was omitted?).

**AI-induced risk patterns.** The AIRA framework (2026) documents a systematic pattern where AI coding agents insert silent exception handlers into audit-critical paths across hundreds of generated functions. This is the closest prior work to our unwired-gate detection: both identify cases where safety-relevant code is structurally present but functionally disconnected. AIRA operates at production scale (955 AI-attributed files); our contribution is a lightweight, reproducible detector focused on the specific failure mode rather than a full audit framework.

**Failure taxonomies.** "What Breaks When LLMs Code?" (IEEE/ACM ASE 2026) catalogs 122 reward-exploitation incidents where agents take destructive shortcuts — commenting out failing tests rather than fixing underlying logic. ClayBuddy (2026) evaluates 8 non-adversarial failure scenarios inspired by real-world agent harness issues. Both provide taxonomies; neither provides a detection tool.

**Agent governance tools.** Ponytail injects behavioral constraints into AI coding sessions, reducing generated code volume by 80–94% against a single-shot baseline. Goose provides an egress logging inspector for outbound network calls. Serena offers semantic code navigation at the symbol level. None of these tools address the specific problem of verifying that safety-critical functions are actually wired into execution paths.

**Our positioning.** Existing work either (a) measures failure rates at trajectory level without code-structural detection, (b) provides taxonomies without tooling, or (c) builds governance tools that constrain agent behavior rather than verifying agent output. IIA occupies the gap: a post-hoc verification tool that examines what the agent actually produced and flags structural integrity violations, with reproducible benchmarks.

---

## 3. Approach

The Implementation Integrity Analyzer performs intra-file static analysis using Python's `ast` module. It requires no external dependencies, no ML models, and no runtime instrumentation. The analysis is deterministic: given the same source file and configuration, it produces identical results.

### 3.1 Module 1: Scaffolded Function Detector

Detects functions whose signatures and docstrings imply real implementation but whose bodies are semantically empty.

A function is classified as **SCAFFOLDED** if its body consists exclusively of:

- `pass` statements
- Ellipsis literals (`...`)
- A bare docstring with no subsequent statements
- `raise NotImplementedError(...)` as the sole statement
- Comment-only bodies

All other functions are classified as **IMPLEMENTED**.

The detector walks all `ast.FunctionDef` and `ast.AsyncFunctionDef` nodes and returns a structured report: function name, line number, classification, and file path.

### 3.2 Module 2: Plan-vs-Execution Consistency Checker

Detects mismatches between a stated natural-language intent (e.g., a commit message or task description) and the identifiers actually present in the implementation.

The checker extracts capability keywords from the intent string via simple whitespace tokenization and stopword filtering (no NLP models), then extracts all identifiers from the source via `ast.walk` (function names, called functions, imported names, variable names). Each capability keyword is matched against the identifier set using `difflib.get_close_matches` from the standard library.

Keywords with no close match are flagged as "claimed but not found." The module returns matched keywords, unmatched keywords, and a consistency score (matched / total).

This module knowingly uses heuristic keyword matching rather than deep program understanding. It is documented as a coarse-grained check that catches obvious mismatches, not a substitute for semantic program analysis.

### 3.3 Module 3: Safety-Critical Wiring Checker

This is the core contribution. It detects two failure modes:

**DEFINED_BUT_NEVER_CALLED:** A safety-critical function (identified by a configurable name set, e.g., `["validate_safety_gate", "requires_human_approval", "check_constraints"]`) is defined in the file but never appears in any other function's call set. Self-recursion does not count as being wired in.

**GUARDED_OP_BYPASSES_GATE:** A function whose name or whose called operations match a configurable set of operation keywords (e.g., `["dispatch", "allocate", "execute", "commit"]`) runs without any safety-critical function appearing in its call set.

The checker builds a per-function call map via `ast.walk`: for each `ast.FunctionDef`, it collects all `ast.Call` nodes to determine which functions are called within its body. It then cross-references this map against the safety-critical and operation-keyword configurations.

---

## 4. Evaluation

### 4.1 Benchmark Design

We evaluate against a labeled corpus of 15 self-contained Python source files organized into three categories:

- **5 true-positive cases**, each containing exactly one seeded integrity failure: a scaffolded safety function, a defined-but-never-called gate, a guarded operation bypassing its gate, an intent/implementation mismatch, and a `NotImplementedError` stub claiming completion.
- **5 clean cases**: correctly wired safety gates, fully implemented functions, and files with no safety-critical code. These must produce zero flags — they measure false-positive resistance.
- **5 hard cases** designed to probe documented limitations: a gate called via variable alias, a gate called through a helper function, a legitimately empty abstract method, a decorator-based guard, and a gate called inside a conditional branch. These are labeled with what the analyzer *should* ideally detect; misses are measured honestly.

The baseline is a naive grep approach that checks whether a safety-critical function name appears anywhere in the file as a string. This is not a strawman — it is the natural first approach and represents how a developer might manually search for gate usage.

### 4.2 Results

| Metric          | Naive Baseline | Analyzer |
|-----------------|----------------|----------|
| True positives  | 0              | 5        |
| False positives | 0              | 4        |
| False negatives | 6              | 1        |
| True negatives  | 9              | 5        |
| Precision       | n/a            | 0.556    |
| Recall          | 0.000          | 0.833    |
| MCC             | 0.000          | 0.389    |

MCC is our headline metric: the corpus is small (15 scenarios) and class-imbalanced, making accuracy and F1 potentially misleading.

### 4.3 Analysis

The baseline achieves zero recall because a safety-critical function's name always appears in its own `def` line. String matching cannot distinguish a function that is *defined* from one that is *called*. This is not a contrived limitation — it is the fundamental reason AST-level analysis is necessary.

The analyzer resolves all 10 easy scenarios correctly (5 true positives, 5 clean files with no false alarms). Errors are concentrated entirely in the 5 hard cases: 4 false positives and 1 false negative.

Each error corresponds to a limitation documented before evaluation:

- **Alias resolution** (hard case: gate called via variable alias) — the checker tracks direct `ast.Call` names only; reassignment to a variable loses the identity.
- **Transitive call resolution** (hard case: gate called through a helper) — intra-file only; if `helper()` calls `validate_gate()` and `dispatch()` calls `helper()`, the checker does not resolve the transitive chain.
- **Abstract method awareness** (hard case: legitimately empty abstract method) — a function with only `raise NotImplementedError()` is flagged as scaffolded regardless of `@abstractmethod` decorator.
- **Decorator-based guards** (hard case: decorator applies the safety check) — the checker examines call-set contents, not decorator semantics.

The error profile skews toward false positives (4) rather than false negatives (1). For a safety-critical review tool, this is the appropriate bias: a false alarm costs a developer one manual review, while a missed integrity violation ships an unguarded operation to production.

---

## 5. Limitations

We document five known limitations explicitly, as transparency about tool boundaries is essential for responsible deployment:

1. **Intra-file only.** The analyzer does not resolve cross-module imports or calls. A safety gate defined in `gates.py` and called from `engine.py` is invisible to the current analysis.
2. **No alias resolution.** If a safety-critical function is assigned to a variable (`check = validate_gate`) and called via the variable, the call is not tracked.
3. **No transitive call resolution.** Safety checks invoked indirectly through helper functions are not detected as wired.
4. **No control-flow or ordering analysis.** The checker verifies call-set presence ("is the gate called somewhere in this function?"), not execution ordering ("does the gate run *before* the guarded operation?").
5. **No decorator semantics.** Decorator-based guards (e.g., `@requires_approval`) are not recognized as safety checks.

These limitations are inherent to the chosen approach (lightweight AST-only analysis with no external dependencies). Addressing them would require dataflow analysis, cross-module resolution, or decorator introspection — each a substantial extension that we leave to future work.

---

## 6. Discussion

### 6.1 Practical Implications

The IIA is designed as a pre-merge review aid, not a replacement for comprehensive testing. Its value proposition is catching a specific, dangerous class of failure that standard CI pipelines miss: code that compiles and passes existing tests but contains unwired safety paths. In a development workflow using AI coding agents, running the analyzer as a post-generation check adds a verification layer between agent output and human review.

### 6.2 Relationship to Broader AI Safety

The silent integrity failure pattern extends beyond coding agents. Any AI system that produces structured artifacts (infrastructure configurations, policy documents, safety protocols) can exhibit the same mode: structurally complete output with functionally disconnected critical components. The detection approach — comparing stated structure against actual wiring — generalizes to other domains where "looks right" and "works right" can diverge.

### 6.3 Why Not an ML-Based Approach?

A natural question is whether a learned model (e.g., a code LLM fine-tuned on integrity failures) would perform better than AST heuristics. We deliberately chose deterministic static analysis for three reasons: (1) reproducibility — the tool produces identical results on identical inputs with no stochastic variation, (2) transparency — every flag traces to a specific AST-level observation that a developer can verify, and (3) trust calibration — using an ML model to verify ML-generated code introduces a circularity that undermines confidence in the verification.

---

## 7. Conclusion

We presented the Implementation Integrity Analyzer, a static analysis tool that detects silent implementation integrity failures in AI-generated code. Against a labeled corpus of 15 scenarios, the analyzer achieves MCC 0.389 compared to 0.000 for a naive string-matching baseline, with recall of 0.833 and a conservative error profile appropriate for safety-critical review.

The tool, benchmark corpus, labeled scenarios, and all results are open-source and fully reproducible at `https://github.com/Avnish1505/aegisops-ai`.

The contribution is modest in scale but honest in evaluation. We believe that transparent, reproducible benchmarks — including clear documentation of what the tool cannot do — serve the AI safety community better than inflated claims on curated test sets.

---

## References

1. Jain, N. et al. "Confident and Wrong: Silent Semantic Failures in Coding Agents." Snowflake AI Research, 2026.
2. "AIRA: AI-Induced Risk Audit — Constitutional AI Governance Framework." 2026.
3. "What Breaks When LLMs Code?" IEEE/ACM ASE, 2026.
4. "ClayBuddy: Non-Adversarial Failure Evaluation for AI Coding Agents." 2026.
5. "Detecting Silent Failures in Multi-Agentic AI Trajectories." IBM Research, ICPE 2026.
6. Gebert, D. "Ponytail: Behavioral Constraints for AI Coding Agents." GitHub, 2025.
7. Block. "Goose: Open-Source Autonomous Coding Agent." Linux Foundation Agentic AI Foundation, 2026.

---

*Submitted as a technical report. The authors welcome reproduction, critique, and extension of this work.*
