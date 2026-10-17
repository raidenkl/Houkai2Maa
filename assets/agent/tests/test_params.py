"""`agent/common/params.py` 与部分自定义识别的纯逻辑测试。"""

from __future__ import annotations

import pytest
from common.params import ParamError, as_bool, as_int, as_node_list, as_str, as_str_list
from common.state import STATE_AVAILABLE, STATE_CLAIMED, classify_panel


def test_as_int_accepts_int_and_digit_string() -> None:
    assert as_int({"n": 3}, "n", 0) == 3
    assert as_int({"n": "5"}, "n", 0) == 5
    assert as_int({}, "n", 7) == 7


def test_as_int_rejects_bool_and_garbage() -> None:
    with pytest.raises(ParamError):
        as_int({"n": True}, "n", 0)
    with pytest.raises(ParamError):
        as_int({"n": "abc"}, "n", 0)


def test_as_int_bounds() -> None:
    with pytest.raises(ParamError):
        as_int({"n": -1}, "n", 0, minimum=0)
    with pytest.raises(ParamError):
        as_int({"n": 11}, "n", 0, maximum=10)


def test_as_bool_variants() -> None:
    assert as_bool({"b": "yes"}, "b", False) is True
    assert as_bool({"b": "No"}, "b", True) is False
    assert as_bool({}, "b", True) is True
    with pytest.raises(ParamError):
        as_bool({"b": "maybe"}, "b", False)


def test_as_str_and_lists() -> None:
    assert as_str({"s": "x"}, "s") == "x"
    assert as_str_list({"l": "A"}, "l") == ["A"]
    assert as_str_list({"l": ["A", "B"]}, "l") == ["A", "B"]
    assert as_node_list({"n": ["[JumpBack]NavHome"]}, "n") == ["[JumpBack]NavHome"]
    with pytest.raises(ParamError):
        as_str_list({"l": [1]}, "l")


def test_panel_state_classify() -> None:
    assert classify_panel(True, False) == STATE_CLAIMED
    assert classify_panel(False, True) == STATE_AVAILABLE
    assert classify_panel(True, True) is None
    assert classify_panel(False, False) is None
