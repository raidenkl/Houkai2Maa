"""StaminaInsufficient：判定「体力不足」。

为什么值得一个自定义识别：单看一个模板或一句 OCR 都不够稳——体力不足
常见形态是「弹窗标题 + 提示文案 + 补充体力按钮」，需要组合判断；有时还要
把 OCR 出的数值与本次消耗比较。这些组合逻辑放 Agent 比在 JSON 里叠
`And` + `Or` 更清晰，也能写单测。

两种用法（参数二选一）：

1. 复用已有节点（推荐，识别逻辑仍在 JSON 里维护）：

    "custom_recognition_param": {"node": "CommonPopupStaminaInsufficient"}

2. 直接跑 OCR（临时/实验用）：

    "custom_recognition_param": {
        "expected": ["体力不足", "补充体力"],
        "roi": [340, 240, 600, 200]
    }

命中时返回识别框与 detail（含模式与实际文本），未命中返回 None。
"""

from __future__ import annotations

import json
from typing import Any

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_recognition import CustomRecognition
from maa.pipeline import JOCR, JRecognitionType

from common.log import get_logger
from common.params import ParamError, as_str, as_str_list

REGISTERED = ["StaminaInsufficient"]
RECOGNITION_ID = "StaminaInsufficient"

logger = get_logger("recognition.stamina")


def _parse(raw: str) -> dict[str, Any]:
    try:
        params = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise ParamError(f"custom_recognition_param 不是合法 JSON：{error}") from error
    if not isinstance(params, dict):
        raise ParamError("custom_recognition_param 必须是 JSON 对象")

    node = as_str(params, "node", "")
    expected = as_str_list(params, "expected")
    if not node and not expected:
        raise ParamError("StaminaInsufficient 需要 `node` 或 `expected` 之一")

    roi = params.get("roi")
    if roi is not None and (not isinstance(roi, list) or len(roi) != 4):
        raise ParamError("`roi` 必须是 [x, y, w, h]")

    return {
        "node": node,
        "expected": expected,
        "roi": roi,
        "threshold": float(params.get("threshold", 0.4)),
    }


def _text_of(detail) -> str:
    best = getattr(detail, "best_result", None)
    return str(getattr(best, "text", "") or "")


@AgentServer.custom_recognition(RECOGNITION_ID)
class StaminaInsufficient(CustomRecognition):
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

        if options["node"]:
            detail = context.run_recognition(options["node"], argv.image)
            mode = f"node:{options['node']}"
        else:
            param = JOCR(expected=options["expected"], threshold=options["threshold"])
            if options["roi"]:
                param.roi = tuple(int(value) for value in options["roi"])
            detail = context.run_recognition_direct(JRecognitionType.OCR, param, argv.image)
            mode = "ocr"

        if detail is None or not detail.hit:
            logger.debug("StaminaInsufficient 未命中（%s）", mode)
            return None

        box = detail.box
        text = _text_of(detail)
        logger.info("StaminaInsufficient 命中（%s）文本=%r 位置=%s", mode, text, box)
        return CustomRecognition.AnalyzeResult(
            box=None if box is None else (box.x, box.y, box.w, box.h),
            detail={"mode": mode, "text": text, "node": argv.node_name},
        )
