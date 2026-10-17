#!/usr/bin/env python3
"""`@nekosu/maa-tools` 的薄封装。

为什么需要它：maa-tools 通过 `pacote` 下载 MaaFramework 运行时，
默认会写入用户主目录的 npm 缓存（`~/.npm`）。在没有写权限的环境里
（沙箱、受限 CI、以只读 home 运行）会直接失败且报错信息很隐蔽。

本脚本把 `npm_config_cache` 指向仓库内的 `.npm-cache`，并把
`--cache` 之外的参数原样透传，做到「克隆即可跑」。

用法：

    python tools/dev/maa_tools.py check
    python tools/dev/maa_tools.py test
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = REPO_ROOT / "node_modules" / ".bin"


def main(argv: list[str]) -> int:
    if not argv:
        print("用法: python tools/dev/maa_tools.py <check|test|init> [更多参数]", file=sys.stderr)
        return 2

    binary = BIN_DIR / ("maa-tools.cmd" if os.name == "nt" else "maa-tools")
    if not binary.exists():
        print("未找到 maa-tools，请先执行：npm install", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env.setdefault("npm_config_cache", str(REPO_ROOT / ".npm-cache"))
    env.setdefault("npm_config_update_notifier", "false")
    env.setdefault("npm_config_fetch_retries", "5")
    env.setdefault("npm_config_fetch_retry_mintimeout", "2000")

    # 首次运行需要从 npm 拉取 MaaFramework 运行时，偶发网络失败会直接返回非零；
    # 这里重试两次，并在日志里说明，避免让一次抖动变成「构建失败」。
    attempts = 3
    for attempt in range(1, attempts + 1):
        completed = subprocess.run([str(binary), *argv], cwd=REPO_ROOT, env=env)
        if completed.returncode == 0:
            return 0
        if attempt == attempts:
            return completed.returncode
        print(f"[maa-tools] 第 {attempt} 次执行失败（可能为网络抖动），重试 …", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
