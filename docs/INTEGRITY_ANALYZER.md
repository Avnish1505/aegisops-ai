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
