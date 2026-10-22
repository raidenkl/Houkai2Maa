"""`tools/lint/pipeline_lint.py` 的自定义件注册表扫描测试。

背景：E204 依赖「pipeline 里写的 Custom ID 是否在 agent/ 注册过」。
早期实现只认字符串字面量，`@AgentServer.custom_action(LOOP_ACTION)` 这种
「模块级常量」写法会被误报成未注册；反过来，完全解析不到的标识符如果静默
忽略，真正的注册缺失就只能在运行期才暴露。这两个方向都要锁住。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pipeline_lint = pytest.importorskip("lint.pipeline_lint")

scan = pipeline_lint.scan_agent_registrations


def write_agent(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


def test_scans_string_literals(tmp_path: Path) -> None:
    write_agent(
        tmp_path,
        "a.py",
        """
from maa.agent.agent_server import AgentServer


@AgentServer.custom_action("FarmRoute")
class FarmRoute:
    pass


@AgentServer.custom_recognition("FarmScene")
class FarmScene:
    pass
""",
    )
    actions, recognitions, unresolved = scan(tmp_path)
    assert actions == {"FarmRoute"}
    assert recognitions == {"FarmScene"}
    assert unresolved == set()


def test_scans_module_level_constants(tmp_path: Path) -> None:
    write_agent(
        tmp_path,
        "b.py",
        """
LOOP_ACTION = "FarmLoop"
NOTE_ID: str = "FarmNote"


@AgentServer.custom_action(LOOP_ACTION)
class FarmLoop:
    pass


@AgentServer.custom_action(NOTE_ID)
class FarmNote:
    pass
""",
    )
    actions, _, unresolved = scan(tmp_path)
    assert actions == {"FarmLoop", "FarmNote"}
    assert unresolved == set()


def test_resolves_constant_from_other_module(tmp_path: Path) -> None:
    write_agent(tmp_path, "ids.py", 'ROUTE_ID = "FarmRoute"\n')
    write_agent(tmp_path, "c.py", "@AgentServer.custom_action(ROUTE_ID)\nclass FarmRoute:\n    pass\n")
    actions, _, unresolved = scan(tmp_path)
    assert actions == {"FarmRoute"}
    assert unresolved == set()


def test_unresolvable_identifier_is_reported(tmp_path: Path) -> None:
    write_agent(tmp_path, "d.py", "@AgentServer.custom_action(SOMEONE_ELSE)\nclass X:\n    pass\n")
    _, _, unresolved = scan(tmp_path)
    assert any("custom_action(SOMEONE_ELSE)" in item for item in unresolved)


def test_missing_agent_dir_is_not_an_error(tmp_path: Path) -> None:
    actions, recognitions, unresolved = scan(tmp_path / "nope")
    assert (actions, recognitions, unresolved) == (set(), set(), set())


def test_repo_registry_contains_activity_farm_ids() -> None:
    """真实仓库：活动清体力改造用到的 ID 必须都能被扫到，否则 lint 会误报。"""

    actions, recognitions, unresolved = scan()
    assert {"FarmLoop", "FarmReset", "FarmFail", "FarmNote"} <= actions
    assert {"StaminaInsufficient", "PanelState"} <= recognitions
    assert unresolved == set()
