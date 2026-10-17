"""`agent/common/frame.py` 的尺寸判定测试。"""

from __future__ import annotations

from common.frame import evaluate_frame


def test_base_size_passes() -> None:
    check = evaluate_frame(1280, 720)
    assert check.ok
    assert "符合基准" in check.message


def test_portrait_rejected() -> None:
    check = evaluate_frame(720, 1280)
    assert check.ok is False
    assert "竖屏" in check.message


def test_wide_aspect_rejected() -> None:
    check = evaluate_frame(1600, 720)
    assert check.ok is False
    assert "16:9" in check.message


def test_16_9_non_720p_rejected_with_hint() -> None:
    check = evaluate_frame(1920, 1080)
    assert check.ok is False
    assert "1280x720" in check.message


def test_odd_size_rejected() -> None:
    check = evaluate_frame(1024, 600)
    assert check.ok is False
    assert "1280x720" in check.message


def test_invalid_size_rejected() -> None:
    check = evaluate_frame(0, 0)
    assert check.ok is False


def test_frame_check_is_truthy_for_bool_use() -> None:
    assert bool(evaluate_frame(1280, 720)) is True
    assert bool(evaluate_frame(1920, 1080)) is False
