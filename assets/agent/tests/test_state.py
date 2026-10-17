"""`agent/common/state.py` 的单元测试。"""

from __future__ import annotations

import pytest

from common.state import (
    STOP_FAILURE_LIMIT,
    STOP_STAMINA,
    STOP_TARGET,
    FarmPlan,
    FarmProgress,
    decide_stop,
)


def test_plan_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        FarmPlan(max_times=-1)
    with pytest.raises(ValueError):
        FarmPlan(max_failures=-1)


def test_unlimited_plan_never_stops_on_count() -> None:
    plan = FarmPlan(max_times=0)
    progress = FarmProgress(battles=999)
    assert decide_stop(plan, progress) == (False, "")


def test_stops_when_target_reached() -> None:
    plan = FarmPlan(max_times=3)
    progress = FarmProgress(battles=3)
    assert decide_stop(plan, progress) == (True, STOP_TARGET)

    progress.battles = 2
    assert decide_stop(plan, progress) == (False, "")


def test_stamina_stop_only_when_plan_requests_it() -> None:
    progress = FarmProgress(battles=1)
    assert decide_stop(FarmPlan(until_no_stamina=True), progress, stamina_insufficient=True) == (True, STOP_STAMINA)
    assert decide_stop(FarmPlan(until_no_stamina=False), progress, stamina_insufficient=True) == (False, "")


def test_failure_limit_takes_priority() -> None:
    plan = FarmPlan(max_times=1, until_no_stamina=True, max_failures=2)
    progress = FarmProgress(battles=1, failures=2)
    assert decide_stop(plan, progress, stamina_insufficient=True) == (True, STOP_FAILURE_LIMIT)


def test_record_helpers() -> None:
    progress = FarmProgress()
    progress.record_battle()
    progress.record_failure()
    assert (progress.battles, progress.failures) == (1, 1)
    progress.reset()
    assert (progress.battles, progress.failures) == (0, 0)


def test_failure_limit_reached_by_farm_fail_semantics() -> None:
    """FarmFail 语义：累计失败达到 max_failures 即放弃，且优先于其它条件。"""

    plan = FarmPlan(max_failures=2)
    progress = FarmProgress()
    progress.record_failure()
    assert decide_stop(plan, progress)[0] is False
    progress.record_failure()
    assert decide_stop(plan, progress) == (True, STOP_FAILURE_LIMIT)
    assert decide_stop(plan, progress, stamina_insufficient=True) == (True, STOP_FAILURE_LIMIT)


def test_zero_failure_limit_disables_guard() -> None:
    plan = FarmPlan(max_failures=0)
    progress = FarmProgress(failures=99)
    assert decide_stop(plan, progress)[0] is False


def test_stamina_flag_is_consumed_once() -> None:
    progress = FarmProgress()
    progress.note_stamina_insufficient()
    assert progress.consume_stamina_flag() is True
    assert progress.consume_stamina_flag() is False
    assert progress.stamina_insufficient is False


def test_reset_clears_stamina_flag() -> None:
    progress = FarmProgress(battles=2, failures=1)
    progress.note_stamina_insufficient()
    progress.reset()
    assert progress.consume_stamina_flag() is False
