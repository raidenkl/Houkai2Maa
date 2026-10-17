#!/usr/bin/env python3
"""设备截图 + 全屏 OCR，产出「AI 能读懂」的事实采集包。

不用 `uvx maafw-cli` 也能跑（直接走仓库内 `.pylib` 的 maafw 绑定），
适合在没有 uv、或需要离线批量采集的环境。

产物（默认 `debug/probe/`）：

    <ts>-screen.png   720p 原始截图
    <ts>-ocr.png      标注图（画框 + 序号），方便人眼对照
    <ts>-ocr.json     [{"index":1,"text":"签到","box":[x,y,w,h],"score":0.98}, ...]

用法：

    python tools/dev/snapshot.py                       # 用第一台 ADB 设备
    python tools/dev/snapshot.py --address 127.0.0.1:16384
    python tools/dev/snapshot.py --roi 0,0,640,720     # 只识别左半屏
    python tools/dev/snapshot.py --json                # 结果输出为 JSON
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
from maa.controller import AdbController  # noqa: E402
from maa.pipeline import JOCR, JRecognitionType  # noqa: E402
from maa.resource import Resource  # noqa: E402
from maa.tasker import Tasker  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "agent"))
from common.png import write_png  # noqa: E402

SHORT_SIDE = 720
BASE_SIZE = (1280, 720)


def pick_device(address: str | None, adb_path: str | None) -> tuple[str, str]:
    if address and adb_path:
        return adb_path, address

    devices = Toolkit.find_adb_devices()
    if not devices:
        raise SystemExit("未找到 ADB 设备：请启动模拟器 / 连接手机后重试，或用 --adb/--address 指定。")

    if address:
        for device in devices:
            if device.address == address:
                return str(device.adb_path), device.address
        raise SystemExit("没有地址为 %s 的设备，可用：%s" % (address, ", ".join(d.address for d in devices)))

    for index, device in enumerate(devices):
        print(f"  [{index}] {device.name} {device.address}", file=sys.stderr)
    device = devices[0]
    return str(device.adb_path), device.address


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
        # 序号：在左上角画 3x5 的实心小块，避免依赖字体
        label_x = min(width - 4, x0 + 2)
        label_y = min(height - 8, max(0, y0 - 8))
        canvas[label_y : label_y + 6, label_x : label_x + 3 * min(3, len(str(entry["index"])))] = color
    return canvas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="设备截图 + 全屏 OCR（事实采集）")
    parser.add_argument("--address", help="ADB 设备地址，如 127.0.0.1:16384")
    parser.add_argument("--adb", help="adb 可执行文件路径")
    parser.add_argument("--roi", help="OCR 区域 x,y,w,h（默认全屏）")
    parser.add_argument("--out", default="debug/probe", help="输出目录（默认 debug/probe）")
    parser.add_argument("--json", action="store_true", help="把结果以 JSON 打印到 stdout")
    args = parser.parse_args(argv)

    roi = (0, 0, 0, 0)
    if args.roi:
        parts = [part.strip() for part in args.roi.split(",")]
        if len(parts) != 4 or not all(part.lstrip("-").isdigit() for part in parts):
            raise SystemExit("--roi 格式应为 x,y,w,h")
        roi = tuple(int(part) for part in parts)  # type: ignore[assignment]

    resource = Resource()
    resource.post_bundle(REPO_ROOT / "assets" / "resource").wait()
    if not resource.loaded:
        raise SystemExit("资源加载失败：请先执行 python tools/dev/setup.py（准备 OCR 模型）")

    adb_path, address = pick_device(args.address, args.adb)
    controller = AdbController(adb_path=adb_path, address=address)
    controller.set_screenshot_target_short_side(SHORT_SIDE)
    controller.post_connection().wait()

    tasker = Tasker()
    tasker.bind(resource, controller)

    print(f"截图：{address}", file=sys.stderr)
    image = controller.post_screencap().wait().get()
    if image is None:
        raise SystemExit("截图失败")
    height, width = image.shape[:2]
    if (width, height) != BASE_SIZE:
        print(
            f"[warn] 截图尺寸 {width}x{height} 与基准 1280x720 不一致，"
            "请把模拟器分辨率设为 1280x720（16:9）后重新采集",
            file=sys.stderr,
        )

    print("识别文字 ...", file=sys.stderr)
    detail = tasker.post_recognition(JRecognitionType.OCR, JOCR(roi=roi), image).wait().get()
    entries: list[dict] = []
    if detail is not None:
        for index, result in enumerate(detail.filtered_results or detail.all_results, start=1):
            text = getattr(result, "text", "")
            box = getattr(result, "box", None)
            score = getattr(result, "score", 0.0)
            if box is None or not text:
                continue
            entries.append(
                {
                    "index": index,
                    "text": text,
                    "box": [box.x, box.y, box.w, box.h],
                    "score": round(float(score), 4),
                }
            )

    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    screen_path = out_dir / f"{stamp}-screen.png"
    ocr_png_path = out_dir / f"{stamp}-ocr.png"
    ocr_json_path = out_dir / f"{stamp}-ocr.json"

    write_png(screen_path, image)
    write_png(ocr_png_path, draw_boxes(image[:, :, ::-1], entries), bgr=False)
    ocr_json_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps({"screen": str(screen_path), "ocr": entries}, ensure_ascii=False, indent=2))
    else:
        for entry in entries:
            x, y, w, h = entry["box"]
            print(f"[{entry['index']:>2}] ({x:>4},{y:>3},{w:>4},{h:>3})  {entry['text']}")
        print(f"\n截图：{screen_path.relative_to(REPO_ROOT)}")
        print(f"标注：{ocr_png_path.relative_to(REPO_ROOT)}")
        print(f"文本：{ocr_json_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
