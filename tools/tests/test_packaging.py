"""`tools/shared/packaging.py`：Agent / 嵌入式 Python 的打包规则测试。

这些规则决定「发出去的包里到底有没有 Agent」。历史上踩过的坑是：
`interface.json` 写了裸 `python` → MFA 拼成 `resource/base/python` → 启动链中止，
用户看到的是「连不上模拟器」。所以规则本身必须有测试锁住。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

packaging = pytest.importorskip("shared.packaging")


def make_interface(**extra: object) -> dict:
    return {"version": "v1.0.0", "import": ["tasks/daily/Demo.json"], **extra}


def test_supports_agent_only_win_x64() -> None:
    assert packaging.supports_agent("win", "x86_64")
    assert not packaging.supports_agent("win", "aarch64")
    assert not packaging.supports_agent("macos", "aarch64")
    assert not packaging.supports_agent("linux", "x86_64")
    assert not packaging.supports_agent("android", "aarch64")


def test_agent_block_requires_runtime() -> None:
    assert packaging.agent_block(False) is None
    block = packaging.agent_block(True)
    assert block == {"child_exec": "./python/python.exe", "child_args": ["./agent/main.py"]}


def test_apply_agent_injects_on_supported_platform() -> None:
    interface = make_interface()
    packaging.apply_agent(interface, "win", "x86_64", has_python=True)
    assert interface["agent"]["child_exec"] == "./python/python.exe"
    assert "pretask" not in interface


def test_apply_agent_removes_blocks_without_runtime() -> None:
    interface = make_interface(agent={"child_exec": "./python/python.exe"}, pretask={"exec": "python"})
    packaging.apply_agent(interface, "win", "x86_64", has_python=False)
    assert "agent" not in interface
    assert "pretask" not in interface


def test_apply_agent_removes_blocks_on_other_platforms() -> None:
    interface = make_interface(agent={"child_exec": "./python/python.exe"})
    packaging.apply_agent(interface, "macos", "aarch64", has_python=True)
    assert "agent" not in interface


def test_check_paths_reports_missing_child_exec(tmp_path: Path) -> None:
    """最关键的一条：运行时没拷进包时，自检必须失败。"""

    (tmp_path / "tasks" / "daily").mkdir(parents=True)
    (tmp_path / "tasks" / "daily" / "Demo.json").write_text("{}", encoding="utf-8")
    interface = make_interface(agent={"child_exec": "./python/python.exe", "child_args": ["./agent/main.py"]})
    problems = packaging.check_paths(interface, tmp_path)
    assert any("child_exec" in item for item in problems)
    assert any("./agent/main.py" in item for item in problems)


def test_check_paths_accepts_complete_package(tmp_path: Path) -> None:
    (tmp_path / "tasks" / "daily").mkdir(parents=True)
    (tmp_path / "tasks" / "daily" / "Demo.json").write_text("{}", encoding="utf-8")
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "main.py").write_text("", encoding="utf-8")
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "python.exe").write_text("", encoding="utf-8")
    interface = make_interface(agent={"child_exec": "./python/python.exe", "child_args": ["./agent/main.py"]})
    assert packaging.check_paths(interface, tmp_path) == []


def test_check_paths_reports_missing_import(tmp_path: Path) -> None:
    interface = make_interface()
    problems = packaging.check_paths(interface, tmp_path)
    assert any("import" in item for item in problems)


def test_check_paths_skips_placeholder_paths(tmp_path: Path) -> None:
    """`{PROJECT_DIR}/...` 由 MFA 在运行期替换，打包阶段不该当成缺失。"""

    (tmp_path / "tasks" / "daily").mkdir(parents=True)
    (tmp_path / "tasks" / "daily" / "Demo.json").write_text("{}", encoding="utf-8")
    interface = make_interface(pretask={"exec": "{PROJECT_DIR}/../../python/python.exe"})
    assert packaging.check_paths(interface, tmp_path) == []


def write_pipeline(root: Path, name: str, nodes: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(json.dumps(nodes), encoding="utf-8")


def test_count_custom_nodes_handles_both_sections(tmp_path: Path) -> None:
    write_pipeline(
        tmp_path,
        "a.json",
        {
            "Plain": {"recognition": {"type": "OCR"}, "action": {"type": "Click"}},
            "CustomAction": {"recognition": {"type": "DirectHit"}, "action": {"type": "Custom"}},
            "CustomReco": {"recognition": {"type": "Custom"}, "action": {"type": "DoNothing"}},
        },
    )
    assert packaging.count_custom_nodes(tmp_path) == 2


def test_count_custom_nodes_ignores_default_pipeline(tmp_path: Path) -> None:
    write_pipeline(tmp_path, "default_pipeline.json", {"Default": {"action": {"type": "Custom"}}})
    assert packaging.count_custom_nodes(tmp_path) == 0


def test_count_custom_nodes_tolerates_broken_json(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    assert packaging.count_custom_nodes(tmp_path) == 0


def test_custom_requires_agent(tmp_path: Path) -> None:
    write_pipeline(
        tmp_path,
        "a.json",
        {"CustomAction": {"recognition": {"type": "DirectHit"}, "action": {"type": "Custom"}}},
    )
    assert packaging.custom_requires_agent({}, tmp_path)
    assert packaging.custom_requires_agent({"agent": {"child_exec": "./python/python.exe"}}, tmp_path) == []
    assert packaging.custom_requires_agent({}, tmp_path / "empty") == []
