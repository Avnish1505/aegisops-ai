"""50 seeded scenarios x 13 fault classes: every fault caught, no clean plan falsely blocked."""

import pytest

from aegisops.verification.models import CheckSeverity, Verdict

from .corpus import SEEDS, clean_case
from .mutators import MUTATORS, Mutator


def test_there_are_thirteen_fault_classes() -> None:
    assert len(MUTATORS) == 13
    assert len({mutator.name for mutator in MUTATORS}) == 13


@pytest.mark.parametrize("seed", SEEDS)
def test_clean_solver_plan_is_not_blocked(seed: int) -> None:
    report = clean_case(seed).verify()

    assert [check.id for check in report.failed()] == []
    assert report.verdict == Verdict.PASS


@pytest.mark.parametrize("mutator", MUTATORS, ids=lambda mutator: mutator.name)
@pytest.mark.parametrize("seed", SEEDS)
def test_injected_fault_is_caught(seed: int, mutator: Mutator) -> None:
    report = mutator.apply(clean_case(seed)).verify()

    check = report.check(mutator.expected_check)
    assert not check.passed, f"{mutator.name} not caught on seed {seed}"
    assert check.severity == mutator.expected_severity
    if mutator.expected_severity == CheckSeverity.CRITICAL:
        assert report.verdict == Verdict.BLOCKED
    else:
        assert mutator.expected_check not in report.blocking_check_ids


@pytest.mark.parametrize("seed", SEEDS[:5])
def test_mutators_do_not_touch_the_clean_case(seed: int) -> None:
    before = clean_case(seed)
    for mutator in MUTATORS:
        mutator.apply(before)

    assert clean_case(seed).verify().failed() == []
