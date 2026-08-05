"""Parse loaded source text into an abstract syntax tree without executing it."""

from __future__ import annotations

import ast

from aegisops.integrity_analyzer.models import ParsedModule, SourceFile


def parse_source(source: SourceFile) -> ParsedModule:
    """Parse ``source`` into a :class:`ParsedModule`; the source is never executed."""
    try:
        tree = ast.parse(source.content, filename=str(source.path))
    except SyntaxError as error:
        raise ValueError(f"source file has invalid syntax: {source.path} ({error.msg})") from error

    return ParsedModule(source=source, tree=tree)
