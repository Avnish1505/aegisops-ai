"""Immutable value objects shared by the source loader, AST parser, and public API."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum
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


class ScaffoldClassification(StrEnum):
    """The exact scaffold marker found as a function's entire body."""

    PASS = "pass"
    ELLIPSIS = "ellipsis"
    DOCSTRING_ONLY = "docstring_only"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True)
class ScaffoldFinding:
    """A function whose body contains only a scaffold marker, not an implementation."""

    function: str
    line: int
    classification: ScaffoldClassification
    file: Path
