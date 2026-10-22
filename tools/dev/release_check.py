#!/usr/bin/env python3
"""发布前自检：版本号、路径引用、工作区状态。

不重复 `npm run verify` 的工作（CI 会跑全套）；这里只检查**发布特有**的问题：

1. `interface.json` 的 `version` 是合法版本号；
2. 给了 `--tag` 时，version 与 tag 一致（防止「改了版本没打 tag」或反之）；
3. `import` / `pretask.args` / `agent.child_args` 的相对路径都能解析；
4. 工作区是否干净（有未提交改动时提醒，`--strict-git` 视为失败）。

用法：

    python tools/dev/release_check.py
    python tools/dev/release_check.py --tag v2.0.0
    python tools/dev/release_check.py --tag v2.0.0 --strict-git
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import REPO_ROOT  # noqa: E402
from shared.jsonc import JsoncError, load_jsonc  # noqa: E402
from shared.packaging import check_paths as check_interface_paths  # noqa: E402
from shared.version import is_valid, matches_tag, parse  # noqa: E402

INTERFACE_FILE = REPO_ROOT / "assets" / "interface.json"


def check_paths(interface: dict) -> list[str]:
    """仓库侧校验：import / pretask / agent 的相对路径都能解析。

    注意：仓库的 interface.json **刻意不写 agent 块**（由 tools/install.py 打包时注入），
    所以这里只校验已写出来的引用；「有 Custom 节点却没有 agent 块」由
    `tools/install.py::verify_install` 在真正的安装目录里检查。
    """

    return check_interface_paths(interface, INTERFACE_FILE.parent)


def git_dirty() -> bool:
    completed = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True)
    return bool(completed.stdout.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发布前自检")
    parser.add_argument("--tag", help="即将发布的 tag，例如 v2.0.0")
    parser.add_argument("--strict-git", action="store_true", help="工作区有未提交改动时视为失败")
    args = parser.parse_args(argv)

    problems: list[str] = []
    warnings: list[str] = []

    try:
        interface = load_jsonc(INTERFACE_FILE)
    except (JsoncError, OSError) as error:
        print(f"[error] 无法读取 interface.json：{error}", file=sys.stderr)
        return 1

    version = str(interface.get("version", ""))
    if not version:
        problems.append("interface.json 缺少 version")
    elif not is_valid(version):
        problems.append(f"version 不是合法版本号：{version}")
    else:
        print(f"版本号：{version}（parsed={parse(version)}）")

    if args.tag:
        if not is_valid(args.tag):
            problems.append(f"tag 不是合法版本号：{args.tag}")
        elif not matches_tag(version, args.tag):
            problems.append(f"version（{version}）与 tag（{args.tag}）不一致")

    problems.extend(check_paths(interface))

    if git_dirty():
        warnings.append("工作区有未提交改动；发布应基于干净的工作区")
        if args.strict_git:
            problems.append("工作区不干净（--strict-git）")

    for item in warnings:
        print(f"[warn] {item}")
    for item in problems:
        print(f"[error] {item}")

    if problems:
        print(f"\n发布自检失败：{len(problems)} 个问题")
        return 1
    print("\n发布自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
