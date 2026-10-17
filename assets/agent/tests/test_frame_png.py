"""`read_png_size` 的测试。"""

from __future__ import annotations

from pathlib import Path

from common.frame import read_png_size

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_reads_fixture_png_size() -> None:
    assert read_png_size(REPO_ROOT / "tests/fixtures/smoke/screens/01-home.png") == (1280, 720)


def test_non_png_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "fake.png"
    path.write_bytes(b"not a png at all, definitely long enough")
    assert read_png_size(path) is None


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_png_size(tmp_path / "nope.png") is None
