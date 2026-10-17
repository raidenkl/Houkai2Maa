#!/usr/bin/env python3
"""生成 `tests/node-cases` 用例：把「截图 → 命中节点」固化成回归资产。

手工写 node-case 既繁琐又容易写错节点名。这个脚本把 `probe.py` 的能力
批量化：给若干截图和节点名，逐张探测后生成 maa-tools 可直接消费的用例文件。

产物（默认 `tests/node-cases/generated.json`，截图复制到 `tests/node-cases/screens/`）：

```jsonc
{
    "configs": {"name": "generated", "resource": "官服", "controller": "安卓端", "imageRoot": "screens"},
    "cases": [{"image": "home.png", "hits": ["NavHomeFlag"]}]
}
```

用法：

    python tools/dev/nodecase.py --node NavHomeFlag --node DailySignInButton --images shots/home
    python tools/dev/nodecase.py --node SmokeStepA --images tests/fixtures/smoke/screens \\
        --resource tests/fixtures/smoke/resource --out /tmp/case.json --boxes
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
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

from probe import probe_node  # noqa: E402
from static_controller import load_images  # noqa: E402  (保证探测环境与 probe 一致)

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp")
SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


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


def interface_defaults(interface_path: Path) -> tuple[str, str]:
    """取 interface 里第一个 Adb 控制器与第一个资源名，作为用例的 configs。"""

    try:
        data = load_jsonc(interface_path)
    except (JsoncError, OSError):
        return "", ""
    controller = ""
    for item in data.get("controller") or []:
        if isinstance(item, dict) and str(item.get("type", "")).lower() == "adb":
            controller = str(item.get("name", ""))
            break
    resource = ""
    for item in data.get("resource") or []:
        if isinstance(item, dict) and item.get("name"):
            resource = str(item["name"])
            break
    return controller, resource


def copy_screens(files: list[Path], screens_dir: Path) -> list[str]:
    screens_dir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    used: set[str] = set()
    for path in files:
        stem = SAFE_NAME.sub("_", path.stem) or "screen"
        name = f"{stem}{path.suffix.lower()}"
        index = 2
        while name in used:
            name = f"{stem}-{index}{path.suffix.lower()}"
            index += 1
        used.add(name)
        shutil.copyfile(path, screens_dir / name)
        names.append(name)
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从截图生成 maa-tools node-case")
    parser.add_argument("--node", action="append", required=True, help="需要断言的节点名，可重复")
    parser.add_argument("--image", action="append", default=[], help="截图文件，可重复")
    parser.add_argument("--images", action="append", default=[], help="截图目录，可重复")
    parser.add_argument("--resource", default="assets/resource", help="资源包目录（相对仓库根）")
    parser.add_argument("--name", default="generated", help="用例组名（configs.name）")
    parser.add_argument("--out", default="tests/node-cases/generated.json", help="输出 JSON 路径")
    parser.add_argument("--image-root", default="screens", help="截图目录名（相对输出文件所在目录）")
    parser.add_argument("--boxes", action="store_true", help="命中项写成 {node, box} 形式")
    parser.add_argument("--timeout", type=int, default=2000, help="单次识别等待（ms，默认 2000）")
    args = parser.parse_args(argv)

    files = collect_images(list(args.image) + list(args.images))
    resource_dir = REPO_ROOT / args.resource
    if not resource_dir.is_dir():
        raise SystemExit(f"资源目录不存在：{resource_dir}")

    Tasker.set_stdout_level(LoggingLevelEnum.Fatal)
    resource = Resource()
    resource.post_bundle(resource_dir).wait()
    if not resource.loaded:
        raise SystemExit("资源加载失败，请先执行 python tools/dev/setup.py")

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    screens_dir = out_path.parent / args.image_root
    screen_names = copy_screens(files, screens_dir)

    controller_name, resource_name = interface_defaults(REPO_ROOT / "assets" / "interface.json")
    cases: list[dict] = []
    total = 0
    for image_path, screen_name in zip(files, screen_names):
        hits: list = []
        for node in args.node:
            result = probe_node(resource, node, image_path, args.timeout)
            if not result["hit"]:
                continue
            total += 1
            if args.boxes and result["box"]:
                hits.append({"node": node, "box": result["box"]})
            else:
                hits.append(node)
        cases.append({"image": screen_name, "hits": hits})

    payload = {
        "configs": {
            "name": args.name,
            "resource": resource_name,
            "controller": controller_name,
            "imageRoot": args.image_root,
        },
        "cases": cases,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"已生成 {len(cases)} 条用例（共 {len(args.node) * len(files)} 次探测，命中 {total} 次）")
    for case in cases:
        print(f"  {case['image']}: {case['hits'] or '(无命中)'}")
    print(f"用例文件：{out_path}")
    print(f"截图目录：{screens_dir}")
    print("下一步：npm run test:node")
    return 0


if __name__ == "__main__":
    sys.exit(main())
