#!/usr/bin/env python3
"""离线回放用例，验证 pipeline 流程没有被改坏。

用例来自 `tools/dev/record.py` 的录制产物，描述文件放在 `tests/cases/*.json`：

    {
        "case": "farm-normal",
        "entry": "FarmStageEntry",
        "recording": "tests/recordings/farm-normal/farm-normal.jsonl",
        "expect": {
            "completed": true,
            "hit_nodes": ["FarmStart", "FarmWaitResult", "FarmAgain"],
            "max_steps": 120
        }
    }

`hit_nodes` 按**顺序子序列**匹配：录制的节点序列里必须按顺序出现这些节点。
缺少录制文件时默认跳过（返回 0），便于用例先行提交、录屏随后补录。
加 `--require` 可把跳过视为失败（发布前使用）。

用法：

    python tools/dev/replay.py --all
    python tools/dev/replay.py --case farm-normal
    python tools/dev/replay.py --all --require
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import REPO_ROOT, enable_local_lib  # noqa: E402
from shared.jsonc import JsoncError, load_jsonc  # noqa: E402
from shared.lists import is_subsequence  # noqa: E402

enable_local_lib()

from maa.controller import ReplayController  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402


def load_cases(cases_dir: Path) -> list[dict]:
    cases: list[dict] = []
    for path in sorted(cases_dir.glob("*.json")):
        try:
            data = load_jsonc(path)
        except JsoncError as error:
            raise SystemExit(f"用例解析失败：{error}")
        if not isinstance(data, dict) or "case" not in data:
            raise SystemExit(f"用例缺少 case 字段：{path}")
        data.setdefault("_path", str(path.relative_to(REPO_ROOT)))
        cases.append(data)
    return cases


def run_case(case: dict, require: bool) -> str:
    name = case["case"]
    recording = REPO_ROOT / case["recording"]
    if not recording.is_file():
        message = f"跳过 {name}：缺少录制文件 {case['recording']}（用 tools/dev/record.py 补录）"
        if require:
            print(f"[FAIL] {message}")
            return "fail"
        print(f"[SKIP] {message}")
        return "skip"

    resource = Resource()
    resource.post_bundle(REPO_ROOT / case.get("resource", "assets/resource")).wait()
    if not resource.loaded:
        print(f"[FAIL] {name}：资源加载失败")
        return "fail"

    controller = ReplayController(recording)
    controller.post_connection().wait()

    tasker = Tasker()
    tasker.bind(resource, controller)
    job = tasker.post_task(case["entry"])
    job.wait()
    detail = job.get()
    if detail is None:
        print(f"[FAIL] {name}：任务无结果")
        return "fail"

    actual = [node.name for node in detail.nodes]
    expect = case.get("expect", {})
    failures: list[str] = []

    if expect.get("completed", True) and not detail.status.succeeded:
        failures.append(f"任务未成功完成（status={detail.status}）")

    max_steps = expect.get("max_steps")
    if isinstance(max_steps, int) and len(actual) > max_steps:
        failures.append(f"节点数 {len(actual)} 超过 max_steps={max_steps}")

    hit_nodes = expect.get("hit_nodes") or []
    if hit_nodes and not is_subsequence(hit_nodes, actual):
        failures.append(f"期望按顺序命中 {hit_nodes}，实际 {actual}")

    if failures:
        print(f"[FAIL] {name}")
        for failure in failures:
            print(f"       - {failure}")
        return "fail"

    print(f"[PASS] {name}（{len(actual)} 个节点）")
    return "pass"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="回放 MaaFramework 录制用例")
    parser.add_argument("--all", action="store_true", help="运行 tests/cases 下的全部用例")
    parser.add_argument("--case", help="运行指定用例")
    parser.add_argument("--cases-dir", default="tests/cases", help="用例目录")
    parser.add_argument("--require", action="store_true", help="缺少录制文件时视为失败")
    args = parser.parse_args(argv)

    if not args.all and not args.case:
        parser.error("需要 --all 或 --case <name>")

    cases = load_cases(REPO_ROOT / args.cases_dir)
    if not cases:
        print("没有找到任何用例（tests/cases/*.json）。")
        return 1 if args.require else 0

    selected = [case for case in cases if args.case is None or case["case"] == args.case]
    if not selected:
        print(f"没有名为 {args.case} 的用例")
        return 1

    results = [run_case(case, args.require) for case in selected]
    passed = results.count("pass")
    failed = results.count("fail")
    skipped = results.count("skip")
    print(f"\n结果：{passed} passed / {failed} failed / {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
