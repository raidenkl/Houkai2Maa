"""自定义识别集合。

同样按 ID 注册，`tools/lint/pipeline_lint.py` 会校验 pipeline 中的
`custom_recognition` 是否真实存在。
"""

from __future__ import annotations

from . import panel_state, stamina

MODULES = (stamina, panel_state)


def register_all() -> list[str]:
    names: list[str] = []
    for module in MODULES:
        names.extend(getattr(module, "REGISTERED", []))
    return names
