"""活动清体力场景路由的单元测试（`common/farm_flow.py`）。

这些测试不需要设备也不需要 maafw：`farm_flow` 是纯函数，pipeline 只负责「探测 +
override_next」，所以决策逻辑的正确性全部压在这里。
"""

from __future__ import annotations

import pytest
from common.farm_flow import (
    DEFAULT_EXCHANGE_CANCEL_NODE,
    DEFAULT_STOP_NODE,
    SCENE_ACTIVITY_TAB,
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
    load_params,
    pick_scene,
    route,
)
from common.params import ParamError
from common.state import STOP_DEATH_LIMIT, STOP_STAMINA, STOP_TARGET, STOP_UNKNOWN_LIMIT, FarmPlan, FarmProgress

PROBES = (
    Probe(SCENE_CRYSTAL, "ActivityFarmCrystalPopup"),
    Probe(SCENE_EXCHANGE, "ActivityFarmExchangePopup"),
    Probe(SCENE_DEAD, "ActivityFarmDead"),
    Probe(SCENE_NEED_STAMINA, "ActivityFarmNeedStamina"),
    Probe(SCENE_RESULT, "ActivityFarmResult"),
    Probe(SCENE_READY, "ActivityFarmReady"),
    Probe(SCENE_ASSIST, "ActivityFarmAssist"),
    Probe(SCENE_START, "ActivityFarmStart"),
    Probe(SCENE_ACTIVITY_TAB, "ActivityFarmActivityTab"),
)


def make_params(**plan_kwargs: object) -> RunParams:
    """默认与 pipeline 参数对齐：刷到没体力为止。"""

    plan_kwargs.setdefault("until_no_stamina", True)
    return RunParams(probes=PROBES, plan=FarmPlan(**plan_kwargs))


# --------------------------------------------------------------------------- #
# 参数解析
# --------------------------------------------------------------------------- #


def test_load_params_accepts_pair_list() -> None:
    params = load_params({"probe": [["crystal", "A"], ["result", "B"]], "stop_node": "Home"})
    assert params.probes == (Probe("crystal", "A"), Probe("result", "B"))
    assert params.stop_node == "Home"


def test_load_params_accepts_dict_items_and_json_string() -> None:
    raw = '{"probe": [{"scene": "dead", "node": "DeadNode"}], "max_deaths": 1}'
    params = load_params(raw)
    assert params.probes == (Probe("dead", "DeadNode"),)
    assert params.plan.max_deaths == 1


def test_load_params_defaults() -> None:
    params = load_params(None)
    assert params.probes == ()
    assert params.stop_node == DEFAULT_STOP_NODE
    assert params.exchange_cancel_node == DEFAULT_EXCHANGE_CANCEL_NODE
    assert params.plan.until_no_stamina is True


def test_load_params_rejects_unknown_scene() -> None:
    with pytest.raises(ParamError):
        load_params({"probe": [["whatever", "X"]]})


def test_load_params_rejects_broken_json() -> None:
    with pytest.raises(ParamError):
        load_params("{not json")


def test_load_params_rejects_bad_probe_shape() -> None:
    with pytest.raises(ParamError):
        load_params({"probe": ["crystal"]})


# --------------------------------------------------------------------------- #
# 场景选择
# --------------------------------------------------------------------------- #


def test_pick_scene_follows_probe_order() -> None:
    params = make_params()
    assert pick_scene({"result": True, "ready": True}, params) == SCENE_RESULT
    assert pick_scene({"ready": True, "assist": True}, params) == SCENE_READY


def test_pick_scene_returns_none_when_nothing_hits() -> None:
    assert pick_scene({}, make_params()) is None


# --------------------------------------------------------------------------- #
# 单场景路由
# --------------------------------------------------------------------------- #


def test_crystal_only_cancels_and_marks_stamina() -> None:
    state, params = FarmProgress(), make_params()
    result = route(SCENE_CRYSTAL, state, params)
    assert result.target == "ActivityFarmCrystalPopup"
    assert result.reason == STOP_STAMINA
    assert state.crystal_seen and state.stamina_insufficient
    assert state.in_round is False


def test_exchange_counts_once_then_cancels() -> None:
    state, params = FarmProgress(), make_params()
    first = route(SCENE_EXCHANGE, state, params)
    assert first.target == "ActivityFarmExchangePopup"
    assert state.exchange_used == 1

    second = route(SCENE_EXCHANGE, state, params)
    assert second.target == params.exchange_cancel_node
    assert second.reason == "exchange_limit"
    assert state.exchange_used == 1


