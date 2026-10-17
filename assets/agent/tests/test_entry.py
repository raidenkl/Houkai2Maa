"""Agent 入口与自定义件注册的冒烟测试（不连接设备）。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("maa", reason="需要 maafw 绑定（python tools/dev/setup.py）")

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_DIR = REPO_ROOT / "assets" / "agent"


def _python_env() -> dict[str, str]:
    env = dict(os.environ)
    local_lib = REPO_ROOT / ".pylib"
    if local_lib.is_dir():
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(local_lib), env.get("PYTHONPATH", "")]))
    return env


def test_main_without_arguments_prints_usage() -> None:
    env = _python_env()

    completed = subprocess.run(
        [sys.executable, str(AGENT_DIR / "main.py")],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert completed.returncode == 2
    assert "Usage" in completed.stdout


def test_custom_items_are_registered() -> None:
    # 在子进程里导入：AgentServer 相关模块会动到框架全局状态，
    # 在同进程里 import 会污染后续用 Tasker/Resource 的测试。
    code = (
        f"import sys; sys.path.insert(0, r'{AGENT_DIR}'); "
        "import actions, recognitions; "
        "print('ACTIONS', ','.join(actions.register_all())); "
        "print('RECOGNITIONS', ','.join(recognitions.register_all()))"
    )
    env = _python_env()
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert completed.returncode == 0, completed.stderr

    output = completed.stdout
    action_line = next(line for line in output.splitlines() if line.startswith("ACTIONS "))
    recognition_line = next(line for line in output.splitlines() if line.startswith("RECOGNITIONS "))
    actions = set(action_line.split(" ", 1)[1].split(","))
    recognitions = set(recognition_line.split(" ", 1)[1].split(","))

    assert {"FarmLoop", "FarmReset", "FarmFail", "FarmNote", "SceneGuard", "SaveShot"} <= actions
    assert {"StaminaInsufficient", "PanelState"} <= recognitions
