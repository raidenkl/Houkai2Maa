"""Agent 日志。

写两份：stdout（Client 会收集）+ `debug/agent.log`（复盘用）。
日志目录可用环境变量 `MAAHOUKAI2_DEBUG_DIR` 覆盖，便于 CI/回放时隔离。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_LOGGERS: dict[str, logging.Logger] = {}
_CONFIGURED = False


def debug_dir() -> Path:
    path = Path(os.environ.get("MAAHOUKAI2_DEBUG_DIR", "debug"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("houkai2")
    root.setLevel(logging.DEBUG)
    root.propagate = False

    formatter = logging.Formatter("[%(asctime)s][%(levelname)s][%(name)s] %(message)s", "%H:%M:%S")

    stream = logging.StreamHandler(stream=sys.stdout)
    stream.setFormatter(formatter)
    stream.setLevel(logging.INFO)
    root.addHandler(stream)

    try:
        file_handler = logging.FileHandler(debug_dir() / "agent.log", encoding="utf-8")
    except OSError:
        file_handler = None
    if file_handler is not None:
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    key = f"houkai2.{name}"
    if key not in _LOGGERS:
        _LOGGERS[key] = logging.getLogger(key)
    return _LOGGERS[key]
