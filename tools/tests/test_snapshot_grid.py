"""`tools/dev/snapshot.py` 的网格叠加逻辑测试（纯 numpy + 可选 Pillow）。"""

from __future__ import annotations

import numpy

import pytest

pytest.importorskip("maa", reason="需要 maafw 绑定（python tools/dev/setup.py）")

import snapshot  # noqa: E402

LINE = (0, 220, 255)


def test_grid_draws_lines_at_100px_intervals() -> None:
    image = numpy.zeros((720, 1280, 3), dtype=numpy.uint8)  # BGR
    canvas = snapshot.draw_grid(image, step=100)

    assert canvas.shape == (720, 1280, 3)
    for x in (0, 100, 400, 1200):
        assert tuple(canvas[10, x]) == LINE
    for y in (0, 100, 300, 700):
        assert tuple(canvas[y, 10]) == LINE


def test_grid_keeps_original_pixels_away_from_lines() -> None:
    image = numpy.zeros((720, 1280, 3), dtype=numpy.uint8)
    image[:, :] = (10, 20, 30)
    canvas = snapshot.draw_grid(image, step=100)
    assert tuple(canvas[55, 55]) == (30, 20, 10)  # BGR -> RGB 后原样
