"""SceneGuard：确认「当前确实在期望的界面」，否则改写流程。

为什么需要：pipeline 的 `next` 是「按顺序尝试识别」，一旦某个界面与预期
不同（弹窗、加载、公告），后续节点可能误点。SceneGuard 用**已有节点**做一次
显式校验，把「现在在哪」变成可断言、可回退的动作。

参数：

    {
        "node": "NavHomeFlag",      // 必填：用来判断场景的已有节点
        "expect": "Home",           // 可选：仅用于日志
        "on_mismatch": ["NavHome"], // 可选：不匹配时改写到这些节点
        "require": true             // 可选：不匹配时返回 False（默认 False）
    }
"""

from __future__ import annotations

import json

from common.log import get_logger
from common.params import ParamError, as_bool, as_node_list, as_str
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

REGISTERED = ["SceneGuard"]
ACTION_ID = "SceneGuard"

logger = get_logger("action.scene_guard")


def _parse(raw: str) -> dict:
    try:
        params = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise ParamError(f"custom_action_param 不是合法 JSON：{error}") from error
    if not isinstance(params, dict):
        raise ParamError("custom_action_param 必须是 JSON 对象")
    node = as_str(params, "node", "")
    if not node:
        raise ParamError("SceneGuard 缺少必填参数 `node`")
    return {
        "node": node,
        "expect": as_str(params, "expect", node),
        "on_mismatch": as_node_list(params, "on_mismatch"),
        "require": as_bool(params, "require", False),
    }


@AgentServer.custom_action(ACTION_ID)
class SceneGuard(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            options = _parse(argv.custom_action_param)
        except ParamError as error:
            logger.error("参数错误：%s", error)
            return False

        image = context.tasker.controller.cached_image
        if image is None or getattr(image, "size", 0) == 0:
            logger.warning("SceneGuard 没有可用截图，跳过校验（节点 %s）", argv.node_name)
            return True

        detail = context.run_recognition(options["node"], image)
        hit = bool(detail is not None and detail.hit)
        logger.info(
            "SceneGuard 期望=%s 判定节点=%s 命中=%s（节点 %s）",
            options["expect"],
            options["node"],
            hit,
            argv.node_name,
        )

        if hit:
            return True

        if options["on_mismatch"]:
            logger.warning("SceneGuard 不匹配，改写 next → %s", options["on_mismatch"])
            context.override_next(argv.node_name, options["on_mismatch"])
        return not options["require"]
