"""版本号与 Git tag 的一致性判断（纯函数）。"""

from __future__ import annotations

import re

VERSION_RE = re.compile(r"^(?P<core>\d+\.\d+\.\d+)(?P<suffix>[-+][0-9A-Za-z.\-+]*)?$")


def normalize(text: str) -> str:
    """去掉 `v` 前缀与首尾空白。"""

    value = text.strip()
    if value[:1] in ("v", "V"):
        value = value[1:]
    return value


def parse(text: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.match(normalize(text))
    if not match:
        return None
    core = match.group("core")
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch


def is_valid(text: str) -> bool:
    return parse(text) is not None


def matches_tag(interface_version: str, tag: str) -> bool:
    """`interface.json` 的 version 与发布 tag 是否一致。

    CI 会 git describe 出 `v1.2.3` 或 `v1.2.3-ci.abc` 这样的 tag；
    interface 里写 `1.2.3` 或 `1.2.3-ci.abc`（有无 `v` 都行）视为一致。
    """

    return normalize(interface_version) == normalize(tag)
