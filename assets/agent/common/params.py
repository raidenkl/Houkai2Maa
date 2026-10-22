"""自定义件参数解析。

pipeline 传进来的 `custom_action_param` / `custom_recognition_param` 是任意 JSON，
这里统一做类型校验与默认值填充，避免每个自定义件重复写 try/except。

所有函数都是纯函数，便于单元测试。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


class ParamError(ValueError):
    """参数不合法。消息会直接写进 Agent 日志，便于定位 pipeline 写法问题。"""


def _get(params: dict[str, Any], key: str, default: Any) -> Any:
    value = params.get(key, default)
    return default if value is None else value


def load_param(raw: Any) -> dict[str, Any]:
    """把 `custom_*_param` 归一化成 dict。

    框架的类型声明是 `str`（JSON 字符串），但实际传参既可能是 str 也可能是已经
    解析好的对象（pipeline 里写 JSON 数组/对象时尤其如此）。统一在这里兜住，
    避免每个自定义件都对 dict 调 `json.loads` 然后抛 TypeError。
    """

    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ParamError(f"custom_*_param 不是合法 JSON：{error}") from error
        if not isinstance(parsed, dict):
            raise ParamError("custom_*_param 必须是 JSON 对象")
        return parsed
    raise ParamError(f"custom_*_param 类型不支持：{type(raw).__name__}")


def as_int(
    params: dict[str, Any],
    key: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    value = _get(params, key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            value = int(value.strip())
        else:
            raise ParamError(f"`{key}` 必须是整数，实际是 {value!r}")
    if minimum is not None and value < minimum:
        raise ParamError(f"`{key}` 不得小于 {minimum}，实际是 {value}")
    if maximum is not None and value > maximum:
        raise ParamError(f"`{key}` 不得大于 {maximum}，实际是 {value}")
    return value


def as_bool(params: dict[str, Any], key: str, default: bool) -> bool:
    value = _get(params, key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "y", "1"):
            return True
        if lowered in ("false", "no", "n", "0"):
            return False
    raise ParamError(f"`{key}` 必须是布尔值，实际是 {value!r}")


def as_str(params: dict[str, Any], key: str, default: str = "") -> str:
    value = _get(params, key, default)
    if isinstance(value, str):
        return value
    raise ParamError(f"`{key}` 必须是字符串，实际是 {value!r}")


def as_str_list(params: dict[str, Any], key: str, default: Iterable[str] = ()) -> list[str]:
    value = _get(params, key, list(default))
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ParamError(f"`{key}` 必须是字符串或字符串数组，实际是 {value!r}")


def as_node_list(params: dict[str, Any], key: str, default: Iterable[str] = ()) -> list[str]:
    """next 列表参数：允许 `"Node"`、`["A","B"]`，也允许 `["[JumpBack]A"]`。"""

    return as_str_list(params, key, default)
