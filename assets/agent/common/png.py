"""最小 PNG 编码（仅标准库）。

为什么要自己写：Agent 在用户机器上以子进程运行，不应额外依赖 Pillow。
截图（BGR numpy 数组）转 PNG 只需要 zlib + 结构体拼装，几十行即可，
也让 `pip install` 的负担为零。
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def encode_png(rgb: numpy.ndarray) -> bytes:
    """把 `uint8` 的 (H, W, 3) 数组编码成 PNG 字节流。"""

    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"需要 (H, W, 3) 的 RGB 数组，实际是 {rgb.shape}")
    height, width = rgb.shape[:2]
    array = numpy.ascontiguousarray(rgb, dtype=numpy.uint8)

    raw = bytearray()
    for row in array:
        raw.append(0)  # filter type 0 (None)
        raw.extend(row.tobytes())

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + _chunk(b"IEND", b"")
    )


def bgr_to_rgb(image: numpy.ndarray) -> numpy.ndarray:
    """MaaFramework 截图是 BGR，转成 RGB。"""

    return image[:, :, ::-1]


def write_png(path: str | Path, image: numpy.ndarray, *, bgr: bool = True) -> Path:
    """写 PNG 文件，返回实际路径。"""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rgb = bgr_to_rgb(image) if bgr and image.ndim == 3 and image.shape[2] == 3 else image
    target.write_bytes(encode_png(rgb))
    return target
