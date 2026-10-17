"""`agent/common/png.py` 的单元测试（不依赖 Pillow）。"""

from __future__ import annotations

import struct
import zlib

import numpy
from common.png import bgr_to_rgb, encode_png


def _ihdr(data: bytes) -> tuple[int, int]:
    # PNG 结构：8 字节签名 + IHDR 长度(4) + 类型(4) + 宽(4) + 高(4) + ...
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_encode_png_has_valid_signature_and_header() -> None:
    image = numpy.zeros((3, 5, 3), dtype=numpy.uint8)
    image[1, 2] = [10, 20, 30]
    data = encode_png(image)

    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert _ihdr(data) == (5, 3)
    assert data.endswith(b"IEND\xae\x42\x60\x82")


def test_encode_png_roundtrip_rows() -> None:
    image = numpy.array([[[1, 2, 3], [4, 5, 6]]], dtype=numpy.uint8)
    data = encode_png(image)

    # 找到 IDAT 并解压，第一字节应为 filter type 0
    start = data.index(b"IDAT")
    length = struct.unpack(">I", data[start - 4 : start])[0]
    raw = zlib.decompress(data[start + 4 : start + 4 + length])
    assert raw[0] == 0
    assert list(raw[1:7]) == [1, 2, 3, 4, 5, 6]


def test_encode_png_rejects_bad_shape() -> None:
    try:
        encode_png(numpy.zeros((4, 4), dtype=numpy.uint8))
    except ValueError:
        return
    raise AssertionError("应当拒绝二维数组")


def test_bgr_to_rgb_swaps_channels() -> None:
    bgr = numpy.array([[[3, 2, 1]]], dtype=numpy.uint8)
    rgb = bgr_to_rgb(bgr)
    assert rgb.tolist() == [[[1, 2, 3]]]
