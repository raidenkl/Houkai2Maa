#!/usr/bin/env python3
"""校验打包用的 Python 运行时能真正拉起 Agent。

CI 的 `python-win-x64` 作业在把运行时塞进 artifact 之前跑一次。检查三件事：

1. 解释器自身可用，且 `maa` / `numpy` 能 import（说明 requirements.txt 装齐了）；
2. `assets/agent` 的注册表能加载出预期的自定义件 ID；
3. `assets/agent/main.py` 无参运行必须退出码 2（入口契约，见 main.py）。

任何一项失败都意味着「运行时不完整」，此时发出去的包会在用户机器上表现为
Agent 起不来 —— 而 pipeline 里一旦有 Custom 节点，任务就会卡住或走降级路径。
宁可在这里失败。

用法：

    python tools/dev/verify_agent_runtime.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "assets" / "agent"
LOCAL_LIB = REPO_ROOT / ".pylib"

EXPECTED_ACTIONS = {"FarmLoop", "FarmReset", "FarmFail", "FarmNote"}
EXPECTED_RECOGNITIONS = {"StaminaInsufficient", "PanelState"}
REGISTRY_TIMEOUT = 120


def force_utf8_console() -> None:
    """把 stdout/stderr 切到 UTF-8。

    本脚本会打印中文。GitHub 的 windows-latest 控制台是 **cp1252**，
    直接 print 中文会抛 `UnicodeEncodeError` 并把整个作业打成失败
    （2026-10-22 实测：python-win-x64 挂在 Verify runtime）。
    本机是 cp936 所以看不见，只有 CI 才复现。
    """

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # 非 TextIOWrapper（如被重定向到自定义流）
            pass


force_utf8_console()


def child_env() -> dict[str, str]:
    """把仓库内的 `.pylib` 传给子进程，并强制 UTF-8 输出。

    CI 里 maafw 装在 site-packages，不需要 `.pylib`；本地开发机依赖 `.pylib`，
    不传的话子进程 `import maa` 会直接失败，报出误导性的「运行时不完整」。
    `PYTHONIOENCODING` 是给子进程的同一份保险。
    """

    env = dict(os.environ)
    paths = [str(AGENT_DIR)]
    if LOCAL_LIB.is_dir():
        paths.insert(0, str(LOCAL_LIB))
    existing = env.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def fail(message: str) -> int:
    print(f"[error] {message}", file=sys.stderr)
    return 1


def check_imports() -> int:
    if LOCAL_LIB.is_dir() and str(LOCAL_LIB) not in sys.path:
        sys.path.insert(0, str(LOCAL_LIB))
    try:
        import maa  # noqa: F401
        import numpy  # noqa: F401
    except Exception as error:  # pragma: no cover - 运行时环境问题
        return fail(f"运行时缺少依赖：{error}（先装 assets/agent/requirements.txt）")
    version = getattr(maa, "__version__", "unknown")
    print(f"  maa={version} numpy ok  ({sys.executable})")
    return 0


def check_registry() -> int:
    """注册表必须在子进程里查：import agent_server 会把框架库替换掉。"""

    script = (
        "import sys; "
        f"sys.path.insert(0, {str(AGENT_DIR)!r}); "
        "import actions, recognitions; "
        "print(','.join(actions.register_all() + recognitions.register_all()))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=REGISTRY_TIMEOUT,
        env=child_env(),
    )
    if completed.returncode != 0:
        return fail(f"注册表加载失败：{completed.stderr.strip()[-800:]}")
    registered = {item for item in completed.stdout.strip().split(",") if item}
    missing = (EXPECTED_ACTIONS | EXPECTED_RECOGNITIONS) - registered
    if missing:
        return fail(f"注册表缺少 ID：{sorted(missing)}（实际 {sorted(registered)}）")
    print(f"  注册表 ok：{len(registered)} 个 ID")
    return 0


def check_entry() -> int:
    completed = subprocess.run(
        [sys.executable, str(AGENT_DIR / "main.py")],
        capture_output=True,
        text=True,
        timeout=REGISTRY_TIMEOUT,
        env=child_env(),
    )
    if completed.returncode != 2:
        return fail(f"main.py 无参应以退出码 2 结束，实际 {completed.returncode}：{completed.stderr.strip()[-400:]}")
    if "Usage" not in completed.stdout:
        return fail(f"main.py 无参应打印 Usage，实际输出：{completed.stdout.strip()[:200]}")
    print("  入口契约 ok（无参退出码 2）")
    return 0


def main() -> int:
    print(f"校验 Agent 运行时：{sys.executable}")
    for check in (check_imports, check_registry, check_entry):
        code = check()
        if code:
            return code
    print("运行时自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
