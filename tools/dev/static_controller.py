#!/usr/bin/env python3
"""把「一组静态图片」伪装成控制器，用于完全离线的流程/识别测试。

MaaFramework 自带的 DbgController 依赖 `MaaDbgControlUnit` 插件，
pip 分发的 maafw 里不一定带；`CustomController` 是纯 Python 抽象类，
这里用最小实现替代：

* `screencap()` 返回下一张图（多张时循环，便于测试「点击后界面变化」）；
* 所有点击/滑动/按键都返回成功，不做真实操作（不会碰设备）。

用途：

* `tools/dev/snapshot.py --image`：对本地截图跑 OCR；
* `tools/dev/dryrun.py`：用一组截图跑一条 pipeline，验证流程分支。
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy
from maa.controller import CustomController


class StaticImageController(CustomController):
    def __init__(self, images: Sequence[numpy.ndarray], cycle: bool = True) -> None:
        # 先完成父类初始化再校验参数：否则构造失败的对象在 GC 时
        # 会因缺少 `_handle` 触发 unraisable AttributeError。
        super().__init__()
        if not images:
            raise ValueError("StaticImageController 至少需要一张图片")
        self._images = [numpy.ascontiguousarray(image) for image in images]
        self._cycle = cycle
        self._index = 0

    # --- 生命周期 ---
    def connect(self) -> bool:
        return True

    def request_uuid(self) -> str:
        return "static-image"

    def start_app(self, intent: str) -> bool:
        return True

    def stop_app(self, intent: str) -> bool:
        return True

    # --- 截图 ---
    def screencap(self) -> numpy.ndarray:
        image = self._images[self._index]
        if len(self._images) > 1:
            if self._cycle:
                self._index = (self._index + 1) % len(self._images)
            else:
                self._index = min(self._index + 1, len(self._images) - 1)
        return image

    # --- 输入（全部空实现，保证不操作真实设备）---
    def click(self, x: int, y: int) -> bool:
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> bool:
        return True

    def touch_down(self, contact: int, x: int, y: int, pressure: int) -> bool:
        return True

    def touch_move(self, contact: int, x: int, y: int, pressure: int) -> bool:
        return True

    def touch_up(self, contact: int) -> bool:
        return True

    def click_key(self, keycode: int) -> bool:
        return True

    def input_text(self, text: str) -> bool:
        return True

    def key_down(self, keycode: int) -> bool:
        return True

    def key_up(self, keycode: int) -> bool:
        return True


def load_images(paths: Sequence[str]) -> list[numpy.ndarray]:
    """读取 PNG/JPG 为 BGR 数组（MaaFW 约定）。"""

    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("需要 Pillow 读取图片：python tools/dev/setup.py") from None

    images: list[numpy.ndarray] = []
    for path in paths:
        with Image.open(path) as source:
            rgb = numpy.asarray(source.convert("RGB"))
        images.append(rgb[:, :, ::-1].copy())
    return images
