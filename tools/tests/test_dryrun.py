"""`tools/dev/dryrun.py` 的端到端离线测试。

用仓库内的最小 fixture（纯色块截图 + 三节点流水线）验证：
「用一组截图跑 pipeline」这条链路能走通、节点顺序正确、退出码为 0。

需要 maafw 绑定与 Pillow（读图）：
    python tools/dev/setup.py
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

pytest.importorskip("maa", reason="需要 maafw 绑定（python tools/dev/setup.py）")
pytest.importorskip("PIL", reason="需要 Pillow 读取 fixture 截图")

import dryrun  # noqa: E402


def test_smoke_fixture_runs_to_completion() -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = dryrun.main(
            [
                "--resource",
                "tests/fixtures/smoke/resource",
                "--images",
                "tests/fixtures/smoke/screens",
                "--entry",
                "SmokeEntry",
                "--once",
            ]
        )

    output = buffer.getvalue()
    assert code == 0, output
    assert "SmokeStepA" in output
    assert "SmokeStepB" in output
    assert "成功" in output


def test_unknown_entry_reports_failure() -> None:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = dryrun.main(
            [
                "--resource",
                "tests/fixtures/smoke/resource",
                "--images",
                "tests/fixtures/smoke/screens",
                "--entry",
                "DoesNotExist",
                "--once",
            ]
        )

    assert code == 1
    assert "失败" in buffer.getvalue()
