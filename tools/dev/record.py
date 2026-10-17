#!/usr/bin/env python3
"""把一次真机任务执行录制成可回放的用例。

产物：

    tests/recordings/<case>/<case>.jsonl        # 操作与截图索引（RecordController 写入）
    tests/recordings/<case>/<case>-Screenshot/  # 录制的截图帧
    tests/recordings/<case>/<case>.summary.json # 本次执行摘要（入口、节点序列、结果）

之后可用 `python tools/dev/replay.py --case <case>` 离线回放，
无需设备即可验证流程分支是否被改坏。

用法：

    python tools/dev/record.py --case farm-normal --entry FarmStageEntry
    python tools/dev/record.py --case launch --entry DailyFullEntry --address 127.0.0.1:16384
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import REPO_ROOT, enable_local_lib  # noqa: E402

enable_local_lib()

from maa.controller import AdbController, RecordController  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

SHORT_SIDE = 720


def pick_device(address: str | None, adb_path: str | None) -> tuple[str, str]:
    if address and adb_path:
        return adb_path, address

    devices = Toolkit.find_adb_devices()
    if not devices:
        raise SystemExit(
            "未找到 ADB 设备。请启动模拟器/连接手机后重试，或用 --adb / --address 手动指定。"
        )

    if address:
        matched = [device for device in devices if device.address == address]
        if not matched:
            addresses = ", ".join(device.address for device in devices)
            raise SystemExit(f"没有地址为 {address} 的设备，当前可用：{addresses}")
        return str(matched[0].adb_path), matched[0].address

    for index, device in enumerate(devices):
        print(f"  [{index}] {device.name} {device.address}")
    device = devices[0]
    print(f"使用第一台设备：{device.name} {device.address}（可用 --address 指定其它设备）")
    return str(device.adb_path), device.address


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="录制可回放的 MaaFramework 任务用例")
    parser.add_argument("--case", required=True, help="用例名，例如 farm-normal")
    parser.add_argument("--entry", required=True, help="任务入口节点名")
    parser.add_argument("--resource", default="assets/resource", help="资源包目录（相对仓库根）")
    parser.add_argument("--address", help="ADB 设备地址，例如 127.0.0.1:16384")
    parser.add_argument("--adb", help="adb 可执行文件路径")
    parser.add_argument("--out", default="tests/recordings", help="录制输出目录")
    args = parser.parse_args(argv)

    record_dir = REPO_ROOT / args.out / args.case
    record_dir.mkdir(parents=True, exist_ok=True)
    recording_path = record_dir / f"{args.case}.jsonl"

    log_dir = REPO_ROOT / "debug"
    log_dir.mkdir(exist_ok=True)
    Tasker.set_log_dir(str(log_dir))
    Tasker.set_save_on_error(True)

    resource = Resource()
    bundle = REPO_ROOT / args.resource
    if not bundle.is_dir():
        raise SystemExit(f"资源目录不存在：{bundle}")
    resource.post_bundle(bundle).wait()
    if not resource.loaded:
        raise SystemExit("资源加载失败，请先执行 python tools/dev/setup.py 准备 OCR 模型")

    adb_path, address = pick_device(args.address, args.adb)
    print(f"连接设备：{address}")
    controller = AdbController(adb_path=adb_path, address=address)
    controller.set_screenshot_target_short_side(SHORT_SIDE)
    recorder = RecordController(controller, recording_path)

    controller_job = recorder.post_connection()
    controller_job.wait()
    if not controller_job.succeeded:
        raise SystemExit("设备连接失败，请检查 adb / 模拟器状态")

    tasker = Tasker()
    if not tasker.bind(resource, recorder):
        raise SystemExit("Tasker 绑定资源/控制器失败")

    print(f"执行 {args.entry} ...（录制中，请勿操作设备）")
    job = tasker.post_task(args.entry)
    job.wait()
    detail = job.get()

    nodes: list[dict] = []
    status = "unknown"
    if detail is not None:
        status = "succeeded" if detail.status.succeeded else ("failed" if detail.status.failed else str(detail.status))
        for node in detail.nodes:
            nodes.append({"name": node.name, "completed": bool(node.completed)})

    summary = {
        "case": args.case,
        "entry": args.entry,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "device": address,
        "status": status,
        "nodes": nodes,
    }
    (record_dir / f"{args.case}.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"任务状态：{status}，共 {len(nodes)} 个节点")
    for item in nodes:
        mark = "✓" if item["completed"] else "×"
        print(f"  {mark} {item['name']}")
    print(f"录制文件：{recording_path.relative_to(REPO_ROOT)}")
    print(f"下一步：python tools/dev/replay.py --case {args.case}")
    return 0 if status == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
