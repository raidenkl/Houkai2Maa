"""MaaFramework 录制文件（RecordController 产物）的校验与统计。

录制格式来自框架 `include/MaaControlUnit/RecordTypes.h`：
每行一个 JSON，字段 `type / timestamp / success / cost`，另有各类型的参数
（`connect` 的 uuid/width/height、`screencap` 的 path、`click` 的 x/y ...）。
`screencap.path` 相对 JSONL 所在目录解析。

回放前先跑一遍校验，可以把「录制不完整 / 截图丢了 / 分辨率不对」提前暴露，
而不是等到 `ReplayController` 里只报一句模糊错误。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_SIZE = (1280, 720)


@dataclass
class RecordingSummary:
    path: Path
    lines: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    resolution: tuple[int, int] | None = None
    uuid: str = ""
    screenshots: list[Path] = field(default_factory=list)
    missing_screenshots: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_connect(self) -> bool:
        return self.by_type.get("connect", 0) > 0

    @property
    def has_screencap(self) -> bool:
        return self.by_type.get("screencap", 0) > 0

    @property
    def ok(self) -> bool:
        return not self.errors and not self.missing_screenshots and self.has_connect and self.has_screencap

    @property
    def resolution_matches_base(self) -> bool:
        return self.resolution == BASE_SIZE

    def render(self) -> str:
        counts = ", ".join(f"{name}×{count}" for name, count in sorted(self.by_type.items()))
        resolution = f"{self.resolution[0]}x{self.resolution[1]}" if self.resolution else "未知"
        lines = [
            f"录制文件：{self.path}",
            f"  行数 {self.lines}；动作 {counts or '(空)'}",
            f"  设备 {self.uuid or '未知'}；分辨率 {resolution}",
            f"  截图 {len(self.screenshots)} 张（缺失 {len(self.missing_screenshots)} 张）",
        ]
        if self.resolution and not self.resolution_matches_base:
            lines.append("  ! 分辨率不是 1280x720：回放时坐标会与基准不一致，建议重录")
        for missing in self.missing_screenshots:
            lines.append(f"  ! 缺少截图：{missing}")
        for error in self.errors:
            lines.append(f"  ! {error}")
        return "\n".join(lines)


def validate_recording(path: str | Path) -> RecordingSummary:
    file_path = Path(path)
    summary = RecordingSummary(path=file_path)
    if not file_path.is_file():
        summary.errors.append("录制文件不存在")
        return summary

    base_dir = file_path.parent
    with file_path.open(encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            summary.lines += 1
            record = _parse_line(line, lineno, summary)
            if record is None:
                continue

            record_type = str(record.get("type", ""))
            summary.by_type[record_type] = summary.by_type.get(record_type, 0) + 1

            if record_type == "connect":
                width = record.get("width")
                height = record.get("height")
                if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
                    summary.resolution = (width, height)
                summary.uuid = str(record.get("uuid", ""))
            elif record_type == "screencap":
                relative = record.get("path")
                if not isinstance(relative, str) or not relative:
                    summary.errors.append(f"第 {lineno} 行 screencap 缺少 path")
                    continue
                screenshot = base_dir / relative
                summary.screenshots.append(screenshot)
                if not screenshot.is_file():
                    summary.missing_screenshots.append(screenshot)

    if not summary.has_connect:
        summary.errors.append("缺少 connect 记录（无法确定设备分辨率）")
    if not summary.has_screencap:
        summary.errors.append("没有任何 screencap 记录（回放时没有画面可识别）")
    return summary


def _parse_line(line: str, lineno: int, summary: RecordingSummary) -> dict[str, Any] | None:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as error:
        summary.errors.append(f"第 {lineno} 行不是合法 JSON：{error.msg}")
        return None
    if not isinstance(data, dict):
        summary.errors.append(f"第 {lineno} 行必须是 JSON 对象")
        return None
    if not data.get("type"):
        summary.errors.append(f"第 {lineno} 行缺少 type")
        return None
    return data
