#!/usr/bin/env python3
"""用一张截图探测**单个节点**的识别结果（阈值调参用）。

与 `dryrun.py` 的区别：dryrun 跑整条流程，probe 只跑一个节点并输出
命中/分数/命中框，适合回答「这个模板在这张图上能不能命中」。

原理：把节点作为入口跑一次，并用 `pipeline_override` 清空它的 `next`，
这样不会继续往下走；控制器用静态图片（不碰设备）。

用法：

    python tools/dev/probe.py --node SmokeStepA --image tests/fixtures/smoke/screens/01-home.png
    python tools/dev/probe.py --node SmokeStepA --image tests/fixtures/smoke/screens/02-panel.png
    python tools/dev/probe.py --node DailySignInButton --images shots/ --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import REPO_ROOT, enable_local_lib  # noqa: E402
from shared.jsonc import JsoncError, load_jsonc  # noqa: E402

enable_local_lib()

from maa.define import LoggingLevelEnum  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

from static_controller import StaticImageController, load_images  # noqa: E402

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp")


def collect_images(raw_paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in raw_paths:
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
        raise SystemExit("没有可用截图")
    return files


def pipeline_nodes(resource_dir: Path) -> set[str]:
    """收集资源包里已有的节点名（用于提前发现「节点名写错 / 资源选错」）。"""

    names: set[str] = set()
    pipeline_dir = resource_dir / "pipeline"
    if not pipeline_dir.is_dir():
        return names
    for path in pipeline_dir.rglob("*.json"):
        try:
            data = load_jsonc(path)
        except JsoncError:
            continue
        if isinstance(data, dict):
            names.update(key for key in data if not key.startswith("$"))
    return names


def probe_node(resource: Resource, node: str, image_path: Path, timeout: int = 2000) -> dict:
    controller = StaticImageController(load_images([str(image_path)]), cycle=False)
    controller.post_connection().wait()

    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise SystemExit("Tasker 绑定失败")

    # 清空 next 让任务停在当前节点；同时把 timeout 调小，
    # 否则「未命中」时框架会按默认 20s 反复识别，拖慢批量探测。
    override = {node: {"next": [], "on_error": [], "timeout": timeout}}
    job = tasker.post_task(node, override)
    job.wait()
    detail = job.get()

    result = {"image": str(image_path), "node": node, "hit": False, "box": None, "score": None}
    if detail is None:
        return result
    for node_detail in detail.nodes:
        if node_detail.name != node:
            continue
        recognition = node_detail.recognition
        if recognition is None or not recognition.hit:
            return result
        best = recognition.best_result
        box = recognition.box
        coords = None
        if box is not None:
            coords = [box.x, box.y, box.w, box.h] if hasattr(box, "x") else [int(v) for v in box[:4]]
        result.update(
            hit=True,
            box=coords,
            score=round(float(getattr(best, "score", 0.0)), 4) if best is not None else None,
        )
        return result
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="单节点识别探测（不连设备）")
    parser.add_argument("--node", required=True, help="要探测的节点名")
    parser.add_argument("--image", action="append", default=[], help="截图文件，可重复")
    parser.add_argument("--images", action="append", default=[], help="截图目录（与该目录下所有图片）")
    parser.add_argument("--resource", default="assets/resource", help="资源包目录（相对仓库根）")
    parser.add_argument("--timeout", type=int, default=2000, help="单张图等待识别的最长时间（ms，默认 2000）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args(argv)

    files = collect_images(list(args.image) + list(args.images))

    Tasker.set_stdout_level(LoggingLevelEnum.Fatal)
    resource_dir = REPO_ROOT / args.resource
    available = pipeline_nodes(resource_dir)
    if args.node not in available:
        raise SystemExit(
            f"节点 `{args.node}` 不在 {args.resource} 的 pipeline 里。"
            f"已有节点示例：{', '.join(sorted(available)[:5]) or '(无)'}；"
            "如果是探测测试夹具，请加 --resource tests/fixtures/smoke/resource"
        )

    resource = Resource()
    resource.post_bundle(resource_dir).wait()
    if not resource.loaded:
        raise SystemExit("资源加载失败，请先执行 python tools/dev/setup.py")

    results = [probe_node(resource, args.node, path, args.timeout) for path in files]
    hits = sum(1 for item in results if item["hit"])

    if args.json:
        print(json.dumps({"node": args.node, "hits": hits, "total": len(results), "results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            mark = "HIT " if item["hit"] else "miss"
            box = item["box"] or "-"
            print(f"[{mark}] {Path(item['image']).name}  box={box}  score={item['score']}")
        print(f"\n{args.node}：{hits}/{len(results)} 命中")
    return 0 if hits == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
