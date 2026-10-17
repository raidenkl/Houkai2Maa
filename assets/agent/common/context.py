"""Agent 自身的运行上下文。

从 Client 注入的 `PI_*` 环境变量读取当前 UI、控制器与资源选择，
让 Agent 的日志目录、截图目录、设备策略都不必写死在代码里。

约定见 MaaFramework 文档 `3.3-ProjectInterfaceV2`（Agent 子进程环境变量，v2.5.0 起）。
未注入时（例如 MaaDebugger 直接启动）全部字段回落到安全默认值。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

DEFAULT_CLIENT = "unknown"
DEFAULT_RESOURCE = "官服"


def _json_env(name: str) -> dict[str, Any]:
    raw = os.environ.get(name)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


@dataclass
class ClientContext:
    """当前 Client / 资源快照（只读）。"""

    interface_version: str = ""
    client_name: str = DEFAULT_CLIENT
    client_version: str = ""
    client_language: str = "zh_cn"
    maafw_version: str = ""
    version: str = ""
    controller: dict[str, Any] = field(default_factory=dict)
    resource: dict[str, Any] = field(default_factory=dict)
    registered_actions: str = ""
    registered_recognitions: str = ""

    @property
    def controller_name(self) -> str:
        return str(self.controller.get("name", "")) or "unknown"

    @property
    def controller_type(self) -> str:
        return str(self.controller.get("type", "")) or "unknown"

    @property
    def resource_name(self) -> str:
        return str(self.resource.get("name", "")) or DEFAULT_RESOURCE

    @property
    def is_adb(self) -> bool:
        return self.controller_type.lower() == "adb"


def client_context() -> ClientContext:
    return ClientContext(
        interface_version=os.environ.get("PI_INTERFACE_VERSION", ""),
        client_name=os.environ.get("PI_CLIENT_NAME", DEFAULT_CLIENT),
        client_version=os.environ.get("PI_CLIENT_VERSION", ""),
        client_language=os.environ.get("PI_CLIENT_LANGUAGE", "zh_cn"),
        maafw_version=os.environ.get("PI_CLIENT_MAAFW_VERSION", ""),
        version=os.environ.get("PI_VERSION", ""),
        controller=_json_env("PI_CONTROLLER"),
        resource=_json_env("PI_RESOURCE"),
    )
