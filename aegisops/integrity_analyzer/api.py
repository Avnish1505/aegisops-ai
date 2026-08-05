"""Public entry points for the Implementation Integrity Analyzer.

Bundle 1 exposes source loading and AST parsing only. Integrity-detection
logic is added in a later bundle behind this same surface, so callers should
depend on this module rather than the loader/parser internals directly.
"""

from __future__ import annotations

from pathlib import Path

from aegisops.integrity_analyzer.ast_parser import parse_source
from aegisops.integrity_analyzer.models import ParsedModule, SourceFile
from aegisops.integrity_analyzer.source_loader import load_source_directory, load_source_file

__all__ = [
    "ParsedModule",
    "SourceFile",
    "analyze_directory",
    "analyze_file",
]


def analyze_file(path: Path) -> ParsedModule:
    """Load and parse a single Python source file."""
    return parse_source(load_source_file(path))


def analyze_directory(path: Path, *, recursive: bool = True) -> list[ParsedModule]:
    """Load and parse every Python source file under ``path``."""
    return [parse_source(source) for source in load_source_directory(path, recursive=recursive)]
