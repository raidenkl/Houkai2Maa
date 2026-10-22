"""表驱动的场景序列回放：不花体力也能回归「刷本会不会停对/数对」。

每个用例是一串「界面场景」，按适配器的真实顺序驱动 `farm_flow`：
Entry 路由 → （若到结算页）`after_battle` 判定。任何一条停止原因出现就结束，
与 pipeline 里 `override_next` 收尾的行为一致。

这套测试替代不了真机，但它能锁住历史 bug：
* 第二轮被 `max_hit` 整段跳过（现在靠轮次状态而不是计数器）；
* 体力标志跨轮不清理导致第二轮立刻停；
* 「再来一次」后的残留结算帧被重复计数；
* 死亡 / 未知场景无限空转。
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from common.farm_flow import (
    SCENE_ASSIST,
    SCENE_CRYSTAL,
    SCENE_DEAD,
    SCENE_EXCHANGE,
    SCENE_NEED_STAMINA,
    SCENE_READY,
    SCENE_RESULT,
    SCENE_START,
    Probe,
    RunParams,
    after_battle,
    begin_round,
    route,
)
from common.state import (
    STOP_DEATH_LIMIT,
    STOP_STAMINA,
    STOP_TARGET,
    STOP_UNKNOWN_LIMIT,
    FarmPlan,
    FarmProgress,
)

PROBES = (
    Probe(SCENE_CRYSTAL, "ActivityFarmCrystalPopup"),
    Probe(SCENE_EXCHANGE, "ActivityFarmExchangePopup"),
    Probe(SCENE_DEAD, "ActivityFarmDead"),
    Probe(SCENE_NEED_STAMINA, "ActivityFarmNeedStamina"),
    Probe(SCENE_RESULT, "ActivityFarmResult"),
    Probe(SCENE_READY, "ActivityFarmReady"),
    Probe(SCENE_ASSIST, "ActivityFarmAssist"),
    Probe(SCENE_START, "ActivityFarmStart"),
)

STOP_REASONS = {STOP_STAMINA, STOP_TARGET, STOP_DEATH_LIMIT, STOP_UNKNOWN_LIMIT, "failure_limit"}

#: 只结束「这一轮」的停止原因：体力没了/兑换用完了/死太多，等魔女补体力后还能开下一轮
ROUND_STOPS = {STOP_STAMINA, STOP_DEATH_LIMIT, "exchange_limit"}

#: 直接结束「整个任务」的停止原因
TASK_STOPS = {STOP_TARGET, STOP_UNKNOWN_LIMIT, "failure_limit"}


def run(sequences: Sequence[Sequence[str | None]], plan: FarmPlan) -> tuple[FarmProgress, str, str | None]:
    """按轮次跑若干场景序列，返回 (最终状态, 停止原因, 最后的目标节点)。

    轮内停止（体力/死亡/兑换额度）只中断当前轮，接着跑下一轮；
    任务级停止（次数达标/未知场景）直接结束。
    """

    params = RunParams(probes=PROBES, plan=plan)
    state = FarmProgress()
    reason, target = "", None
    for sequence in sequences:
        begin_round(state)
        for scene in sequence:
            routed = route(scene, state, params)
            reason, target = routed.reason, routed.target
            if scene == SCENE_RESULT:
                after = after_battle(state, params)
                reason, target = after.reason, after.target
            if reason in TASK_STOPS:
                return state, reason, target
            if reason in ROUND_STOPS:
                break
    return state, reason, target


def default_plan(**overrides: object) -> FarmPlan:
    overrides.setdefault("until_no_stamina", True)
    return FarmPlan(**overrides)  # type: ignore[arg-type]


def test_two_battles_then_out_of_stamina() -> None:
    state, reason, target = run(
        [
            [
                SCENE_READY,
                SCENE_ASSIST,
                SCENE_START,
                SCENE_RESULT,
                SCENE_ASSIST,
                SCENE_START,
                SCENE_RESULT,
                SCENE_NEED_STAMINA,
                SCENE_CRYSTAL,
            ]
        ],
        default_plan(),
    )
    assert state.battles == 2
    assert reason == STOP_STAMINA
    assert target == "ActivityFarmCrystalPopup"


def test_stale_result_frame_is_not_double_counted() -> None:
    state, _, _ = run([[SCENE_READY, SCENE_ASSIST, SCENE_START, SCENE_RESULT, SCENE_RESULT]], default_plan())
    assert state.battles == 1


def test_stops_at_max_times() -> None:
    state, reason, target = run(
        [[SCENE_READY, SCENE_ASSIST, SCENE_START, SCENE_RESULT, SCENE_ASSIST, SCENE_START, SCENE_RESULT]],
        default_plan(max_times=1),
    )
    assert state.battles == 1
    assert reason == STOP_TARGET
    assert target == "ActivityFarmHome"


def test_stops_on_death_limit() -> None:
    state, reason, _ = run([[SCENE_DEAD, SCENE_DEAD]], default_plan(max_deaths=2))
    assert state.deaths == 2
    assert reason == STOP_DEATH_LIMIT
    assert state.stop_reason == STOP_DEATH_LIMIT


def test_stops_on_unknown_limit() -> None:
    state, reason, target = run([[None, None, None]], default_plan(max_unknown=3))
    assert state.unknown == 3
    assert reason == STOP_UNKNOWN_LIMIT
    assert target == "ActivityFarmHome"


def test_exchange_then_close_without_spending_again() -> None:
    state, reason, target = run([[SCENE_EXCHANGE, SCENE_EXCHANGE]], default_plan())
    assert state.exchange_used == 1
    assert reason == "exchange_limit"
    assert target == "ActivityFarmExchangeCancel"


def test_second_round_runs_after_stamina_refill() -> None:
    """一键日常两轮：第一轮打完没体力 → 魔女补 100 → 第二轮必须能继续跑。"""

    state, reason, _ = run(
        [
            [SCENE_READY, SCENE_ASSIST, SCENE_START, SCENE_RESULT, SCENE_NEED_STAMINA, SCENE_CRYSTAL],
            [SCENE_READY, SCENE_ASSIST, SCENE_START, SCENE_RESULT, SCENE_NEED_STAMINA, SCENE_CRYSTAL],
        ],
        default_plan(),
    )
    assert state.rounds == 2
    assert state.battles == 2
    assert reason == STOP_STAMINA


def test_rounds_do_not_reset_totals() -> None:
    """max_times 是整次任务的预算，第二轮不能重新从 0 计。"""

    state, reason, _ = run(
        [
            [SCENE_READY, SCENE_ASSIST, SCENE_START, SCENE_RESULT],
            [SCENE_READY, SCENE_ASSIST, SCENE_START, SCENE_RESULT],
        ],
        default_plan(max_times=1),
    )
    assert state.battles == 1
    assert reason == STOP_TARGET


@pytest.mark.parametrize("deaths", [2, 3])
def test_death_limit_respected(deaths: int) -> None:
    state, reason, _ = run([[SCENE_DEAD] * deaths], default_plan(max_deaths=2))
    assert reason == STOP_DEATH_LIMIT
    assert state.deaths >= 2
