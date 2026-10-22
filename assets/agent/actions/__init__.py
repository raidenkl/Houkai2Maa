"""自定义动作集合。

每个模块用 `@AgentServer.custom_action("<ID>")` 注册，ID 与 pipeline 中
`action.param.custom_action` 一一对应；`tools/lint/pipeline_lint.py` 会检查
「pipeline 里用到的 ID 是否真的注册过」，因此改名必须两边一起改。
"""

from __future__ import annotations

from . import farm_loop, farm_run, save_shot, scene_guard

MODULES = (farm_loop, farm_run, save_shot, scene_guard)


def register_all() -> list[str]:
    """导入即注册（装饰器在 import 时生效），返回已注册的 ID 列表。"""

    names: list[str] = []
    for module in MODULES:
        names.extend(getattr(module, "REGISTERED", []))
    return names
