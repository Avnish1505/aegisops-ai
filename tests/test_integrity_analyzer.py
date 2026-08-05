"""Unit tests for the Bundle 1 Implementation Integrity Analyzer scaffolding."""

from pathlib import Path

import pytest

from aegisops.integrity_analyzer.api import analyze_directory, analyze_file
from aegisops.integrity_analyzer.ast_parser import parse_source
from aegisops.integrity_analyzer.models import ParsedModule, SourceFile
from aegisops.integrity_analyzer.source_loader import (
    MAX_SOURCE_BYTES,
    load_source_directory,
    load_source_file,
)


def test_load_source_file_reads_utf8_content(tmp_path: Path) -> None:
    module_path = tmp_path / "sample.py"
    module_path.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    source = load_source_file(module_path)

    assert isinstance(source, SourceFile)
    assert source.path == module_path
    assert "def greet" in source.content


def test_load_source_file_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        load_source_file(tmp_path / "missing.py")


def test_load_source_file_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a file"):
        load_source_file(tmp_path)


def test_load_source_file_rejects_non_python_suffix(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("not python", encoding="utf-8")

    with pytest.raises(ValueError, match=r"\.py suffix"):
        load_source_file(text_path)


def test_load_source_file_rejects_oversized_file(tmp_path: Path) -> None:
    large_path = tmp_path / "large.py"
    large_path.write_text("x" * (MAX_SOURCE_BYTES + 1), encoding="utf-8")

    with pytest.raises(ValueError, match="byte limit"):
        load_source_file(large_path)


def test_load_source_directory_returns_sorted_files(tmp_path: Path) -> None:
    (tmp_path / "b_module.py").write_text("b = 1\n", encoding="utf-8")
    (tmp_path / "a_module.py").write_text("a = 1\n", encoding="utf-8")

    sources = load_source_directory(tmp_path, recursive=False)

    assert [source.path.name for source in sources] == ["a_module.py", "b_module.py"]


def test_load_source_directory_recurses_by_default(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "top.py").write_text("top = 1\n", encoding="utf-8")
    (nested / "inner.py").write_text("inner = 1\n", encoding="utf-8")

    sources = load_source_directory(tmp_path)

    assert {source.path.name for source in sources} == {"top.py", "inner.py"}


def test_load_source_directory_skips_ignored_directories(tmp_path: Path) -> None:
    ignored = tmp_path / "__pycache__"
    ignored.mkdir()
    (ignored / "cached.py").write_text("cached = 1\n", encoding="utf-8")
    (tmp_path / "real.py").write_text("real = 1\n", encoding="utf-8")

    sources = load_source_directory(tmp_path)

    assert [source.path.name for source in sources] == ["real.py"]


def test_load_source_directory_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        load_source_directory(tmp_path / "missing")


def test_load_source_directory_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no .py files found"):
        load_source_directory(tmp_path)


def test_parse_source_returns_parsed_module(tmp_path: Path) -> None:
    module_path = tmp_path / "sample.py"
    module_path.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")
    source = load_source_file(module_path)

    parsed = parse_source(source)

    assert isinstance(parsed, ParsedModule)
    assert parsed.source == source
    assert len(parsed.tree.body) == 1


def test_parse_source_rejects_invalid_syntax(tmp_path: Path) -> None:
    module_path = tmp_path / "broken.py"
    module_path.write_text("def broken(:\n", encoding="utf-8")
    source = load_source_file(module_path)

    with pytest.raises(ValueError, match="invalid syntax"):
        parse_source(source)


def test_analyze_file_loads_and_parses(tmp_path: Path) -> None:
    module_path = tmp_path / "sample.py"
    module_path.write_text("class Sample:\n    pass\n", encoding="utf-8")

    parsed = analyze_file(module_path)

    assert isinstance(parsed, ParsedModule)
    assert parsed.source.path == module_path
    assert len(parsed.tree.body) == 1


def test_analyze_directory_loads_and_parses_every_module(tmp_path: Path) -> None:
    (tmp_path / "one.py").write_text("one = 1\n", encoding="utf-8")
    (tmp_path / "two.py").write_text("two = 2\n", encoding="utf-8")

    parsed_modules = analyze_directory(tmp_path, recursive=False)

    assert [module.source.path.name for module in parsed_modules] == ["one.py", "two.py"]
    assert all(isinstance(module.tree.body, list) for module in parsed_modules)
