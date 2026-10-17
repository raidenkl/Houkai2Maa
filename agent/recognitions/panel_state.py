"""PanelState：判定某个面板的领取状态（已领取 / 可领取 / 未识别）。

日常任务的共性问题是「要不要点」：签到、邮件、社团福利都有「今天已经领过」
的状态，盲目点击会浪费时间，甚至在二次点击后打开别的界面。

参数：

    {
        "claimed_node": "DailySignInClaimed",     // 命中 → 已领取
        "available_node": "DailySignInButton",    // 命中 → 可领取
        "panel": "signin"                          // 仅用于日志
    }

返回：
* 未识别到任何状态 → None（交给 pipeline 走 `on_error`）；
* 命中 → AnalyzeResult(box=..., detail={"state": "claimed"|"available", ...})。
"""

from __future__ import annotations

import json
from typing import Any

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition

from common.log import get_logger
from common.params import ParamError, as_str
from common.state import STATE_AVAILABLE, STATE_CLAIMED, classify_panel

REGISTERED = ["PanelState"]
RECOGNITION_ID = "PanelState"

logger = get_logger("recognition.panel_state")

def _parse(raw: str) -> dict[str, Any]:
    try:
        params = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise ParamError(f"custom_recognition_param 不是合法 JSON：{error}") from error
    if not isinstance(params, dict):
        raise ParamError("custom_recognition_param 必须是 JSON 对象")
    claimed = as_str(params, "claimed_node", "")
    available = as_str(params, "available_node", "")
    if not claimed and not available:
        raise ParamError("PanelState 至少需要 `claimed_node` 或 `available_node`")
    return {
        "claimed_node": claimed,
        "available_node": available,
        "panel": as_str(params, "panel", "unknown"),
    }


@AgentServer.custom_recognition(RECOGNITION_ID)
class PanelState(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult | None:
        try:
            options = _parse(argv.custom_recognition_param)
        except ParamError as error:
            logger.error("参数错误：%s", error)
            return None

        claimed_detail = (
            context.run_recognition(options["claimed_node"], argv.image) if options["claimed_node"] else None
        )
        available_detail = (
            context.run_recognition(options["available_node"], argv.image) if options["available_node"] else None
        )

        state = classify_panel(
            bool(claimed_detail is not None and claimed_detail.hit),
            bool(available_detail is not None and available_detail.hit),
        )
        logger.info("PanelState panel=%s state=%s", options["panel"], state or "unknown")

        if state is None:
            return None

        source = claimed_detail if state == STATE_CLAIMED else available_detail
        box = getattr(source, "box", None)
        return CustomRecognition.AnalyzeResult(
            box=None if box is None else (box.x, box.y, box.w, box.h),
            detail={"panel": options["panel"], "state": state, "node": argv.node_name},
        )
