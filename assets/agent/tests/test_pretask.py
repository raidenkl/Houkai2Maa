"""预任务 `device_prepare.py` 的离线（--image）行为测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from pretask.device_prepare import main

REPO_ROOT = Path(__file__).resolve().parents[3]
BASE_SCREEN = REPO_ROOT / "tests" / "fixtures" / "smoke" / "screens" / "01-home.png"


def test_base_frame_passes() -> None:
    assert main(["--image", str(BASE_SCREEN)]) == 0


def test_non_base_aspect_fails(tmp_path: Path) -> None:
    numpy = pytest.importorskip("numpy")
    from common.png import write_png

    wide = tmp_path / "wide.png"
    write_png(wide, numpy.zeros((720, 1600, 3), dtype=numpy.uint8))
    assert main(["--image", str(wide)]) == 1


def test_missing_image_fails(tmp_path: Path) -> None:
    assert main(["--image", str(tmp_path / "nope.png")]) == 1
