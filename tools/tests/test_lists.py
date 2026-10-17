"""`tools/shared/lists.py` 的单元测试（回放断言语义）。"""

from __future__ import annotations

from shared.lists import is_subsequence


def test_empty_expected_always_matches() -> None:
    assert is_subsequence([], ["A", "B"]) is True


def test_order_matters() -> None:
    assert is_subsequence(["A", "B"], ["A", "X", "B"]) is True
    assert is_subsequence(["B", "A"], ["A", "X", "B"]) is False


def test_repeated_items() -> None:
    assert is_subsequence(["A", "A"], ["A", "B", "A"]) is True
    assert is_subsequence(["A", "A", "A"], ["A", "B", "A"]) is False


def test_missing_item() -> None:
    assert is_subsequence(["A", "C"], ["A", "B"]) is False
