#!/usr/bin/env python3
"""运行 ruff（优先用仓库内 `.pylib/bin/ruff`，其次 PATH）。

CI 里 ruff 装在系统环境，本地装在 `.pylib`，统一从这个入口调用，
避免 npm script 里写死路径。

用法：

    python tools/dev/run_ruff.py check .
    python tools/dev/run_ruff.py format --check .
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def find_ruff() -> str | None:
    bin_dir = REPO_ROOT / ".pylib" / "bin"
    # Windows 上 pip 装出来的是 ruff.exe，不能只按无扩展名查找
    for name in ("ruff.exe", "ruff"):
        candidate = bin_dir / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("ruff")


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: python tools/dev/run_ruff.py <check|format> [...]", file=sys.stderr)
        return 2
    ruff = find_ruff()
    if ruff is None:
        print("未找到 ruff，请执行 python tools/dev/setup.py（或 pip install ruff）", file=sys.stderr)
        return 2
    return subprocess.run([ruff, *argv], cwd=REPO_ROOT).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
