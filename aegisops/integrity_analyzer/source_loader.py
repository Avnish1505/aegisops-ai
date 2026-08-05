"""Load Python source files from disk without executing or modifying them."""

from __future__ import annotations

from pathlib import Path

from aegisops.integrity_analyzer.models import SourceFile

PYTHON_SUFFIX = ".py"
MAX_SOURCE_BYTES = 2_000_000

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
    }
)


def load_source_file(path: Path) -> SourceFile:
    """Read a single ``.py`` file as UTF-8 text, enforcing a bounded size."""
    if not path.exists():
        raise ValueError(f"source file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"source path is not a file: {path}")
    if path.suffix != PYTHON_SUFFIX:
        raise ValueError(f"source file must have a {PYTHON_SUFFIX} suffix: {path}")

    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        raise ValueError(
            f"source file exceeds {MAX_SOURCE_BYTES} byte limit ({size} bytes): {path}"
        )

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"source file is not valid UTF-8: {path}") from error

    return SourceFile(path=path, content=content)


def load_source_directory(directory: Path, *, recursive: bool = True) -> list[SourceFile]:
    """Load every ``.py`` file under ``directory``, skipping tooling/build noise."""
    if not directory.exists():
        raise ValueError(f"source directory does not exist: {directory}")
    if not directory.is_dir():
        raise ValueError(f"source path is not a directory: {directory}")

    pattern = f"**/*{PYTHON_SUFFIX}" if recursive else f"*{PYTHON_SUFFIX}"
    paths = [
        path
        for path in sorted(directory.glob(pattern))
        if IGNORED_DIRECTORY_NAMES.isdisjoint(path.relative_to(directory).parts[:-1])
    ]
    if not paths:
        raise ValueError(f"no {PYTHON_SUFFIX} files found under: {directory}")

    return [load_source_file(path) for path in paths]
