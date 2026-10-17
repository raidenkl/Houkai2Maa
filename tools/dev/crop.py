#!/usr/bin/env python3
"""从 720p 截图裁剪模板图，并输出可直接粘贴的 pipeline 节点片段。

为什么需要它：手工「截图 → 裁图 → 量 ROI → 抄坐标」既慢又容易出错，
且一旦截图不是 720p 就会埋下坐标漂移的坑。本脚本把这一串动作做成一条命令，
并在裁剪前校验基准分辨率。

用法：

    # 1) 用 snapshot.py 采集一张 720p 截图（或自己截）
    python tools/dev/snapshot.py

    # 2) 裁剪模板，保存到 image/ 下，并打印节点 JSON
    python tools/dev/crop.py \
        --screen debug/probe/20260101-120000-screen.png \
        --box 980,560,120,60 \
        --out 30_daily/SignIn/button.png \
        --node DailySignInButton \
        --pad 20

    # 非 720p 截图：自动缩放，--box 按**原图**坐标给（工具会换算到 720p）
    python tools/dev/crop.py --screen phone-1080p.png --box 1470,840,180,90 --out 30_daily/X/btn.png
    # 明确禁止缩放（要求原图就是 1280x720）
    python tools/dev/crop.py --screen x.png --box 0,0,100,50 --no-scale

    # 只看 ROI 不落盘
    python tools/dev/crop.py --screen x.png --box 0,0,100,50 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import REPO_ROOT, enable_local_lib  # noqa: E402

enable_local_lib()

IMAGE_DIR = REPO_ROOT / "assets" / "resource" / "image"
BASE_SIZE = (1280, 720)


def parse_box(text: str) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 4 or not all(part.lstrip("-").isdigit() for part in parts):
        raise SystemExit("--box 格式应为 x,y,w,h（整数）")
    x, y, w, h = (int(part) for part in parts)
    if w <= 0 or h <= 0:
        raise SystemExit("--box 宽高必须为正")
    return x, y, w, h


def clamp_box(box: tuple[int, int, int, int], pad: int) -> tuple[int, int, int, int]:
    x, y, w, h = box
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(BASE_SIZE[0], x + w + pad)
    y1 = min(BASE_SIZE[1], y + h + pad)
    return x0, y0, x1 - x0, y1 - y0


def node_snippet(node: str, template: str, roi: tuple[int, int, int, int]) -> dict:
    return {
        node: {
            "recognition": {
                "type": "TemplateMatch",
                "param": {"template": template, "roi": list(roi)},
            },
            "action": {"type": "Click"},
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="裁剪 720p 模板并生成节点片段")
    parser.add_argument("--screen", required=True, help="720p 截图路径")
    parser.add_argument("--box", required=True, help="裁剪区域 x,y,w,h（模板本体）")
    parser.add_argument("--out", help="模板保存路径（相对 assets/resource/image）")
    parser.add_argument("--node", help="节点名，用于生成 JSON 片段")
    parser.add_argument("--pad", type=int, default=20, help="生成 ROI 时向外扩展的像素（默认 20）")
    parser.add_argument("--no-scale", action="store_true", help="要求截图必须是 1280x720，否则报错")
    parser.add_argument("--dry-run", action="store_true", help="只校验并打印，不写文件")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("需要 Pillow 解码截图：python tools/dev/setup.py（开发环境已安装）") from None

    screen_path = Path(args.screen)
    if not screen_path.is_absolute():
        screen_path = REPO_ROOT / screen_path
    if not screen_path.is_file():
        raise SystemExit(f"截图不存在：{screen_path}")

    image = Image.open(screen_path).convert("RGB")
    original_size = image.size
    scale_x = scale_y = 1.0
    if original_size != BASE_SIZE:
        if args.no_scale:
            raise SystemExit(f"截图尺寸 {original_size} 不是 1280x720（--no-scale 已指定）")
        width, height = original_size
        aspect = width / height
        if abs(aspect - BASE_SIZE[0] / BASE_SIZE[1]) > 0.02:
            raise SystemExit(
                f"截图 {original_size} 不是 16:9（{aspect:.3f}），直接缩放会让模板变形；"
                "请用 16:9 的截图（或先裁剪掉黑边）"
            )
        scale_x = BASE_SIZE[0] / width
        scale_y = BASE_SIZE[1] / height
        image = image.resize(BASE_SIZE, Image.LANCZOS)
        print(
            f"[info] 截图 {original_size[0]}x{original_size[1]} 已缩放到 1280x720，"
            f"--box 按原图坐标换算（x×{scale_x:.3f}, y×{scale_y:.3f}）",
            file=sys.stderr,
        )

    original_box = parse_box(args.box)
    if (scale_x, scale_y) != (1.0, 1.0):
        box = (
            round(original_box[0] * scale_x),
            round(original_box[1] * scale_y),
            max(1, round(original_box[2] * scale_x)),
            max(1, round(original_box[3] * scale_y)),
        )
    else:
        box = original_box
    roi = clamp_box(box, args.pad)
    template_rel = args.out or "template.png"
    snippet = node_snippet(args.node or "UnnamedNode", template_rel, roi)
    payload = {
        "screen": str(screen_path.relative_to(REPO_ROOT))
        if screen_path.is_relative_to(REPO_ROOT)
        else str(screen_path),
        "screen_size": list(original_size),
        "box_input": list(original_box),
        "template_box": list(box),
        "roi": list(roi),
        "template": template_rel,
        "node": snippet,
    }

    if not args.dry_run:
        target = IMAGE_DIR / template_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        image.crop((box[0], box[1], box[0] + box[2], box[1] + box[3])).save(target)
        try:
            payload["saved"] = str(target.relative_to(REPO_ROOT))
        except ValueError:  # 模板目录可能被指向仓库外（测试/临时输出）
            payload["saved"] = str(target)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if "saved" in payload:
            print(f"模板已保存：{payload['saved']}")
        print(f"ROI（含 pad={args.pad}）：{roi}")
        print("\n节点片段：\n")
        print(json.dumps(snippet, ensure_ascii=False, indent=4))
    return 0


if __name__ == "__main__":
    sys.exit(main())
