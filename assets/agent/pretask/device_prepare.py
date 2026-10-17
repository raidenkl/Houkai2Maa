#!/usr/bin/env python3
"""预任务：启动 Controller 之前检查设备分辨率是否符合 720p 基准。

由 `interface.json` 的 `pretask` 调用（PI v2.7+，MaaXYZ/MFAAvalonia 已支持）：

    "pretask": {
        "name": "DevicePrepare",
        "exec": "python",
        "args": ["./agent/pretask/device_prepare.py"],
        "controller": ["安卓端"]
    }

为什么值得单独一步：分辨率不对时，所有 ROI/模板都会整体偏移，现象是
「明明有按钮却识别不到」，排查成本很高。这里在开跑前就把原因说清楚。

行为：

* 先读 `MAAHOUKAI2_ADB_ADDRESS`（可选，多设备时用它指定目标）；
* 找 ADB 设备 → 连接 → 截一张 720p 图 → 校验尺寸；
* 只有**一台**设备时严格检查：不符合 → 退出 1（Client 会中止启动）；
* 有多台设备且未指定地址时只告警、退出 0（避免误判无关设备，把启动卡死）；
* 没有设备 → 退出 1 并提示先启动模拟器；
* `PI_CONTROLLER`（Agent 才会注入）若存在且非 Adb，直接跳过。

注意：MFAAvalonia 执行 pretask 时**不会**注入 `PI_*` 环境变量，
控制器过滤由 interface 里的 `pretask.controller` 字段完成。

也支持离线校验单张截图：`python agent/pretask/device_prepare.py --image x.png`
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.frame import evaluate_frame, read_png_size  # noqa: E402

SHORT_SIDE = 720


def log(message: str) -> None:
    print(f"[device_prepare] {message}")


def controller_type() -> str:
    raw = os.environ.get("PI_CONTROLLER")
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    return str(data.get("type", "")) if isinstance(data, dict) else ""


def check_image(path: Path) -> int:
    size = read_png_size(path)
    if size is None:
        try:
            from PIL import Image

            with Image.open(path) as image:
                size = image.size
        except ImportError:
            log("非 PNG 图片需要 Pillow：python -m pip install pillow")
            return 1
        except OSError as error:
            log(f"无法读取图片：{error}")
            return 1
    width, height = size
    check = evaluate_frame(width, height)
    log(f"{path.name}: {check.message}")
    return 0 if check.ok else 1


def check_device() -> int:
    try:
        from maa.controller import AdbController
        from maa.toolkit import Toolkit
    except ImportError:
        log("缺少 maafw：python -m pip install -r agent/requirements.txt")
        return 1

    devices = Toolkit.find_adb_devices()
    if not devices:
        log("未找到 ADB 设备：请先启动模拟器或连接手机，并确认 adb devices 能看到设备")
        return 1

    for index, item in enumerate(devices):
        log(f"设备 [{index}] {item.name} {item.address}")

    wanted = os.environ.get("MAAHOUKAI2_ADB_ADDRESS", "").strip()
    if wanted:
        matched = [item for item in devices if item.address == wanted]
        if not matched:
            log(f"MAAHOUKAI2_ADB_ADDRESS={wanted} 不在设备列表里，已发现：{', '.join(d.address for d in devices)}")
            return 1
        device = matched[0]
    elif len(devices) > 1:
        log(
            f"检测到 {len(devices)} 台 ADB 设备，无法确定实际使用哪台；跳过严格检查。"
            "如需强制检查，设置环境变量 MAAHOUKAI2_ADB_ADDRESS=<地址>"
        )
        return 0
    else:
        device = devices[0]
    log(f"检查设备 {device.name}（{device.address}）")
    controller = AdbController(adb_path=str(device.adb_path), address=device.address)
    controller.set_screenshot_target_short_side(SHORT_SIDE)
    controller.post_connection().wait()

    image = controller.post_screencap().wait().get()
    if image is None:
        log("截图失败：请确认游戏/模拟器画面正常")
        return 1

    height, width = image.shape[:2]
    check = evaluate_frame(int(width), int(height))
    log(check.message)
    if not check.ok:
        log("提示：MuMu 12 等模拟器可在「设置 → 显示 → 分辨率」选择 1280x720（或自定义 16:9）")
    return 0 if check.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="启动前检查截图分辨率是否符合 720p 基准")
    parser.add_argument("--image", help="离线校验一张截图（不连接设备）")
    args = parser.parse_args(argv)

    if args.image:
        return check_image(Path(args.image))

    current = controller_type()
    if current and current.lower() != "adb":
        log(f"当前控制器类型为 {current}，跳过 ADB 分辨率检查")
        return 0

    return check_device()


if __name__ == "__main__":
    sys.exit(main())
