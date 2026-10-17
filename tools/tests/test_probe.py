"""`tools/dev/probe.py` 的单节点探测行为测试（不需要设备）。"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("maa", reason="需要 maafw 绑定（python tools/dev/setup.py）")
pytest.importorskip("PIL", reason="需要 Pillow 读取 fixture 截图")

import probe  # noqa: E402
from maa.define import LoggingLevelEnum  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "smoke"


@pytest.fixture(scope="module")
def resource() -> Resource:
    Tasker.set_stdout_level(LoggingLevelEnum.Fatal)
    bundle = Resource()
    bundle.post_bundle(FIXTURE / "resource").wait()
    assert bundle.loaded
    return bundle


def test_probe_hits_matching_screen(resource: Resource) -> None:
    result = probe.probe_node(resource, "SmokeStepA", FIXTURE / "screens" / "01-home.png")
    assert result["hit"] is True
    assert result["box"] == [100, 100, 120, 80]
    assert result["score"] == pytest.approx(1.0, abs=0.01)


def test_probe_misses_other_screen(resource: Resource) -> None:
    result = probe.probe_node(resource, "SmokeStepA", FIXTURE / "screens" / "02-panel.png")
    assert result["hit"] is False
    assert result["box"] is None


def test_pipeline_nodes_lists_fixture_nodes() -> None:
    names = probe.pipeline_nodes(FIXTURE / "resource")
    assert {"SmokeEntry", "SmokeStepA", "SmokeStepB"} <= names
