"""FarmLoop / FarmReset：刷本循环计数与收敛。

放在 Agent 的原因：需要跨节点计数（每次回到结算界面 +1），并根据
「次数达标 / 体力耗尽 / 失败次数」动态改写 `next`。这类逻辑用纯 JSON
只能靠 `max_hit` 硬编码，无法叠加 option 与失败重试。

pipeline 用法（示意）：

    "FarmBattleFinished": {
        "action": {
            "type": "Custom",
            "param": {
                "custom_action": "FarmLoop",
                "custom_action_param": {"max_times": 0, "until_no_stamina": true}
            }
        },
        "next": ["FarmAgain"]
    }

达到停止条件时，本动作会把当前节点的 `next` 清空，任务链自然结束。
"""

from __future__ import annotations

import json

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from common.log import get_logger
from common.params import ParamError, as_bool, as_int
from common.state import FarmPlan, FarmProgress, decide_stop

REGISTERED = ["FarmLoop", "FarmReset"]
LOOP_ACTION = "FarmLoop"
RESET_ACTION = "FarmReset"

logger = get_logger("action.farm_loop")

_progress = FarmProgress()


def _parse_plan(raw: str) -> FarmPlan:
    try:
        params = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise ParamError(f"custom_action_param 不是合法 JSON：{error}") from error
    if not isinstance(params, dict):
        raise ParamError("custom_action_param 必须是 JSON 对象")
    return FarmPlan(
        max_times=as_int(params, "max_times", 0, minimum=0),
        until_no_stamina=as_bool(params, "until_no_stamina", False),
        max_failures=as_int(params, "max_failures", 2, minimum=0),
    )


def reset() -> None:
    _progress.reset()


@AgentServer.custom_action(LOOP_ACTION)
class FarmLoop(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            plan = _parse_plan(argv.custom_action_param)
        except ParamError as error:
            logger.error("参数错误：%s", error)
            return False

        _progress.record_battle()
        stop, reason = decide_stop(plan, _progress)
        logger.info(
            "FarmLoop 第 %d 次战斗结束（失败 %d，上限 %s，刷到没体力=%s）→ %s",
            _progress.battles,
            _progress.failures,
            plan.max_times or "不限",
            plan.until_no_stamina,
            f"停止（{reason}）" if stop else "继续",
        )

        if stop:
            context.override_next(argv.node_name, [])
        return True


@AgentServer.custom_action(RESET_ACTION)
class FarmReset(CustomAction):
    """任务入口处调用，确保每次运行从 0 开始计数。"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        reset()
        logger.info("FarmReset：循环计数已清零（节点 %s）", argv.node_name)
        return True
