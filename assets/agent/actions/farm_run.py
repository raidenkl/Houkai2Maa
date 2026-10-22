"""FarmReset / FarmRoute / FarmRound：活动清体力（ActivityFarm）的 Agent 适配层。

分工（重要）：
* `common/farm_flow.py` 负责所有判断（纯函数、有单测）；
* 本模块只做「探场景 → 问决策 → override_next」，每个类不超过十几行。

三条硬约束：

1. **全函数降级**：参数错误、识别异常、`override_next` 失败一律记日志并 `return True`
   且**不改写 next**。这样 Agent 挂了就等于回到纯 JSON 的候选顺序，刷本任务不会直接死。
2. **惰性探测**：按 `probe` 顺序逐个跑识别，命中即停，成本与改造前的候选扫描一致
   （改造前 Entry 有 14 个候选，框架也是依次试）。
3. **未知场景留证据**：连续识别不到任何已知界面时落盘一帧到 `debug/shots/unknown-*.png`，
   这是真机排障唯一的现场。

参数（`custom_action_param`）见 `common/farm_flow.RunParams`：

    {
        "max_times": 20,              // 场次安全网（0=不限）
        "until_no_stamina": true,     // 刷到没体力为止
        "max_deaths": 2, "max_unknown": 3, "exchange_limit": 1,
        "stop_node": "ActivityFarmHome",
        "exchange_cancel_node": "ActivityFarmExchangeCancel",
        "probe": [["crystal", "ActivityFarmCrystalPopup"], ...]
    }
"""

from __future__ import annotations

import numpy
from common.farm_flow import (
    RunParams,
    after_battle,
    begin_round,
    describe,
    load_params,
    route,
)
from common.log import debug_dir, get_logger
from common.params import ParamError, load_param
from common.png import write_png
from common.state import FarmProgress
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

REGISTERED = ["FarmReset", "FarmRoute", "FarmRound"]

logger = get_logger("action.farm_run")

#: 本模块是刷本状态的唯一所有者（进程级单例）。`FarmReset` 在任务入口清零。
_state = FarmProgress()

#: 未知场景最多留几张图，避免刷本时把 debug/shots 撑爆
MAX_UNKNOWN_SHOTS = 5


def _dump_unknown(context: Context) -> None:
    """未知场景落盘一帧（失败不影响主流程）。"""

    try:
        shots = debug_dir() / "shots"
        shots.mkdir(parents=True, exist_ok=True)
        existing = sorted(shots.glob("unknown-*.png"))
        if len(existing) >= MAX_UNKNOWN_SHOTS:
            return
        image = context.tasker.controller.cached_image
        if image is None:
            return
        write_png(shots / f"unknown-{len(existing) + 1:03d}.png", numpy.asarray(image))
        logger.warning("未知场景已落盘：%s", shots)
    except Exception:  # 落盘纯属附加信息，绝不因为它让流程失败
        logger.exception("未知场景落盘失败")


def _hit(context: Context, node: str, image: numpy.ndarray) -> bool:
    detail = context.run_recognition(node, image)
    return bool(detail and detail.hit)


def _probe(context: Context, params: RunParams) -> str | None:
    """按 probe 顺序惰性探测，命中即返回场景名。"""

    image = context.tasker.controller.cached_image
    if image is None:
        logger.warning("FarmRoute 取不到截图，按未知场景处理")
        return None
    for probe in params.probes:
        try:
            if _hit(context, probe.node, image):
                return probe.scene
        except Exception:
            logger.exception("探测节点 %s 异常，跳过", probe.node)
    return None


@AgentServer.custom_action("FarmReset")
class FarmReset(CustomAction):
    """任务入口清零。放在 `ActivityFarmBegin`，第二轮刻意不经过它。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            params = load_params(load_param(argv.custom_action_param))
        except ParamError as error:
            # 参数写错也要清零：否则上一轮的计数会污染这一轮
            logger.error("FarmReset 参数错误（仍会清零）：%s", error)
            _state.reset()
            return True

        _state.reset()
        logger.info("FarmReset：计数已清零，计划 %s", params.plan)
        return True


@AgentServer.custom_action("FarmRoute")
class FarmRoute(CustomAction):
    """Entry 的场景分发：取代原来 14 个候选的隐式状态机。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            params = load_params(load_param(argv.custom_action_param))
        except ParamError as error:
            logger.error("FarmRoute 参数错误，落回 JSON 顺序：%s", error)
            return True

        try:
            is_new_round = begin_round(_state)
            if is_new_round:
                logger.info("FarmRoute：进入第 %d 轮", _state.rounds)

            scene = _probe(context, params)
            result = route(scene, _state, params)

            logger.info(
                "FarmRoute scene=%s → %s（%s）%s",
                scene or "unknown",
                result.target or "JSON 顺序",
                result.reason or "-",
                describe(_state),
            )
            if scene is None:
                _dump_unknown(context)
            if result.override:
                return bool(context.override_next(argv.node_name, [result.target]))
            return True
        except Exception:
            # 全函数降级：不 override，流程回到 JSON 的候选顺序
            logger.exception("FarmRoute 异常，落回 JSON 候选顺序")
            return True


@AgentServer.custom_action("FarmRound")
class FarmRound(CustomAction):
    """结算页收敛：计一场，决定「再来一次」还是回首页收尾。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            params = load_params(load_param(argv.custom_action_param))
        except ParamError as error:
            logger.error("FarmRound 参数错误，落回 JSON 顺序：%s", error)
            return True

        try:
            result = after_battle(_state, params)
            logger.info(
                "FarmRound → %s（%s）%s",
                result.target or "继续下一场",
                result.reason or "-",
                describe(_state),
            )
            if result.override:
                return bool(context.override_next(argv.node_name, [result.target]))
            return True
        except Exception:
            logger.exception("FarmRound 异常，落回 JSON 候选顺序")
            return True
