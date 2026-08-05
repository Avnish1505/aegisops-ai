"""Immutable value objects shared by the source loader, AST parser, and public API."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceFile:
    """Raw Python source text read from disk, not yet parsed or analyzed."""

    path: Path
    content: str


@dataclass(frozen=True)
class ParsedModule:
    """A source file paired with its parsed abstract syntax tree."""

    source: SourceFile
    tree: ast.Module
