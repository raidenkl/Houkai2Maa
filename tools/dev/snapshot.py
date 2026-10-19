#!/usr/bin/env python3
"""截图 + 全屏 OCR，产出「AI 能读懂」的事实采集包。

两种输入：

* **设备**：连接 ADB，截 720p 图后识别（需要模拟器/手机）；
* **本地图片**：`--image x.png`，对已有截图识别（无需设备）。
  非 1280×720 的图片会先缩放到 720p，所以输出的坐标始终是**基准坐标**。

产物（默认 `debug/probe/`）：

    <name>-screen.png   720p 截图（原图或缩放后）
    <name>-ocr.png      标注图（画框 + 序号）
    <name>-ocr.json     [{"index":1,"text":"签到","box":[x,y,w,h],"score":0.98}, ...]

用法：

    python tools/dev/snapshot.py                          # 第一台 ADB 设备
    python tools/dev/snapshot.py --address 127.0.0.1:16384
    python tools/dev/snapshot.py --image shots/home.png   # 离线分析一张截图
    python tools/dev/snapshot.py --roi 0,0,640,720        # 只识别左半屏
    python tools/dev/snapshot.py --json                   # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import REPO_ROOT, enable_local_lib  # noqa: E402

enable_local_lib()

import numpy  # noqa: E402
from maa.define import LoggingLevelEnum  # noqa: E402
from maa.pipeline import JOCR, JRecognitionType  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "assets" / "agent"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.png import write_png  # noqa: E402
from static_controller import StaticImageController  # noqa: E402

SHORT_SIDE = 720
BASE_SIZE = (1280, 720)


def load_image(path: Path) -> numpy.ndarray:
    """用 Pillow 读图并缩放到 1280×720，返回 BGR uint8 数组（MaaFW 约定）。"""

    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("离线分析需要 Pillow：python tools/dev/setup.py") from None

    with Image.open(path) as source:
        image = source.convert("RGB")
        if image.size != BASE_SIZE:
            print(f"[info] 输入 {image.size[0]}x{image.size[1]}，已缩放到 1280x720", file=sys.stderr)
            image = image.resize(BASE_SIZE, Image.LANCZOS)
        rgb = numpy.asarray(image)
    return rgb[:, :, ::-1].copy()


def capture_from_device(address: str | None, adb_path: str | None) -> tuple[numpy.ndarray, object]:
    """连接设备并截一张 720p 图。返回 (image, controller)，controller 供 Tasker 绑定。"""
    try:
        from maa.controller import AdbController
        from maa.toolkit import Toolkit
    except ImportError as error:
        raise SystemExit(f"缺少 maafw 依赖：{error}") from error

    if address and adb_path:
        adb, target = adb_path, address
    else:
        devices = Toolkit.find_adb_devices()
        if not devices:
            raise SystemExit("未找到 ADB 设备：请启动模拟器/连接手机，或用 --image 分析本地截图。")
        if address:
            matched = [device for device in devices if device.address == address]
            if not matched:
                raise SystemExit(f"没有地址为 {address} 的设备，可用：{', '.join(d.address for d in devices)}")
            device = matched[0]
        else:
            for index, item in enumerate(devices):
                print(f"  [{index}] {item.name} {item.address}", file=sys.stderr)
            device = devices[0]
        adb, target = str(device.adb_path), device.address

    controller = AdbController(adb_path=adb, address=target)
    controller.set_screenshot_target_short_side(SHORT_SIDE)
    controller.post_connection().wait()
    print(f"截图：{target}", file=sys.stderr)
    image = controller.post_screencap().wait().get()
    if image is None:
        raise SystemExit("截图失败")
    return image, controller


def draw_grid(image: numpy.ndarray, step: int = 100) -> numpy.ndarray:
    """叠加坐标网格（100px 一格 + 边缘刻度），方便按截图报坐标。

    需要 Pillow（画文字）；缺失时退化为只画线。
    """

    rgb = image[:, :, ::-1] if image.ndim == 3 and image.shape[2] == 3 else image
    canvas = numpy.ascontiguousarray(rgb.copy())
    height, width = canvas.shape[:2]
    line_color = numpy.array([0, 220, 255], dtype=numpy.uint8)
    for x in range(0, width, step):
        canvas[:, x : x + 1] = line_color
    for y in range(0, height, step):
        canvas[y : y + 1, :] = line_color

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return canvas

    pil = Image.fromarray(canvas)
    draw = ImageDraw.Draw(pil)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    for x in range(0, width, step):
        for y in range(0, height, step):
            draw.text((x + 3, y + 2), f"{x},{y}", fill=(0, 220, 255), font=font)
    return numpy.asarray(pil)


def draw_boxes(image: numpy.ndarray, entries: list[dict]) -> numpy.ndarray:
    """在 RGB 图上画框与序号（纯 numpy，避免引入 Pillow/OpenCV）。"""

    canvas = image.copy()
    height, width = canvas.shape[:2]
    for entry in entries:
        x, y, w, h = entry["box"]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width - 1, x + w), min(height - 1, y + h)
        color = numpy.array([255, 60, 60], dtype=numpy.uint8)
        for thickness in range(2):
            if y0 + thickness < height:
                canvas[y0 + thickness, x0 : x1 + 1] = color
            if y1 - thickness >= 0:
                canvas[y1 - thickness, x0 : x1 + 1] = color
            if x0 + thickness < width:
                canvas[y0 : y1 + 1, x0 + thickness] = color
            if x1 - thickness >= 0:
                canvas[y0 : y1 + 1, x1 - thickness] = color
        label_x = min(width - 4, x0 + 2)
        label_y = min(height - 8, max(0, y0 - 8))
        canvas[label_y : label_y + 6, label_x : label_x + 3 * min(3, len(str(entry["index"])))] = color
    return canvas


def parse_roi(text: str | None) -> tuple[int, int, int, int]:
    if not text:
        return (0, 0, 0, 0)
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 4 or not all(part.lstrip("-").isdigit() for part in parts):
        raise SystemExit("--roi 格式应为 x,y,w,h")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="截图 + 全屏 OCR（事实采集）")
    parser.add_argument("--image", help="离线分析本地图片（缩放至 720p），不连接设备")
    parser.add_argument("--address", help="ADB 设备地址，如 127.0.0.1:16384")
    parser.add_argument("--adb", help="adb 可执行文件路径")
    parser.add_argument("--roi", help="OCR 区域 x,y,w,h（默认全屏）")
    parser.add_argument("--out", default="debug/probe", help="输出目录（默认 debug/probe）")
    parser.add_argument("--grid", action="store_true", help="额外输出一张带坐标网格的截图（便于按图报坐标）")
    parser.add_argument("--json", action="store_true", help="把结果以 JSON 打印到 stdout")
    args = parser.parse_args(argv)

    roi = parse_roi(args.roi)

    resource = Resource()
    resource.post_bundle(REPO_ROOT / "assets" / "resource").wait()
    if not resource.loaded:
        raise SystemExit("资源加载失败：请先执行 python tools/dev/setup.py（准备 OCR 模型）")

    if args.image:
        source = Path(args.image)
        if not source.is_absolute():
            source = REPO_ROOT / source
        if not source.is_file():
            raise SystemExit(f"图片不存在：{source}")
        image = load_image(source)
        # 离线分析时把图片本身当作「设备」
        controller = StaticImageController([image], cycle=False)
        controller.post_connection().wait()
        stem = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{source.stem}"
    else:
        image, controller = capture_from_device(args.address, args.adb)
        stem = datetime.now().strftime("%Y%m%d-%H%M%S")

    height, width = image.shape[:2]
    if (width, height) != BASE_SIZE:
        print(f"[warn] 截图尺寸 {width}x{height} 不是 1280x720，坐标可能偏移", file=sys.stderr)

    print("识别文字 ...", file=sys.stderr)
    Tasker.set_stdout_level(LoggingLevelEnum.Fatal)
    tasker = Tasker()
    # 识别需要 Tasker 绑定资源与控制器（设备模式同样必须绑定，否则 Tasker 未初始化、OCR 静默返回空）
    tasker.bind(resource, controller)
    task_detail = tasker.post_recognition(JRecognitionType.OCR, JOCR(roi=roi), image).wait().get()
    detail = None
    if task_detail is not None:
        for node in task_detail.nodes:
            if node.recognition is not None:
                detail = node.recognition
                break
    if detail is None:
        print("[warn] OCR 未返回结果（Tasker/资源未就绪？），后续产物将是空的", file=sys.stderr)

    entries: list[dict] = []
    if detail is not None:
        for index, result in enumerate(detail.filtered_results or detail.all_results, start=1):
            text = getattr(result, "text", "")
            box = getattr(result, "box", None)
            score = getattr(result, "score", 0.0)
            if box is None or not text:
                continue
            coords = (
                [box.x, box.y, box.w, box.h]
                if hasattr(box, "x")
                else [int(value) for value in (box[0], box[1], box[2], box[3])]
            )
            entries.append(
                {
                    "index": index,
                    "text": text,
                    "box": coords,
                    "score": round(float(score), 4),
                }
            )

    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    screen_path = out_dir / f"{stem}-screen.png"
    ocr_png_path = out_dir / f"{stem}-ocr.png"
    ocr_json_path = out_dir / f"{stem}-ocr.json"

    write_png(screen_path, image)
    write_png(ocr_png_path, draw_boxes(image[:, :, ::-1], entries), bgr=False)
    grid_path = None
    if args.grid:
        grid_path = out_dir / f"{stem}-grid.png"
        write_png(grid_path, draw_grid(image), bgr=False)
    ocr_json_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({"screen": str(screen_path), "ocr": entries}, ensure_ascii=False, indent=2))
    else:
        for entry in entries:
            x, y, w, h = entry["box"]
            print(f"[{entry['index']:>2}] ({x:>4},{y:>3},{w:>4},{h:>3})  {entry['text']}")
        print(f"\n截图：{screen_path.relative_to(REPO_ROOT)}")
        print(f"标注：{ocr_png_path.relative_to(REPO_ROOT)}")
        if grid_path is not None:
            print(f"网格：{grid_path.relative_to(REPO_ROOT)}")
        print(f"文本：{ocr_json_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
