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

from common.log import get_logger
from common.params import ParamError, as_bool, as_int
from common.state import FarmPlan, FarmProgress, decide_stop
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

REGISTERED = ["FarmLoop", "FarmReset", "FarmFail", "FarmNote"]
LOOP_ACTION = "FarmLoop"
RESET_ACTION = "FarmReset"
FAIL_ACTION = "FarmFail"
NOTE_ACTION = "FarmNote"

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


def progress() -> FarmProgress:
    """供测试与调试读取当前进度。"""

    return _progress


@AgentServer.custom_action(LOOP_ACTION)
class FarmLoop(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            plan = _parse_plan(argv.custom_action_param)
        except ParamError as error:
            logger.error("参数错误：%s", error)
            return False

        _progress.record_battle()
        stop, reason = decide_stop(plan, _progress, _progress.consume_stamina_flag())
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


@AgentServer.custom_action(FAIL_ACTION)
class FarmFail(CustomAction):
    """记录一次失败，并在超过上限时结束循环。

    pipeline 用法（失败分支上挂本动作，正常重试仍由 JSON 的 next 决定）：

        "FarmBattleFailed": {
            "action": {
                "type": "Custom",
                "param": {
                    "custom_action": "FarmFail",
                    "custom_action_param": {"max_failures": 2, "on_give_up": []}
                }
            },
            "next": ["FarmRetry"]
        }

    * 未达上限：`next` 保持原样，流程按 JSON 继续重试；
    * 达到上限：`override_next(node, on_give_up)`，若 `on_give_up` 为空则结束该任务链。
    """

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            params = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError as error:
            logger.error("FarmFail 参数不是合法 JSON：%s", error)
            return False
        if not isinstance(params, dict):
            logger.error("FarmFail 参数必须是 JSON 对象")
            return False

        try:
            max_failures = as_int(params, "max_failures", 2, minimum=0)
            on_give_up = params.get("on_give_up") or []
            if not isinstance(on_give_up, list) or not all(isinstance(item, str) for item in on_give_up):
                raise ParamError("`on_give_up` 必须是字符串数组")
        except ParamError as error:
            logger.error("FarmFail 参数错误：%s", error)
            return False

        _progress.record_failure()
        plan = FarmPlan(max_failures=max_failures)
        stop, reason = decide_stop(plan, _progress)
        logger.info(
            "FarmFail 失败次数 %d/%s（节点 %s）→ %s",
            _progress.failures,
            max_failures or "不限",
            argv.node_name,
            f"放弃（{reason}）" if stop else "重试",
        )

        if stop:
            context.override_next(argv.node_name, list(on_give_up))
        return True


@AgentServer.custom_action(NOTE_ACTION)
class FarmNote(CustomAction):
    """给 loop 打「体力不足」标记。

    pipeline 用法（体力不足弹窗分支）：

        "FarmStaminaPopup": {
            "recognition": {"type": "Custom", "param": {"custom_recognition": "StaminaInsufficient"}},
            "action": {
                "type": "Custom",
                "param": {
                    "custom_action": "FarmNote",
                    "custom_action_param": {"stamina_insufficient": true}
                }
            },
            "next": ["FarmStaminaDecision"]
        }

    标记会在下一次 `FarmLoop` 判定时被消费（只生效一次），
    因此「打到没体力」与「中途误触」不会互相污染。
    """

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            params = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError as error:
            logger.error("FarmNote 参数不是合法 JSON：%s", error)
            return False
        if not isinstance(params, dict):
            logger.error("FarmNote 参数必须是 JSON 对象")
            return False

        try:
            flag = as_bool(params, "stamina_insufficient", True)
        except ParamError as error:
            logger.error("FarmNote 参数错误：%s", error)
            return False

        if flag:
            _progress.note_stamina_insufficient()
        logger.info("FarmNote 体力不足标记=%s（节点 %s）", flag, argv.node_name)
        return True
