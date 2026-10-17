"""`tools/dev/static_controller.py` 的单元测试。

只测「图片轮播顺序」这一纯逻辑：它决定离线回放的语义，错了会让 dryrun
给出误导性的结论（曾经因为不循环分支不推进索引，导致 StepB 永远看不到第二张图）。
"""

from __future__ import annotations

import numpy

import pytest

pytest.importorskip("maa", reason="需要 maafw 绑定（python tools/dev/setup.py）")

from static_controller import StaticImageController  # noqa: E402


def make_images(count: int) -> list[numpy.ndarray]:
    return [numpy.full((4, 4, 3), index, dtype=numpy.uint8) for index in range(count)]


def value(image: numpy.ndarray) -> int:
    return int(image[0, 0, 0])


def test_single_image_repeats() -> None:
    controller = StaticImageController(make_images(1))
    assert [value(controller.screencap()) for _ in range(3)] == [0, 0, 0]


def test_cycle_wraps_around() -> None:
    controller = StaticImageController(make_images(2), cycle=True)
    assert [value(controller.screencap()) for _ in range(5)] == [0, 1, 0, 1, 0]


def test_no_cycle_holds_last_image() -> None:
    controller = StaticImageController(make_images(2), cycle=False)
    assert [value(controller.screencap()) for _ in range(4)] == [0, 1, 1, 1]


def test_empty_images_rejected() -> None:
    with pytest.raises(ValueError):
        StaticImageController([])
