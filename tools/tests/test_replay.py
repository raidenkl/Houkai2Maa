"""`tools/dev/replay.py` 的用例加载与跳过语义测试（不需要设备/录制）。"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

pytest.importorskip("maa", reason="需要 maafw 绑定（python tools/dev/setup.py）")

import replay  # noqa: E402

def write_case(directory: Path, name: str, recording: str) -> Path:
    path = directory / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "case": name,
                "entry": "SmokeEntry",
                "recording": recording,
                "expect": {"completed": True, "hit_nodes": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def test_missing_recording_is_skipped_by_default(tmp_path: Path) -> None:
    write_case(tmp_path, "ghost", "tests/recordings/ghost/ghost.jsonl")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = replay.main(["--all", "--cases-dir", str(tmp_path)])

    assert code == 0
    assert "[SKIP]" in buffer.getvalue()


def test_missing_recording_fails_with_require(tmp_path: Path) -> None:
    write_case(tmp_path, "ghost", "tests/recordings/ghost/ghost.jsonl")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = replay.main(["--all", "--cases-dir", str(tmp_path), "--require"])

    assert code == 1
    assert "[FAIL]" in buffer.getvalue()


def test_unknown_case_name_reports_failure(tmp_path: Path) -> None:
    write_case(tmp_path, "known", "tests/recordings/known/known.jsonl")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = replay.main(["--case", "nope", "--cases-dir", str(tmp_path)])

    assert code == 1
    assert "没有名为 nope 的用例" in buffer.getvalue()


def test_replay_engine_flags_missing_expected_node(tmp_path: Path) -> None:
    """录制可用但期望节点对不上时，回放必须失败（防止断言形同虚设）。"""

    case = {
        "case": "wrong-expect",
        "entry": "SmokeEntry",
        "resource": "tests/fixtures/smoke/resource",
        "recording": "tests/fixtures/replay/smoke/smoke.jsonl",
        "expect": {"completed": True, "hit_nodes": ["SmokeStepA", "NoSuchNode"]},
    }
    (tmp_path / "wrong-expect.json").write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = replay.main(["--all", "--cases-dir", str(tmp_path)])

    assert code == 1
    assert "[FAIL]" in buffer.getvalue()
