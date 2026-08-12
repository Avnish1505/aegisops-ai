"""Unit tests for the safety-critical wiring checker.

Exactly five scenarios, per module scope: gate wired in, gate never called,
operation bypassing the gate, operation correctly wired to the gate, and
both failure modes present in the same file.
"""

from pathlib import Path

from aegisops.integrity_analyzer.ast_parser import parse_source
from aegisops.integrity_analyzer.models import ParsedModule
from aegisops.integrity_analyzer.source_loader import load_source_file
from aegisops.integrity_analyzer.wiring_checker import (
    WiringFailureMode,
    check_safety_wiring,
)


def _parse(tmp_path: Path, source: str) -> ParsedModule:
    module_path = tmp_path / "module.py"
    module_path.write_text(source, encoding="utf-8")
    return parse_source(load_source_file(module_path))


def test_gate_defined_and_called_by_operation_produces_no_flags(tmp_path: Path) -> None:
    """A safety-critical function that is defined and actually called: no flags."""
    source = (
        "def validate_safety_gate():\n"
        "    return True\n"
        "\n"
        "def dispatch_resources():\n"
        "    validate_safety_gate()\n"
        "    return do_dispatch()\n"
    )
    parsed = _parse(tmp_path, source)

    findings = check_safety_wiring(
        parsed,
        safety_critical_names=["validate_safety_gate"],
        operation_keywords=["dispatch"],
    )

    assert findings == []


def test_gate_never_called_is_flagged(tmp_path: Path) -> None:
    """A safety-critical function that is defined but called nowhere is flagged."""
    source = "def validate_safety_gate():\n    return True\n\ndef unrelated():\n    return 1\n"
    parsed = _parse(tmp_path, source)

    findings = check_safety_wiring(
        parsed,
        safety_critical_names=["validate_safety_gate"],
        operation_keywords=["dispatch"],
    )

    assert len(findings) == 1
    assert findings[0].function == "validate_safety_gate"
    assert findings[0].line == 1
    assert findings[0].failure_mode == WiringFailureMode.DEFINED_BUT_NEVER_CALLED


def test_operation_without_gate_call_is_flagged(tmp_path: Path) -> None:
    """A critical operation that runs without calling any safety-critical function is flagged."""
    source = (
        "def validate_safety_gate():\n"
        "    return True\n"
        "\n"
        "def some_admin_check():\n"
        "    validate_safety_gate()\n"
        "\n"
        "def dispatch_resources():\n"
        "    return do_dispatch()\n"
    )
    parsed = _parse(tmp_path, source)

    findings = check_safety_wiring(
        parsed,
        safety_critical_names=["validate_safety_gate"],
        operation_keywords=["dispatch"],
    )

    assert len(findings) == 1
    assert findings[0].function == "dispatch_resources"
    assert findings[0].failure_mode == WiringFailureMode.GUARDED_OP_BYPASSES_GATE


def test_operation_that_calls_gate_first_produces_no_bypass_flag(tmp_path: Path) -> None:
    """A critical operation that calls the safety gate before running: no bypass flag."""
    source = (
        "def validate_safety_gate():\n"
        "    return True\n"
        "\n"
        "def dispatch_resources():\n"
        "    validate_safety_gate()\n"
        "    return do_dispatch()\n"
    )
    parsed = _parse(tmp_path, source)

    findings = check_safety_wiring(
        parsed,
        safety_critical_names=["validate_safety_gate"],
        operation_keywords=["dispatch"],
    )

    assert findings == []


def test_report_contains_both_failure_modes_together(tmp_path: Path) -> None:
    """A file with an unwired gate and a separate bypassed gate reports both failure modes."""
    source = (
        "def validate_safety_gate():\n"
        "    return True\n"
        "\n"
        "def requires_human_approval():\n"
        "    return True\n"
        "\n"
        "def dispatch_resources():\n"
        "    validate_safety_gate()\n"
        "    return do_dispatch()\n"
        "\n"
        "def execute_plan():\n"
        "    return run_plan()\n"
    )
    parsed = _parse(tmp_path, source)

    findings = check_safety_wiring(
        parsed,
        safety_critical_names=["validate_safety_gate", "requires_human_approval"],
        operation_keywords=["dispatch", "execute"],
    )

    failure_modes = {finding.failure_mode for finding in findings}
    assert failure_modes == {
        WiringFailureMode.DEFINED_BUT_NEVER_CALLED,
        WiringFailureMode.GUARDED_OP_BYPASSES_GATE,
    }
    never_called = next(
        f for f in findings if f.failure_mode == WiringFailureMode.DEFINED_BUT_NEVER_CALLED
    )
    bypassed = next(
        f for f in findings if f.failure_mode == WiringFailureMode.GUARDED_OP_BYPASSES_GATE
    )
    assert never_called.function == "requires_human_approval"
    assert bypassed.function == "execute_plan"
