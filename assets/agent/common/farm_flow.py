"""活动清体力（ActivityFarm）的场景路由与循环收敛 —— 纯逻辑，禁止 import maa。

为什么需要它：pipeline 只能靠 `next` 候选的**顺序**表达「我现在在哪个界面」，
而「这一场算不算数 / 还能不能换体力 / 该不该收尾」需要跨节点累计。JSON 里只能用
`max_hit` 硬编码，它的语义是**整次任务累计**，所以第二轮会整段跳过
（2026-10-21 实测：FindBonus / 双倍券第二轮全跳过，结算页卡 45s）。

这里把决策拆成两半：

* `pick_scene` / 惰性探测：按 JSON 给的 `probe` 顺序选出当前场景；
* `route`：根据场景 + 累计状态给出「下一个节点」，`None` 表示不干预、落回 JSON 顺序。

`route` 返回非 None 时，适配器调用 `context.override_next`。

设计约束（改这里之前先读）：

1. 水晶购买窗**永远只取消**：pipeline 里根本不存在「确认购买」节点，
   本模块也不允许出现指向水晶购买的 target。
2. 结算只计一次：必须 `expect_battle` 为真（说明刚经过备战/助战/开战），
   否则视为「再来一次」后的残留帧，不重复计数。
3. 轮次之间要塞「勤劳的魔女」领 100 体力，所以 `begin_round` 会清体力标志，
   但**不清** `battles` / `exchange_used`（它们代表整次任务的消耗）。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from common.params import ParamError, as_bool, as_int, as_str
from common.state import (
    STOP_DEATH_LIMIT,
    STOP_STAMINA,
    STOP_TARGET,
    STOP_UNKNOWN_LIMIT,
    FarmPlan,
    FarmProgress,
    decide_stop,
)

SCENE_CRYSTAL = "crystal"
SCENE_EXCHANGE = "exchange"
SCENE_DEAD = "dead"
SCENE_NEED_STAMINA = "need_stamina"
SCENE_RESULT = "result"
SCENE_READY = "ready"
SCENE_ASSIST = "assist"
SCENE_START = "start"
SCENE_STAGE = "stage"
SCENE_LIST = "list"
SCENE_ACTIVITY_TAB = "activity_tab"
SCENE_BATTLE_TAB = "battle_tab"

KNOWN_SCENES = frozenset(
    {
        SCENE_CRYSTAL,
        SCENE_EXCHANGE,
        SCENE_DEAD,
        SCENE_NEED_STAMINA,
        SCENE_RESULT,
        SCENE_READY,
        SCENE_ASSIST,
        SCENE_START,
        SCENE_STAGE,
        SCENE_LIST,
        SCENE_ACTIVITY_TAB,
        SCENE_BATTLE_TAB,
    }
)

#: 路由到这些场景说明「马上要开打」，之后的结算帧才计一场
BATTLE_BOUND_SCENES = frozenset({SCENE_READY, SCENE_ASSIST, SCENE_START})

#: 路由到这些场景说明「这一场已经结束/被打断」，需要清掉期待标记
BATTLE_END_SCENES = frozenset({SCENE_RESULT, SCENE_DEAD, SCENE_CRYSTAL, SCENE_NEED_STAMINA})

DEFAULT_STOP_NODE = "ActivityFarmHome"
DEFAULT_EXCHANGE_CANCEL_NODE = "ActivityFarmExchangeCancel"


@dataclass(frozen=True)
class Probe:
    """场景 → pipeline 节点名。顺序即优先级。"""

    scene: str
    node: str


@dataclass(frozen=True)
class Route:
    """路由结果。`target` 为 None 表示不 override，交给 JSON 的 `next`。"""

    target: str | None = None
    reason: str = ""

    @property
    def override(self) -> bool:
        return self.target is not None


@dataclass(frozen=True)
class RunParams:
    probes: tuple[Probe, ...] = ()
    plan: FarmPlan = field(default_factory=FarmPlan)
    stop_node: str = DEFAULT_STOP_NODE
    exchange_cancel_node: str = DEFAULT_EXCHANGE_CANCEL_NODE

    def node_of(self, scene: str) -> str | None:
        for probe in self.probes:
            if probe.scene == scene:
                return probe.node
        return None


def _as_mapping(raw: Any) -> dict[str, Any]:
    """`custom_action_param` 可能是 dict，也可能是 JSON 字符串（框架两种都见过）。"""

    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ParamError(f"custom_action_param 不是合法 JSON：{error}") from error
        if not isinstance(parsed, dict):
            raise ParamError("custom_action_param 必须是 JSON 对象")
        return parsed
    raise ParamError(f"custom_action_param 类型不支持：{type(raw).__name__}")


def _parse_probe(raw: Any) -> Probe:
    if isinstance(raw, dict):
        scene, node = raw.get("scene"), raw.get("node")
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        scene, node = raw
    else:
        raise ParamError(f"probe 项必须是 [scene, node] 或 {{scene,node}}：{raw!r}")
    if not isinstance(scene, str) or scene not in KNOWN_SCENES:
        raise ParamError(f"未知场景：{scene!r}（可用：{', '.join(sorted(KNOWN_SCENES))}）")
    if not isinstance(node, str) or not node:
        raise ParamError(f"probe 的 node 必须是非空字符串：{raw!r}")
    return Probe(scene=scene, node=node)


def load_params(raw: Any) -> RunParams:
    """解析 `custom_action_param`。"""

    data = _as_mapping(raw)
    probes = tuple(_parse_probe(item) for item in data.get("probe") or [])
    plan = FarmPlan(
        max_times=as_int(data, "max_times", 0, minimum=0),
        until_no_stamina=as_bool(data, "until_no_stamina", True),
        max_failures=as_int(data, "max_failures", 2, minimum=0),
        max_deaths=as_int(data, "max_deaths", 2, minimum=0),
        max_unknown=as_int(data, "max_unknown", 3, minimum=0),
        exchange_limit=as_int(data, "exchange_limit", 1, minimum=0),
    )
    return RunParams(
        probes=probes,
        plan=plan,
        stop_node=as_str(data, "stop_node", DEFAULT_STOP_NODE),
        exchange_cancel_node=as_str(data, "exchange_cancel_node", DEFAULT_EXCHANGE_CANCEL_NODE),
    )


def pick_scene(hits: Mapping[str, bool], params: RunParams) -> str | None:
    """按 `probe` 顺序返回第一个命中的场景。

    适配器不走这个函数（它必须**惰性**探测，命中即停，避免每次都跑满 12 次识别），
    但表驱动测试用它表达「同样的命中集合应选出同一个场景」。
    """

    for probe in params.probes:
        if hits.get(probe.scene):
            return probe.scene
    return None


def begin_round(state: FarmProgress) -> bool:
    """进入一轮刷本。返回 True 表示这是新的一轮。"""

    return state.begin_round()


def route(scene: str | None, state: FarmProgress, params: RunParams) -> Route:
    """当前场景 → 下一个节点（会就地更新 state）。"""

    state.last_scene = scene or ""

    if scene is None:
        state.record_unknown()
        if params.plan.max_unknown and state.unknown >= params.plan.max_unknown:
            state.in_round = False
            state.expect_battle = False
            state.stop_reason = STOP_UNKNOWN_LIMIT
            return Route(params.stop_node, STOP_UNKNOWN_LIMIT)
        return Route(None, "unknown")

    if scene == SCENE_CRYSTAL:
        # 水晶购买窗：只取消。pipeline 里没有「确认购买」节点，这里也不允许出现。
        state.crystal_seen = True
        state.stamina_insufficient = True
        state.in_round = False
        state.expect_battle = False
        state.stop_reason = STOP_STAMINA
        return Route(params.node_of(SCENE_CRYSTAL), STOP_STAMINA)

    if scene == SCENE_EXCHANGE:
        # exchange_limit=0 表示「一次也不换」（不是不限次数）：体力兑换会花道具，
        # 语义上必须偏保守，不能像 max_times 那样把 0 当「无限」。
        if state.exchange_used >= params.plan.exchange_limit:
            # 兑换额度用完了：关窗收尾，等魔女那一步补体力
            state.stamina_insufficient = True
            state.in_round = False
            state.stop_reason = STOP_STAMINA
            return Route(params.exchange_cancel_node, "exchange_limit")
        state.record_exchange()
        return Route(params.node_of(SCENE_EXCHANGE), "exchange")

    if scene == SCENE_DEAD:
        state.record_death()
        state.in_round = False
        state.expect_battle = False
        stop, reason = decide_stop(params.plan, state, False)
        if stop:
            # 死亡链路自己会走「救救我 → 返回 → 退出关卡 → 首页」，无需额外 override
            state.stop_reason = reason
        return Route(params.node_of(SCENE_DEAD), reason or "dead")

    if scene == SCENE_NEED_STAMINA:
        state.stamina_insufficient = True
        state.in_round = False
        state.expect_battle = False
        return Route(params.node_of(SCENE_NEED_STAMINA), "need_stamina")

    if scene == SCENE_RESULT:
        # 结算页本身由 FarmRound 处理，这里只负责把流程送过去
        return Route(params.node_of(SCENE_RESULT), "result")

    if scene in BATTLE_BOUND_SCENES:
        state.expect_battle = True
        state.in_round = True
        return Route(params.node_of(scene), "battle_bound")

    # stage / list / activity_tab / battle_tab：纯导航，不改计数
    return Route(params.node_of(scene), "navigate")


def after_battle(state: FarmProgress, params: RunParams) -> Route:
    """结算页判定：计一场，然后决定「再来一次」还是收尾。"""

    if state.expect_battle:
        state.battles += 1
        state.expect_battle = False

    state.in_round = False
    stamina_insufficient = state.consume_stamina_flag() or state.crystal_seen
    stop, reason = decide_stop(params.plan, state, stamina_insufficient)

    if stop:
        state.stop_reason = reason
        return Route(params.stop_node, reason)

    state.in_round = True
    return Route(None, "continue")


def describe(state: FarmProgress) -> dict[str, Any]:
    """给日志用的一行摘要（适配器不依赖它做判断）。"""

    return {
        "battles": state.battles,
        "deaths": state.deaths,
        "unknown": state.unknown,
        "rounds": state.rounds,
        "exchange_used": state.exchange_used,
        "stop_reason": state.stop_reason or "-",
    }


__all__ = [
    "BATTLE_BOUND_SCENES",
    "BATTLE_END_SCENES",
    "DEFAULT_EXCHANGE_CANCEL_NODE",
    "DEFAULT_STOP_NODE",
    "KNOWN_SCENES",
    "Probe",
    "Route",
    "RunParams",
    "SCENE_ACTIVITY_TAB",
    "SCENE_ASSIST",
    "SCENE_BATTLE_TAB",
    "SCENE_CRYSTAL",
    "SCENE_DEAD",
    "SCENE_EXCHANGE",
    "SCENE_LIST",
    "SCENE_NEED_STAMINA",
    "SCENE_READY",
    "SCENE_RESULT",
    "SCENE_STAGE",
    "SCENE_START",
    "STOP_DEATH_LIMIT",
    "STOP_STAMINA",
    "STOP_TARGET",
    "STOP_UNKNOWN_LIMIT",
    "after_battle",
    "begin_round",
    "describe",
    "load_params",
    "pick_scene",
    "route",
]