def test_exchange_limit_zero_never_spends() -> None:
    state = FarmProgress()
    params = make_params(exchange_limit=0)
    assert route(SCENE_EXCHANGE, state, params).target == params.exchange_cancel_node
    assert state.exchange_used == 0


def test_dead_increments_and_reports_limit() -> None:
    state, params = FarmProgress(), make_params(max_deaths=2)
    assert route(SCENE_DEAD, state, params).target == "ActivityFarmDead"
    assert state.deaths == 1
    second = route(SCENE_DEAD, state, params)
    assert second.reason == STOP_DEATH_LIMIT
    assert state.stop_reason == STOP_DEATH_LIMIT


def test_need_stamina_marks_without_override() -> None:
    state, params = FarmProgress(), make_params()
    result = route(SCENE_NEED_STAMINA, state, params)
    assert result.target == "ActivityFarmNeedStamina"
    assert state.stamina_insufficient


def test_battle_bound_sets_expect_flag() -> None:
    state, params = FarmProgress(), make_params()
    for scene in (SCENE_READY, SCENE_ASSIST, SCENE_START):
        route(scene, state, params)
        assert state.expect_battle is True
        assert state.in_round is True


def test_navigation_scene_does_not_touch_counters() -> None:
    state, params = FarmProgress(), make_params()
    route(SCENE_ACTIVITY_TAB, state, params)
    assert (state.battles, state.deaths, state.unknown) == (0, 0, 0)


def test_unknown_scene_falls_back_until_limit() -> None:
    state, params = FarmProgress(), make_params(max_unknown=3)
    assert route(None, state, params).override is False
    assert route(None, state, params).override is False
    third = route(None, state, params)
    assert third.target == params.stop_node
    assert third.reason == STOP_UNKNOWN_LIMIT


def test_unknown_scene_with_zero_limit_stops_at_once() -> None:
    state = FarmProgress()
    params = make_params(max_unknown=0)
    assert route(None, state, params).override is False


# --------------------------------------------------------------------------- #
# 结算判定
# --------------------------------------------------------------------------- #


def test_after_battle_counts_once_per_battle() -> None:
    state, params = FarmProgress(), make_params()
    route(SCENE_START, state, params)
    assert after_battle(state, params).override is False
    assert state.battles == 1

    # 没有经过开战就再看到结算 = 残留帧，不重复计数
    route(SCENE_RESULT, state, params)
    assert after_battle(state, params).override is False
    assert state.battles == 1


def test_after_battle_stops_when_target_reached() -> None:
    state, params = FarmProgress(), make_params(max_times=1)
    route(SCENE_START, state, params)
    result = after_battle(state, params)
    assert result.target == params.stop_node
    assert result.reason == STOP_TARGET


def test_after_battle_stops_when_out_of_stamina() -> None:
    state, params = FarmProgress(), make_params()
    route(SCENE_NEED_STAMINA, state, params)
    route(SCENE_START, state, params)
    result = after_battle(state, params)
    assert result.reason == STOP_STAMINA
    assert state.stop_reason == STOP_STAMINA


def test_after_battle_stops_on_death_limit() -> None:
    state, params = FarmProgress(), make_params(max_deaths=1)
    route(SCENE_DEAD, state, params)
    route(SCENE_START, state, params)
    assert after_battle(state, params).reason == STOP_DEATH_LIMIT


# --------------------------------------------------------------------------- #
# 轮次
# --------------------------------------------------------------------------- #


def test_begin_round_clears_stamina_but_keeps_totals() -> None:
    state = FarmProgress()
    begin_round(state)
    route(SCENE_EXCHANGE, state, params := make_params())
    route(SCENE_START, state, params)
    after_battle(state, params)
    route(SCENE_CRYSTAL, state, params)

    assert state.rounds == 1
    assert state.stamina_insufficient is True
    assert state.battles == 1
    assert state.exchange_used == 1

    assert begin_round(state) is True
    assert state.rounds == 2
    assert state.stamina_insufficient is False
    assert state.crystal_seen is False
    assert state.battles == 1
    assert state.exchange_used == 1


def test_begin_round_is_idempotent_while_in_round() -> None:
    state = FarmProgress()
    begin_round(state)
    assert begin_round(state) is False
    assert state.rounds == 1
