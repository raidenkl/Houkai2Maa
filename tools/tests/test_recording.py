"""`tools/shared/recording.py` 的录制校验测试（使用仓库内回放夹具）。"""

from __future__ import annotations

import json
from pathlib import Path

from shared.recording import validate_recording

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "tests" / "fixtures" / "replay" / "smoke" / "smoke.jsonl"


def test_smoke_recording_is_valid() -> None:
    summary = validate_recording(SMOKE)
    assert summary.ok, summary.render()
    assert summary.resolution == (1280, 720)
    assert summary.by_type["connect"] == 1
    assert summary.by_type["screencap"] == 2
    assert summary.by_type["click"] == 2
    assert len(summary.screenshots) == 2


def test_missing_recording_reports_error(tmp_path: Path) -> None:
    summary = validate_recording(tmp_path / "nope.jsonl")
    assert summary.ok is False
    assert any("不存在" in item for item in summary.errors)


def test_missing_screenshot_detected(tmp_path: Path) -> None:
    recording = tmp_path / "case.jsonl"
    recording.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                {"type": "connect", "uuid": "x", "version": "v", "width": 1280, "height": 720,
                 "success": True, "cost": 0, "timestamp": 1},
                {"type": "screencap", "path": "missing.png", "success": True, "cost": 0, "timestamp": 2},
            ]
        ),
        encoding="utf-8",
    )
    summary = validate_recording(recording)
    assert summary.ok is False
    assert len(summary.missing_screenshots) == 1


def test_bad_line_and_missing_connect_reported(tmp_path: Path) -> None:
    recording = tmp_path / "bad.jsonl"
    recording.write_text('{"type": "click", "x": 1, "y": 2}\nnot-json\n', encoding="utf-8")
    summary = validate_recording(recording)
    assert summary.ok is False
    assert any("不是合法 JSON" in item for item in summary.errors)
    assert any("connect" in item for item in summary.errors)


def test_non_base_resolution_flagged(tmp_path: Path) -> None:
    recording = tmp_path / "hd.jsonl"
    recording.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                {"type": "connect", "uuid": "x", "version": "v", "width": 1920, "height": 1080,
                 "success": True, "cost": 0, "timestamp": 1},
                {"type": "screencap", "path": "a.png", "success": True, "cost": 0, "timestamp": 2},
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    summary = validate_recording(recording)
    assert summary.resolution_matches_base is False
    assert "分辨率不是 1280x720" in summary.render()
