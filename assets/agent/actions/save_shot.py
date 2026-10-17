"""SaveShot：把当前画面落盘，便于复盘失败分支。

参数：

    {"tag": "farm-before-start", "max_files": 20}

截图保存在 `debug/shots/<tag>-<序号>.png`（目录可用 `MAAHOUKAI2_DEBUG_DIR` 覆盖），
`max_files` 限制同一 tag 的保留数量，避免刷本时把磁盘写满。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy
from common.log import debug_dir, get_logger
from common.params import ParamError, as_int, as_str
from common.png import write_png
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

REGISTERED = ["SaveShot"]
ACTION_ID = "SaveShot"

logger = get_logger("action.save_shot")

_SAFE_TAG = re.compile(r"[^A-Za-z0-9_.-]+")


def _parse(raw: str) -> tuple[str, int]:
    try:
        params = json.loads(raw) if raw else {}
    except json.JSONDecodeError as error:
        raise ParamError(f"custom_action_param 不是合法 JSON：{error}") from error
    if not isinstance(params, dict):
        raise ParamError("custom_action_param 必须是 JSON 对象")
    tag = _SAFE_TAG.sub("_", as_str(params, "tag", "shot")) or "shot"
    max_files = as_int(params, "max_files", 20, minimum=1, maximum=500)
    return tag, max_files


def _prune(paths: list[Path], max_files: int) -> None:
    for stale in sorted(paths)[:-max_files]:
        try:
            stale.unlink()
        except OSError:
            pass


@AgentServer.custom_action(ACTION_ID)
class SaveShot(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            tag, max_files = _parse(argv.custom_action_param)
        except ParamError as error:
            logger.error("参数错误：%s", error)
            return False

        image = context.tasker.controller.post_screencap().wait().get()
        if image is None:
            logger.error("SaveShot 截图失败（节点 %s）", argv.node_name)
            return False

        shots = debug_dir() / "shots"
        shots.mkdir(parents=True, exist_ok=True)
        existing = sorted(shots.glob(f"{tag}-*.png"))
        index = len(existing) + 1
        target = shots / f"{tag}-{index:03d}.png"

        try:
            write_png(target, numpy.asarray(image))
        except (OSError, ValueError) as error:
            logger.error("SaveShot 写文件失败：%s", error)
            return False

        _prune(sorted(shots.glob(f"{tag}-*.png")), max_files)
        logger.info("SaveShot 已保存 %s（节点 %s）", target, argv.node_name)
        return True
