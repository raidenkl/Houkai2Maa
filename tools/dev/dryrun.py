#!/usr/bin/env python3
"""离线跑一条 pipeline：用一组截图代替设备，验证流程分支是否走得通。

原理：`StaticImageController` 每次 `screencap()` 返回下一张图（可循环），
所有点击都被丢弃。适合在**没有设备**时确认「节点串联是否正确」：

* 分支是否可达（图片顺序对上时应命中预期节点）；
* 有没有写出死循环；
* 改名/改顺序后是否还会走到旧节点。

注意：它验证的是**流程结构与识别参数**，不验证真实点击效果。
最终仍需真机跑一遍。

用法：

    python tools/dev/dryrun.py --images tests/screens/daily --entry DailyFullEntry
    python tools/dev/dryrun.py --images a.png --images b.png --entry FooEntry --once
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import REPO_ROOT, enable_local_lib  # noqa: E402

enable_local_lib()

from maa.define import LoggingLevelEnum  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from static_controller import StaticImageController, load_images  # noqa: E402

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp")


def collect_images(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if path.is_dir():
            files.extend(sorted(p for p in path.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES))
        elif path.is_file():
            files.append(path)
        else:
            raise SystemExit(f"找不到图片或目录：{path}")
    if not files:
        raise SystemExit("没有可用截图（支持 png/jpg/bmp）")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用截图离线跑 pipeline")
    parser.add_argument("--images", action="append", required=True, help="截图文件或目录，可重复")
    parser.add_argument("--entry", required=True, help="入口节点名")
    parser.add_argument("--resource", default="assets/resource", help="资源包目录（相对仓库根）")
    parser.add_argument("--once", action="store_true", help="图片只播一遍（默认循环）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    files = collect_images(args.images)
    images = load_images([str(path) for path in files])

    Tasker.set_stdout_level(LoggingLevelEnum.Fatal)
    Tasker.set_log_dir(str(REPO_ROOT / "debug"))
    Tasker.set_save_on_error(True)

    resource = Resource()
    bundle = REPO_ROOT / args.resource
    resource.post_bundle(bundle).wait()
    if not resource.loaded:
        raise SystemExit("资源加载失败，请先执行 python tools/dev/setup.py")

    controller = StaticImageController(images, cycle=not args.once)
    controller.post_connection().wait()

    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise SystemExit("Tasker 绑定失败")

    job = tasker.post_task(args.entry)
    job.wait()
    detail = job.get()
    if detail is None:
        raise SystemExit("任务没有返回结果（入口节点可能不存在）")

    nodes = [{"name": node.name, "completed": bool(node.completed)} for node in detail.nodes]
    succeeded = bool(detail.status.succeeded)

    if args.json:
        print(
            json.dumps(
                {
                    "entry": args.entry,
                    "images": [str(path) for path in files],
                    "succeeded": succeeded,
                    "nodes": nodes,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"入口 {args.entry}，截图 {len(files)} 张（{'单次' if args.once else '循环'}）")
        for item in nodes:
            print(f"  {'✓' if item['completed'] else '×'} {item['name']}")
        print(f"\n结果：{'成功' if succeeded else '失败'}，共 {len(nodes)} 个节点")
        print("提示：离线只验证流程结构，最终请用真机再跑一遍。")
    return 0 if succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
