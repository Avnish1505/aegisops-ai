"""Unit tests for the Implementation Integrity Analyzer (Bundles 1-2)."""

from pathlib import Path

import pytest

from aegisops.integrity_analyzer.api import (
    analyze_directory,
    analyze_file,
    find_scaffolded_functions,
    find_scaffolded_functions_in_directory,
)
from aegisops.integrity_analyzer.ast_parser import parse_source
from aegisops.integrity_analyzer.models import ParsedModule, ScaffoldClassification, SourceFile
from aegisops.integrity_analyzer.scaffold_detector import detect_scaffolded_functions
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


def _parse(tmp_path: Path, source: str) -> ParsedModule:
    module_path = tmp_path / "module.py"
    module_path.write_text(source, encoding="utf-8")
    return parse_source(load_source_file(module_path))


def test_detects_pass_only_function(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def stub():\n    pass\n")

    findings = detect_scaffolded_functions(parsed)

    assert len(findings) == 1
    assert findings[0].function == "stub"
    assert findings[0].line == 1
    assert findings[0].classification == ScaffoldClassification.PASS
    assert findings[0].file == parsed.source.path


def test_detects_ellipsis_only_function(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def stub():\n    ...\n")

    findings = detect_scaffolded_functions(parsed)

    assert len(findings) == 1
    assert findings[0].classification == ScaffoldClassification.ELLIPSIS


def test_detects_docstring_only_function(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def stub():\n    'TODO: implement this.'\n")

    findings = detect_scaffolded_functions(parsed)

    assert len(findings) == 1
    assert findings[0].classification == ScaffoldClassification.DOCSTRING_ONLY


def test_detects_raise_not_implemented_error_call(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def stub():\n    raise NotImplementedError()\n")

    findings = detect_scaffolded_functions(parsed)

    assert len(findings) == 1
    assert findings[0].classification == ScaffoldClassification.NOT_IMPLEMENTED


def test_detects_raise_not_implemented_error_with_message(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def stub():\n    raise NotImplementedError('later')\n")

    findings = detect_scaffolded_functions(parsed)

    assert len(findings) == 1
    assert findings[0].classification == ScaffoldClassification.NOT_IMPLEMENTED


def test_detects_bare_raise_not_implemented_error(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def stub():\n    raise NotImplementedError\n")

    findings = detect_scaffolded_functions(parsed)

    assert len(findings) == 1
    assert findings[0].classification == ScaffoldClassification.NOT_IMPLEMENTED


def test_ignores_implemented_function(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def real():\n    return 1 + 1\n")

    assert detect_scaffolded_functions(parsed) == []


def test_ignores_other_raised_exceptions(tmp_path: Path) -> None:
    parsed = _parse(tmp_path, "def stub():\n    raise ValueError('nope')\n")

    assert detect_scaffolded_functions(parsed) == []


def test_ignores_docstring_followed_by_pass(tmp_path: Path) -> None:
    """A multi-statement body is not one of the four exact scaffold shapes."""
    parsed = _parse(tmp_path, "def stub():\n    'doc'\n    pass\n")

    assert detect_scaffolded_functions(parsed) == []


def test_detects_scaffolded_method_and_async_function(tmp_path: Path) -> None:
    source = (
        "class Service:\n"
        "    def handle(self):\n"
        "        pass\n"
        "\n"
        "async def fetch():\n"
        "    ...\n"
    )
    parsed = _parse(tmp_path, source)

    findings = detect_scaffolded_functions(parsed)

    assert {finding.function for finding in findings} == {"handle", "fetch"}
    handle = next(finding for finding in findings if finding.function == "handle")
    assert handle.line == 2
    assert handle.classification == ScaffoldClassification.PASS


def test_find_scaffolded_functions_reads_from_disk(tmp_path: Path) -> None:
    module_path = tmp_path / "stub.py"
    module_path.write_text("def stub():\n    pass\n", encoding="utf-8")

    findings = find_scaffolded_functions(module_path)

    assert len(findings) == 1
    assert findings[0].file == module_path


def test_find_scaffolded_functions_in_directory_aggregates_findings(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def a():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def b():\n    return 1\n", encoding="utf-8")

    findings = find_scaffolded_functions_in_directory(tmp_path, recursive=False)

    assert len(findings) == 1
    assert findings[0].function == "a"
    assert findings[0].file == tmp_path / "a.py"
