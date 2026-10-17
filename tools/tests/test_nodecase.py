"""`tools/dev/nodecase.py` 的用例生成测试（离线，使用 smoke 夹具）。"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

pytest.importorskip("maa", reason="需要 maafw 绑定（python tools/dev/setup.py）")
pytest.importorskip("PIL", reason="需要 Pillow 读取 fixture 截图")

import nodecase  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "smoke"


def test_interface_defaults_reads_repo_interface() -> None:
    controller, resource = nodecase.interface_defaults(REPO_ROOT / "assets" / "interface.json")
    assert controller == "安卓端"
    assert resource == "官服"


def test_generates_cases_with_hits(tmp_path: Path) -> None:
    out = tmp_path / "generated.json"
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = nodecase.main(
            [
                "--resource",
                "tests/fixtures/smoke/resource",
                "--node",
                "SmokeStepA",
                "--node",
                "SmokeStepB",
                "--images",
                "tests/fixtures/smoke/screens",
                "--out",
                str(out),
            ]
        )

    assert code == 0, buffer.getvalue()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["configs"]["imageRoot"] == "screens"
    assert len(payload["cases"]) == 2
    by_image = {case["image"]: case["hits"] for case in payload["cases"]}
    assert by_image["01-home.png"] == ["SmokeStepA"]
    assert by_image["02-panel.png"] == ["SmokeStepB"]
    assert (tmp_path / "screens" / "01-home.png").is_file()


def test_missing_image_fails(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        nodecase.main(
            [
                "--resource",
                "tests/fixtures/smoke/resource",
                "--node",
                "SmokeStepA",
                "--image",
                str(tmp_path / "nope.png"),
                "--out",
                str(tmp_path / "x.json"),
            ]
        )
