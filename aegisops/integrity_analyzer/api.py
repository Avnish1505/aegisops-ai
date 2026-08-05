"""Public entry points for the Implementation Integrity Analyzer.

Bundle 1 exposes source loading and AST parsing. Bundle 2 adds scaffolded-function
detection. Bundle 3 adds structured report generation (Python dict and JSON) over
those findings. Callers should depend on this module rather than the loader,
parser, detector, or report internals directly.
"""

from __future__ import annotations

from pathlib import Path

from aegisops.integrity_analyzer.ast_parser import parse_source
from aegisops.integrity_analyzer.models import ParsedModule, ScaffoldFinding, SourceFile
from aegisops.integrity_analyzer.report import build_report, json_report
from aegisops.integrity_analyzer.scaffold_detector import detect_scaffolded_functions
from aegisops.integrity_analyzer.source_loader import load_source_directory, load_source_file

__all__ = [
    "ParsedModule",
    "ScaffoldFinding",
    "SourceFile",
    "analyze_directory",
    "analyze_file",
    "build_report",
    "find_scaffolded_functions",
    "find_scaffolded_functions_in_directory",
    "json_report",
]


def analyze_file(path: Path) -> ParsedModule:
    """Load and parse a single Python source file."""
    return parse_source(load_source_file(path))


def analyze_directory(path: Path, *, recursive: bool = True) -> list[ParsedModule]:
    """Load and parse every Python source file under ``path``."""
    return [parse_source(source) for source in load_source_directory(path, recursive=recursive)]


def find_scaffolded_functions(path: Path) -> list[ScaffoldFinding]:
    """Report scaffolded functions (pass/.../docstring-only/NotImplementedError) in one file."""
    return detect_scaffolded_functions(analyze_file(path))


def find_scaffolded_functions_in_directory(
    path: Path, *, recursive: bool = True
) -> list[ScaffoldFinding]:
    """Report scaffolded functions across every Python source file under ``path``."""
    return [
        finding
        for parsed in analyze_directory(path, recursive=recursive)
        for finding in detect_scaffolded_functions(parsed)
    ]
