"""`tools/dev/crop.py` 的坐标换算测试（非 720p 截图自动缩放）。"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

pytest.importorskip("PIL", reason="需要 Pillow 解码截图")

import crop  # noqa: E402


def make_image(path: Path, size: tuple[int, int]) -> None:
    from PIL import Image

    Image.new("RGB", size, (30, 40, 60)).save(path)


def run_cli(args: list[str]) -> tuple[int, dict]:
    buffer = io.StringIO()
    errors = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(errors):
        code = crop.main(args)
    return code, json.loads(buffer.getvalue())


def test_720p_input_is_not_scaled(tmp_path: Path) -> None:
    screen = tmp_path / "screen.png"
    make_image(screen, (1280, 720))
    code, payload = run_cli(
        ["--screen", str(screen), "--box", "100,200,120,60", "--node", "Demo", "--dry-run", "--json", "--pad", "10"]
    )
    assert code == 0
    assert payload["screen_size"] == [1280, 720]
    assert payload["box_input"] == [100, 200, 120, 60]
    assert payload["template_box"] == [100, 200, 120, 60]
    assert payload["roi"] == [90, 190, 140, 80]


def test_1080p_input_is_scaled_and_box_mapped(tmp_path: Path) -> None:
    screen = tmp_path / "screen-1080p.png"
    make_image(screen, (1920, 1080))
    code, payload = run_cli(
        ["--screen", str(screen), "--box", "1470,840,180,90", "--node", "Demo", "--dry-run", "--json", "--pad", "20"]
    )
    assert code == 0
    assert payload["screen_size"] == [1920, 1080]
    assert payload["box_input"] == [1470, 840, 180, 90]
    assert payload["template_box"] == [980, 560, 120, 60]
    assert payload["roi"] == [960, 540, 160, 100]


def test_non_16_9_rejected(tmp_path: Path) -> None:
    screen = tmp_path / "wide.png"
    make_image(screen, (1600, 720))
    with pytest.raises(SystemExit) as excinfo:
        crop.main(["--screen", str(screen), "--box", "10,10,20,20", "--dry-run"])
    assert "16:9" in str(excinfo.value)


def test_no_scale_rejects_non_720p(tmp_path: Path) -> None:
    screen = tmp_path / "screen-1440p.png"
    make_image(screen, (2560, 1440))
    with pytest.raises(SystemExit) as excinfo:
        crop.main(["--screen", str(screen), "--box", "10,10,20,20", "--dry-run", "--no-scale"])
    assert "1280x720" in str(excinfo.value)


def test_template_saved_with_expected_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    screen = tmp_path / "screen-1080p.png"
    make_image(screen, (1920, 1080))
    image_dir = tmp_path / "image"
    image_dir.mkdir()
    monkeypatch.setattr(crop, "IMAGE_DIR", image_dir)

    code, payload = run_cli(
        ["--screen", str(screen), "--box", "1470,840,180,90", "--out", "demo/btn.png", "--node", "Demo", "--json"]
    )
    assert code == 0
    from PIL import Image

    saved = image_dir / "demo" / "btn.png"
    assert saved.is_file()
    assert Image.open(saved).size == (120, 60)
    assert payload["saved"].endswith("demo/btn.png")
