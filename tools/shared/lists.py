"""列表小工具（纯标准库）。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def is_subsequence(expected: Sequence[str], actual: Iterable[str]) -> bool:
    """判断 `expected` 是否为 `actual` 的**有序子序列**。

    回放用例用它断言「这些节点按顺序出现过」，允许中间夹着其它节点
    （弹窗兜底、加载等待等），比全等断言更贴近真实流程。
    """

    iterator = iter(actual)
    return all(item in iterator for item in expected)
