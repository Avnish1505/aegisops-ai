# Implementation Integrity Analyzer

`aegisops/integrity_analyzer/` is a self-contained static-analysis toolkit that finds
*scaffolded* Python functions — functions whose body is only a placeholder (`pass`, `...`, a lone
docstring, or `raise NotImplementedError()`) rather than a real implementation — and reports them
as a Python dict or JSON. It has no dependency on `aegisops.domain`, `aegisops.application`,
`aegisops.infrastructure`, or `aegisops.api`, and it exposes no HTTP route or CLI entry point; it
is used as a library, from Python.

## Architecture

The package is a short, one-directional pipeline. Each stage is its own module and depends only on
the stage(s) before it:

```text
source_loader.py  ->  ast_parser.py  ->  scaffold_detector.py  ->  report.py
 (disk -> text)      (text -> AST)      (AST -> ScaffoldFinding)   (findings -> dict/JSON)
```

- `models.py` — shared, immutable value objects used across every stage: `SourceFile` (a path and
  its text), `ParsedModule` (a `SourceFile` plus its parsed `ast.Module`), `ScaffoldClassification`
  (a `StrEnum` of the four recognised markers), and `ScaffoldFinding` (`function`, `line`,
  `classification`, `file`).
- `source_loader.py` — reads `.py` files from disk as UTF-8 text. Rejects missing paths,
  non-`.py` files, files over 2,000,000 bytes, and non-UTF-8 content. Directory loading skips
  tooling/build noise (`__pycache__`, `.git`, `.venv`, `venv`, `node_modules`, `.pytest_cache`,
  `.ruff_cache`, `.mypy_cache`, `dist`) and can be recursive or not.
- `ast_parser.py` — turns loaded source text into an `ast.Module` via `ast.parse`; source is never
  executed. Invalid syntax becomes a `ValueError`.
- `scaffold_detector.py` — walks every `FunctionDef`/`AsyncFunctionDef` in a parsed module,
  including nested functions and methods, and classifies each one whose body is *exactly one
  statement* matching a scaffold marker. Multi-statement bodies (e.g. a docstring followed by
  `pass`) are not flagged — only literal single-statement bodies are.
- `report.py` — converts a list of `ScaffoldFinding` into a report: `build_report` produces a
  plain Python dict (`Path` and enum values are converted to strings), and `json_report` renders
  a dict produced by `build_report` as a JSON string.
- `api.py` — the public entry point. Callers should import from here rather than from the
  internal stage modules.

Errors are raised as `ValueError` throughout, consistent with the rest of `aegisops`; there is no
package-specific exception hierarchy.

## Public API

Everything below is importable from `aegisops.integrity_analyzer.api` (also re-exported from the
same-named symbols in `models.py`).

| Symbol | Signature | Returns |
| --- | --- | --- |
| `analyze_file` | `analyze_file(path: Path) -> ParsedModule` | The loaded and parsed source of one file. |
| `analyze_directory` | `analyze_directory(path: Path, *, recursive: bool = True) -> list[ParsedModule]` | Loaded and parsed source for every `.py` file under `path`. |
| `find_scaffolded_functions` | `find_scaffolded_functions(path: Path) -> list[ScaffoldFinding]` | Scaffold findings for one file. |
| `find_scaffolded_functions_in_directory` | `find_scaffolded_functions_in_directory(path: Path, *, recursive: bool = True) -> list[ScaffoldFinding]` | Scaffold findings across every `.py` file under `path`. |
| `build_report` | `build_report(findings: list[ScaffoldFinding]) -> dict[str, object]` | `{"total_findings": int, "findings": [...]}`, each finding as `function`/`line`/`classification`/`file` strings and ints. |
| `json_report` | `json_report(report: dict[str, object], *, indent: int \| None = 2) -> str` | The report dict rendered as a JSON string. |

Value types (`aegisops.integrity_analyzer.models`):

| Type | Fields |
| --- | --- |
| `SourceFile` | `path: Path`, `content: str` |
| `ParsedModule` | `source: SourceFile`, `tree: ast.Module` |
| `ScaffoldClassification` | `StrEnum`: `PASS`, `ELLIPSIS`, `DOCSTRING_ONLY`, `NOT_IMPLEMENTED` |
| `ScaffoldFinding` | `function: str`, `line: int`, `classification: ScaffoldClassification`, `file: Path` |

All functions raise `ValueError` for a missing path, a non-`.py` file, an oversized file, invalid
UTF-8, invalid syntax, or a directory with no `.py` files.

## Usage

```python
from pathlib import Path

from aegisops.integrity_analyzer.api import (
    build_report,
    find_scaffolded_functions_in_directory,
    json_report,
)

findings = find_scaffolded_functions_in_directory(Path("aegisops"))
for finding in findings:
    print(f"{finding.file}:{finding.line} {finding.function} ({finding.classification})")

report = build_report(findings)
print(report["total_findings"])

print(json_report(report))
```

For a single file:

```python
from pathlib import Path

from aegisops.integrity_analyzer.api import find_scaffolded_functions

findings = find_scaffolded_functions(Path("aegisops/domain/models.py"))
```

To inspect the parsed AST directly, without running scaffold detection:

```python
from pathlib import Path

from aegisops.integrity_analyzer.api import analyze_file

parsed = analyze_file(Path("aegisops/domain/models.py"))
print(parsed.tree.body)
```

## Benchmark: analyzer vs naive baseline

The Implementation Integrity Analyzer is evaluated against a labeled corpus of
15 scenarios: 5 true-positive (one seeded integrity failure each), 5 clean
(correctly wired, fully implemented code that must not be flagged), and 5 hard
cases chosen to probe the limits of intra-file static analysis.

The comparison point is a naive grep baseline that checks whether a
safety-critical function name appears anywhere in the file.

| Metric          | Naive Baseline | Analyzer |
| --------------- | -------------- | -------- |
| True positives  | 0              | 5        |
| False positives | 0              | 4        |
| False negatives | 6              | 1        |
| True negatives  | 9              | 5        |
| Precision       | n/a            | 0.556    |
| Recall          | 0.000          | 0.833    |
| MCC             | 0.000          | 0.389    |

MCC is the headline metric: the corpus is small and class-imbalanced, so
accuracy would be misleading.

### Interpretation

The baseline detects nothing (recall 0.000, undefined precision). This is not a
strawman — it is the natural failure mode of string matching. A safety-critical
function's name always appears in its own `def` line, so a text search cannot
distinguish a gate that is *defined* from a gate that is actually *called*.
Separating definition from invocation requires an AST-level call map, which is
what the analyzer builds.

The analyzer resolves all 10 easy scenarios correctly: 5 true positives and 5
clean files with no false alarms. Its errors are concentrated entirely in the 5
hard cases — 4 false positives and 1 false negative — and each corresponds to a
limitation already documented in the module docstrings of `wiring_checker.py`
and `scaffold_detector.py`: no alias resolution, no transitive call resolution
through helpers, no `@abstractmethod` awareness, and no control-flow or ordering
analysis (call-set presence only, not "runs before"). Nothing was excluded,
retuned, or reweighted to improve these numbers.

The error profile skews toward false positives rather than false negatives. For
a safety-critical review tool this is the appropriate bias: a false alarm costs
a developer one review, while a missed integrity violation ships an unguarded
operation.

### Reproducing

```bash
python -m aegisops.integrity_analyzer.benchmark.run_benchmark
```

This prints the table above and rewrites `aegisops/integrity_analyzer/benchmark/results.json`;
the committed file holds the same numbers.
