"""截图尺寸校验（纯函数，无 MaaFramework 依赖）。

项目的所有坐标、ROI、模板都以 **1280x720（16:9）** 为基准
（`interface.json` 的 `display_short_side = 720`）。只要实际截图尺寸不是这个值，
识别就会整体偏移，且很难从日志里看出来。所以：

* `pretask` 在启动 Controller 前做一次体检；
* `record.py`/`snapshot.py` 采集时也会打印告警。

注意：`display_short_side=720` 只固定**短边**。20:9 的手机会得到 1600x720，
同样与 1280x720 的模板不兼容，因此这里对宽高都做严格判断。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

BASE_WIDTH = 1280
BASE_HEIGHT = 720


@dataclass(frozen=True)
class FrameCheck:
    ok: bool
    message: str

    def __bool__(self) -> bool:  # 允许直接 if check:
        return self.ok


def evaluate_frame(width: int, height: int) -> FrameCheck:
    """判断截图尺寸是否符合 720p 基准。"""

    if width <= 0 or height <= 0:
        return FrameCheck(False, f"截图尺寸非法：{width}x{height}")

    if (width, height) == (BASE_WIDTH, BASE_HEIGHT):
        return FrameCheck(True, "截图尺寸 1280x720，符合基准")

    if height > width:
        return FrameCheck(
            False,
            f"截图是竖屏 {width}x{height}；游戏需要横屏，请把模拟器/设备转为横屏并设 1280x720",
        )

    if height == BASE_HEIGHT:
        return FrameCheck(
            False,
            f"截图是 {width}x{height}（短边 720 但比例为 {width}:{height}）；"
            "模板按 16:9 裁剪，非 16:9 会整体错位。请把分辨率改为 1280x720（16:9）",
        )

    ratio = width / height
    if abs(ratio - 16 / 9) < 0.02 and height != BASE_HEIGHT:
        return FrameCheck(
            False,
            f"截图是 {width}x{height}，比例正确但不是 720p；"
            "建议直接用 1280x720（缩放后字体会更清晰、识别更快）",
        )

    return FrameCheck(
        False,
        f"截图是 {width}x{height}，既不是 16:9 也不是 720p；请改为 1280x720",
    )


def read_png_size(path: str | Path) -> tuple[int, int] | None:
    """读取 PNG 尺寸（仅标准库）。非 PNG 或读取失败返回 None。"""

    try:
        header = Path(path).read_bytes()[:24]
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)
