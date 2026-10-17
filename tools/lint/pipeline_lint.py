#!/usr/bin/env python3
"""Houkai2Maa 流水线静态检查。

`@nekosu/maa-tools check` 负责「框架语义」层面的检查（任务树、图片路径、schema 等）。
本脚本只负责**本项目自己的约定**，这些约定写不进 JSON Schema：

1. 坐标基准 1280x720（16:9），ROI 不得越界；
2. 模板图片存在、PNG 尺寸合理、扩展名小写、无未引用图片；
3. 禁止 v1 弃用字段，统一使用 Pipeline v2（`recognition` / `action` 为对象）；
4. 禁止 >1000ms 的固定延迟（改用 `pre_wait_freezes` / 中间识别节点）；
5. 命名规范：ASCII PascalCase，内部节点 `__` 前缀；
6. 业务层入口节点必须带 `[JumpBack]` 兜底；
7. `Custom` 识别/动作的 ID 必须在 `agent/` 中真实注册；
8. interface / tasks 引用完整性（entry、pipeline_override、import）。

用法：

    python tools/lint/pipeline_lint.py            # 只把 error 视为失败
    python tools/lint/pipeline_lint.py --strict   # warning 也算失败（CI 用）
    python tools/lint/pipeline_lint.py --json     # 机器可读输出
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.jsonc import JsoncError, load_jsonc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCE_DIR = REPO_ROOT / "assets" / "resource"
PIPELINE_DIR = RESOURCE_DIR / "pipeline"
IMAGE_DIR = RESOURCE_DIR / "image"
AGENT_DIR = REPO_ROOT / "agent"
INTERFACE_FILE = REPO_ROOT / "assets" / "interface.json"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "allowlist.json"
TASKS_DIR = INTERFACE_FILE.parent / "tasks"

BASE_WIDTH = 1280
BASE_HEIGHT = 720
MAX_DELAY_MS = 1000
MIN_RATE_LIMIT = 100
MAX_TEMPLATE_WIDTH = BASE_WIDTH // 2
MAX_TEMPLATE_HEIGHT = BASE_HEIGHT // 2
MIN_TEMPLATE_SIDE = 4

BUSINESS_DIR_PREFIXES = ("30_daily", "90_activity")


def _load_allowlist() -> dict[str, dict[str, list[str]]]:
    if not ALLOWLIST_FILE.is_file():
        return {}
    try:
        data = load_jsonc(ALLOWLIST_FILE)
    except JsoncError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(code): {str(file): [str(node) for node in nodes] for file, nodes in rules.items()}
        for code, rules in data.items()
        if isinstance(rules, dict)
    }


ALLOWLIST = _load_allowlist()
DEPRECATED_FIELDS = ("is_sub", "timeout_next", "package_doc", "template_doc")
POINT_FIELDS = ("target", "begin", "end", "target_offset", "begin_offset", "end_offset")

NODE_NAME_RE = re.compile(r"^(?:__)?[A-Za-z][A-Za-z0-9_]*$")
PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
JUMP_BACK_PREFIX = "["

CUSTOM_ACTION_RE = re.compile(r"custom_action\(\s*[\"']([^\"']+)[\"']")
CUSTOM_RECOGNITION_RE = re.compile(r"custom_recognition\(\s*[\"']([^\"']+)[\"']")


@dataclass
class Diagnostic:
    severity: str  # "error" | "warning"
    code: str
    message: str
    file: str = ""
    line: int = 0
    node: str = ""

    def render(self) -> str:
        location = self.file
        if self.line:
            location += f":{self.line}"
        if self.node:
            location += f" [{self.node}]"
        return f"{location} ({self.severity}) {self.code} {self.message}"


@dataclass
class Node:
    name: str
    data: dict
    file: Path
    line: int
    business: bool


@dataclass
class LintContext:
    diagnostics: list[Diagnostic] = field(default_factory=list)
    allowed: list[Diagnostic] = field(default_factory=list)
    nodes: dict[str, Node] = field(default_factory=dict)
    duplicate_files: dict[str, list[Path]] = field(default_factory=dict)
    referenced_templates: set[str] = field(default_factory=set)

    def _allowed(self, code: str, file: str, node: str) -> bool:
        entries = ALLOWLIST.get(code)
        if not entries:
            return False
        return node in entries.get(file, [])

    def error(self, code: str, message: str, **kwargs) -> None:
        diagnostic = Diagnostic("error", code, message, **kwargs)
        if self._allowed(code, diagnostic.file, diagnostic.node):
            self.allowed.append(diagnostic)
            return
        self.diagnostics.append(diagnostic)

    def warn(self, code: str, message: str, **kwargs) -> None:
        diagnostic = Diagnostic("warning", code, message, **kwargs)
        if self._allowed(code, diagnostic.file, diagnostic.node):
            self.allowed.append(diagnostic)
            return
        self.diagnostics.append(diagnostic)

    @property
    def errors(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [item for item in self.diagnostics if item.severity == "warning"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def node_line_index(text: str) -> dict[str, int]:
    """节点名 -> 行号（用于把诊断定位到源码）。"""

    index: dict[str, int] = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        match = re.match(r'\s*"([^"]+)"\s*:', raw)
        if match:
            index.setdefault(match.group(1), lineno)
    return index


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def next_entries(value) -> list[tuple[str, bool]]:
    """把 next / on_error 归一化为 (节点名, 是否 jump_back)。"""

    entries: list[tuple[str, bool]] = []
    for item in as_list(value):
        if isinstance(item, str):
            if item.startswith(JUMP_BACK_PREFIX):
                name = item
                while name and name[0] in "[":  # 兼容 [JumpBack] / [Anchor]
                    end = name.find("]")
                    if end == -1:
                        break
                    name = name[end + 1 :]
                entries.append((name, True))
            else:
                entries.append((item, False))
        elif isinstance(item, dict):
            name = item.get("name", "")
            if name:
                entries.append((str(name), bool(item.get("jump_back") or item.get("anchor"))))
    return entries


def v2_param(node: dict, key: str) -> dict:
    section = node.get(key)
    if isinstance(section, dict):
        param = section.get("param")
        if isinstance(param, dict):
            return param
    return {}


def section_type(node: dict, key: str) -> str:
    section = node.get(key)
    if isinstance(section, dict):
        return str(section.get("type", "")) or ""
    if isinstance(section, str):
        return section
    return ""


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        header = path.read_bytes()[:24]
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def is_business_file(path: Path) -> bool:
    return any(part.startswith(prefix) for part in path.parts for prefix in BUSINESS_DIR_PREFIXES)


# --------------------------------------------------------------------------- #
# pipeline checks
# --------------------------------------------------------------------------- #


def collect_nodes(ctx: LintContext) -> None:
    pipeline_files = sorted(PIPELINE_DIR.rglob("*.json"))
    if not pipeline_files:
        ctx.warn("W000", "未找到任何 pipeline 文件", file=str(PIPELINE_DIR.relative_to(REPO_ROOT)))
        return

    for path in pipeline_files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
            data = load_jsonc(path)
        except JsoncError as error:
            ctx.error("E001", f"JSONC 解析失败：{error}", file=rel)
            continue

        if not isinstance(data, dict):
            ctx.error("E002", "pipeline 文件顶层必须是对象", file=rel)
            continue

        line_index = node_line_index(text)
        business = is_business_file(path.relative_to(PIPELINE_DIR))
        for name, node_data in data.items():
            if name.startswith("$"):
                continue
            if not isinstance(node_data, dict):
                ctx.error("E003", "节点定义必须是对象", file=rel, node=name)
                continue
            if name in ctx.nodes:
                ctx.duplicate_files.setdefault(name, [ctx.nodes[name].file]).append(path)
                ctx.error("E201", f"节点名重复，已存在于 {ctx.nodes[name].file.relative_to(REPO_ROOT)}", file=rel, node=name)
                continue
            ctx.nodes[name] = Node(name=name, data=node_data, file=path, line=line_index.get(name, 0), business=business)


def check_node_shape(ctx: LintContext, node: Node) -> None:
    rel = node.file.relative_to(REPO_ROOT).as_posix()
    data = node.data

    if not NODE_NAME_RE.match(node.name):
        ctx.error("E004", "节点名必须是 ASCII（字母/数字/下划线），内部节点用 `__` 前缀", file=rel, node=node.name, line=node.line)
    elif not node.name.startswith("__") and not PASCAL_CASE_RE.match(node.name):
        ctx.warn("W004", "节点名建议使用 PascalCase", file=rel, node=node.name, line=node.line)

    for key in DEPRECATED_FIELDS:
        if key in data:
            ctx.error("E104", f"禁止使用 v1 弃用字段 `{key}`", file=rel, node=node.name, line=node.line)

    for key in ("recognition", "action"):
        if isinstance(data.get(key), str):
            ctx.error("E010", f"`{key}` 必须使用 v2 对象形式 `{{type, param}}`", file=rel, node=node.name, line=node.line)

    for key, code in (("pre_delay", "E105"), ("post_delay", "E105")):
        value = data.get(key)
        if isinstance(value, (int, float)) and value > MAX_DELAY_MS:
            ctx.error(
                code,
                f"`{key}={value}ms` 超过 {MAX_DELAY_MS}ms，请改用 pre_wait_freezes/post_wait_freezes 或中间识别节点",
                file=rel,
                node=node.name,
                line=node.line,
            )

    rate_limit = data.get("rate_limit")
    if isinstance(rate_limit, (int, float)) and rate_limit < MIN_RATE_LIMIT:
        ctx.warn("W101", f"`rate_limit={rate_limit}ms` 过小，可能造成频繁截图", file=rel, node=node.name, line=node.line)


def check_coordinates(ctx: LintContext, node: Node) -> None:
    """`target` / `begin` / `end` 等坐标字段必须在 720p 基准内。"""

    rel = node.file.relative_to(REPO_ROOT).as_posix()
    param = v2_param(node.data, "action")
    for field_name in POINT_FIELDS:
        value = param.get(field_name, node.data.get(field_name))
        if value is None or isinstance(value, (bool, str)):
            continue
        candidates = value if isinstance(value, list) and value and isinstance(value[0], list) else [value]
        for candidate in candidates:
            if not isinstance(candidate, list) or len(candidate) not in (2, 4):
                ctx.error(
                    "E111",
                    f"`{field_name}` 必须是 [x, y] 或 [x, y, w, h]：{candidate}",
                    file=rel,
                    node=node.name,
                    line=node.line,
                )
                continue
            if not all(isinstance(item, int) for item in candidate):
                ctx.error("E111", f"`{field_name}` 必须全为整数：{candidate}", file=rel, node=node.name, line=node.line)
                continue
            x, y = candidate[0], candidate[1]
            width = candidate[2] if len(candidate) == 4 else 1
            height = candidate[3] if len(candidate) == 4 else 1
            if x < 0 or y < 0 or x + width > BASE_WIDTH or y + height > BASE_HEIGHT:
                ctx.error(
                    "E111",
                    f"`{field_name}` 超出 {BASE_WIDTH}x{BASE_HEIGHT} 基准：{candidate}",
                    file=rel,
                    node=node.name,
                    line=node.line,
                )


def check_action_params(ctx: LintContext, node: Node) -> None:
    """动作必填参数与类型检查。"""

    rel = node.file.relative_to(REPO_ROOT).as_posix()
    action_type = section_type(node.data, "action")
    param = v2_param(node.data, "action")

    if action_type in ("StartApp", "StopApp"):
        package = param.get("package", node.data.get("package"))
        if not isinstance(package, str) or not package.strip():
            ctx.error("E216", f"`{action_type}` 需要非空 `package`", file=rel, node=node.name, line=node.line)
    if action_type == "Shell":
        cmd = param.get("cmd", node.data.get("cmd"))
        if not isinstance(cmd, str) or not cmd.strip():
            ctx.error("E216", "`Shell` 需要非空 `cmd`", file=rel, node=node.name, line=node.line)
    if action_type == "Custom":
        if not isinstance(param.get("custom_action"), str):
            ctx.error("E204", "Custom 动作缺少字符串型 `custom_action`", file=rel, node=node.name, line=node.line)

    max_hit = node.data.get("max_hit")
    if max_hit is not None and (not isinstance(max_hit, int) or isinstance(max_hit, bool) or max_hit <= 0):
        ctx.error("E214", f"`max_hit` 必须是正整数，实际 {max_hit!r}", file=rel, node=node.name, line=node.line)
    enabled = node.data.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        ctx.error("E214", f"`enabled` 必须是布尔值，实际 {enabled!r}", file=rel, node=node.name, line=node.line)


def check_self_loop(ctx: LintContext, node: Node) -> None:
    """节点在 next/on_error 里引用自己时必须配 `max_hit`，否则可能无限循环。"""

    rel = node.file.relative_to(REPO_ROOT).as_posix()
    for field_name in ("next", "on_error"):
        for target, _ in next_entries(node.data.get(field_name)):
            if target == node.name and not node.data.get("max_hit"):
                ctx.warn(
                    "W211",
                    f"`{field_name}` 引用了自身且没有 `max_hit`，存在死循环风险",
                    file=rel,
                    node=node.name,
                    line=node.line,
                )


def check_ocr_expected(ctx: LintContext, node: Node) -> None:
    """OCR 的 `expected` 质量：过短会误命中。"""

    if section_type(node.data, "recognition") != "OCR":
        return
    rel = node.file.relative_to(REPO_ROOT).as_posix()
    param = v2_param(node.data, "recognition")
    expected = param.get("expected", node.data.get("expected"))
    if expected is None:
        ctx.warn("W212", "OCR 未设置 `expected`，会匹配任意文本", file=rel, node=node.name, line=node.line)
        return
    for item in as_list(expected):
        if not isinstance(item, str):
            ctx.error("W212", f"OCR `expected` 含非字符串项 {item!r}", file=rel, node=node.name, line=node.line)
            continue
        if len(item.strip()) <= 1:
            ctx.warn(
                "W213",
                f"OCR `expected` 过短（{item!r}），建议写完整按钮文案",
                file=rel,
                node=node.name,
                line=node.line,
            )


def check_templates(ctx: LintContext, node: Node) -> None:
    rel = node.file.relative_to(REPO_ROOT).as_posix()
    param = v2_param(node.data, "recognition")
    templates = as_list(param.get("template", node.data.get("template")))
    for template in templates:
        if not isinstance(template, str):
            continue
        ctx.referenced_templates.add(template)
        path = IMAGE_DIR / template
        if path.suffix != path.suffix.lower():
            ctx.error("E102", f"图片扩展名必须小写：`{template}`", file=rel, node=node.name, line=node.line)
        if not path.is_file():
            ctx.error("E101", f"模板图片不存在：`image/{template}`", file=rel, node=node.name, line=node.line)
            continue
        size = png_size(path)
        if size is None:
            ctx.error("E108", f"模板图片不是合法 PNG：`image/{template}`", file=rel, node=node.name, line=node.line)
            continue
        width, height = size
        if width < MIN_TEMPLATE_SIDE or height < MIN_TEMPLATE_SIDE:
            ctx.error("E108", f"模板过小（{width}x{height}）：`image/{template}`", file=rel, node=node.name, line=node.line)
        if width > MAX_TEMPLATE_WIDTH or height > MAX_TEMPLATE_HEIGHT:
            ctx.warn(
                "W108",
                f"模板过大（{width}x{height}）：`image/{template}`，建议缩小 ROI 后重新裁剪",
                file=rel,
                node=node.name,
                line=node.line,
            )


def check_roi(ctx: LintContext, node: Node) -> None:
    rel = node.file.relative_to(REPO_ROOT).as_posix()
    param = v2_param(node.data, "recognition")
    roi = param.get("roi", node.data.get("roi"))
    if roi is None:
        return
    candidates = roi if isinstance(roi, list) and roi and isinstance(roi[0], list) else [roi]
    for candidate in candidates:
        if not isinstance(candidate, list) or len(candidate) != 4:
            ctx.error("E103", f"roi 必须是 [x, y, w, h]：{candidate}", file=rel, node=node.name, line=node.line)
            continue
        x, y, width, height = (int(value) for value in candidate)
        if width == 0 and height == 0:
            continue  # 全屏
        if width <= 0 or height <= 0:
            ctx.error("E103", f"roi 宽高必须为正：{candidate}", file=rel, node=node.name, line=node.line)
            continue
        if x < 0 or y < 0 or x + width > BASE_WIDTH or y + height > BASE_HEIGHT:
            ctx.error(
                "E103",
                f"roi 超出 {BASE_WIDTH}x{BASE_HEIGHT} 基准：{candidate}",
                file=rel,
                node=node.name,
                line=node.line,
            )


def check_custom_ids(ctx: LintContext, node: Node, registered_actions: set[str], registered_recognitions: set[str]) -> None:
    rel = node.file.relative_to(REPO_ROOT).as_posix()
    recognition_param = v2_param(node.data, "recognition")
    if section_type(node.data, "recognition") == "Custom":
        custom = recognition_param.get("custom_recognition")
        if not custom:
            ctx.error("E204", "Custom 识别缺少 `custom_recognition`", file=rel, node=node.name, line=node.line)
        elif custom not in registered_recognitions:
            ctx.error("E204", f"自定义识别 `{custom}` 未在 agent/ 注册", file=rel, node=node.name, line=node.line)

    action_param = v2_param(node.data, "action")
    if section_type(node.data, "action") == "Custom":
        custom = action_param.get("custom_action")
        if not custom:
            ctx.error("E204", "Custom 动作缺少 `custom_action`", file=rel, node=node.name, line=node.line)
        elif custom not in registered_actions:
            ctx.error("E204", f"自定义动作 `{custom}` 未在 agent/ 注册", file=rel, node=node.name, line=node.line)


def check_business_entry(ctx: LintContext, node: Node) -> None:
    if not node.business or not node.name.endswith("Entry"):
        return
    rel = node.file.relative_to(REPO_ROOT).as_posix()
    has_fallback = any(jump_back for _, jump_back in next_entries(node.data.get("next"))) or any(
        jump_back for _, jump_back in next_entries(node.data.get("on_error"))
    )
    if not has_fallback:
        ctx.error(
            "E203",
            "业务入口节点的 next 必须包含 `[JumpBack]` 兜底（弹窗/加载/回导航）",
            file=rel,
            node=node.name,
            line=node.line,
        )


def check_graph(ctx: LintContext, entries: set[str]) -> None:
    graph: dict[str, list[str]] = {}
    for name, node in ctx.nodes.items():
        targets: list[str] = []
        for key in ("next", "on_error"):
            targets.extend(target for target, _ in next_entries(node.data.get(key)))
        graph[name] = targets

    for name, targets in graph.items():
        node = ctx.nodes[name]
        rel = node.file.relative_to(REPO_ROOT).as_posix()
        for target in targets:
            if target and target not in ctx.nodes:
                ctx.error("E205", f"引用了不存在的节点 `{target}`", file=rel, node=name, line=node.line)

    reachable: set[str] = set()
    stack = [entry for entry in entries if entry in ctx.nodes]
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(target for target in graph.get(current, []) if target in ctx.nodes)

    for name, node in ctx.nodes.items():
        if entries and name not in reachable:
            rel = node.file.relative_to(REPO_ROOT).as_posix()
            ctx.warn("W200", "节点不可达（不在任何 entry 的子图中）", file=rel, node=name, line=node.line)


def check_unused_templates(ctx: LintContext) -> None:
    for path in sorted(IMAGE_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".png":
            continue
        rel = path.relative_to(IMAGE_DIR).as_posix()
        if rel not in ctx.referenced_templates:
            ctx.warn("W210", f"图片未被任何节点引用：`image/{rel}`", file=path.relative_to(REPO_ROOT).as_posix())


# --------------------------------------------------------------------------- #
# interface / tasks checks
# --------------------------------------------------------------------------- #


def load_interface(ctx: LintContext) -> set[str]:
    entries: set[str] = set()
    if not INTERFACE_FILE.is_file():
        ctx.error("E005", "缺少 assets/interface.json", file="assets/interface.json")
        return entries

    try:
        interface = load_jsonc(INTERFACE_FILE)
    except JsoncError as error:
        ctx.error("E001", f"interface.json 解析失败：{error}", file="assets/interface.json")
        return entries

    for task in as_list(interface.get("task")):
        if isinstance(task, dict) and task.get("entry"):
            entries.add(str(task["entry"]))

    for import_path in as_list(interface.get("import")):
        imported = (INTERFACE_FILE.parent / str(import_path)).resolve()
        if not imported.is_file():
            ctx.error("E207", f"import 文件不存在：`{import_path}`", file="assets/interface.json")
            continue
        try:
            fragment = load_jsonc(imported)
        except JsoncError as error:
            ctx.error("E001", f"{import_path} 解析失败：{error}", file=import_path)
            continue
        for task in as_list(fragment.get("task")):
            if isinstance(task, dict) and task.get("entry"):
                entries.add(str(task["entry"]))

    for name in entries:
        if name not in ctx.nodes:
            ctx.error("E206", f"interface 任务 entry 指向不存在的节点 `{name}`", file="assets/interface.json")

    for controller in as_list(interface.get("controller")):
        if not isinstance(controller, dict):
            continue
        if str(controller.get("type", "")).lower() != "adb":
            continue
        short_side = controller.get("display_short_side")
        if short_side != BASE_HEIGHT:
            ctx.error(
                "E110",
                f"Adb 控制器 `{controller.get('name')}` 的 display_short_side 必须是 {BASE_HEIGHT}（当前 {short_side!r}）",
                file="assets/interface.json",
            )

    group_names = {
        str(group.get("name"))
        for group in as_list(interface.get("group"))
        if isinstance(group, dict) and group.get("name")
    }
    resource_names = {
        str(resource.get("name"))
        for resource in as_list(interface.get("resource"))
        if isinstance(resource, dict) and resource.get("name")
    }
    controller_names = {
        str(controller.get("name"))
        for controller in as_list(interface.get("controller"))
        if isinstance(controller, dict) and controller.get("name")
    }
    option_names = set((interface.get("option") or {}).keys())

    seen_task_names: set[str] = set()
    for task in as_list(interface.get("task")):
        if not isinstance(task, dict):
            continue
        task_name = str(task.get("name", ""))
        if task_name in seen_task_names:
            ctx.error("E206", f"任务名重复：`{task_name}`", file="assets/interface.json")
        seen_task_names.add(task_name)

        for group in as_list(task.get("group")):
            if group not in group_names:
                ctx.error("E217", f"任务 `{task_name}` 引用了未声明的 group `{group}`", file="assets/interface.json")
        for controller in as_list(task.get("controller")):
            if controller not in controller_names:
                ctx.error(
                    "E217",
                    f"任务 `{task_name}` 引用了未声明的 controller `{controller}`",
                    file="assets/interface.json",
                )
        for resource in as_list(task.get("resource")):
            if resource not in resource_names:
                ctx.error("E217", f"任务 `{task_name}` 引用了未声明的 resource `{resource}`", file="assets/interface.json")
        for option in as_list(task.get("option")):
            if option not in option_names:
                ctx.error("E218", f"任务 `{task_name}` 引用了未定义的 option `{option}`", file="assets/interface.json")

    for option in as_list(interface.get("global_option")):
        if option not in option_names:
            ctx.error("E218", f"global_option 引用了未定义的 option `{option}`", file="assets/interface.json")

    for option_name, option in (interface.get("option") or {}).items():
        if not isinstance(option, dict):
            continue
        for case in as_list(option.get("cases")):
            if not isinstance(case, dict):
                continue
            override = case.get("pipeline_override")
            if isinstance(override, dict):
                for name in override:
                    if name.startswith("$"):
                        continue
                    if name not in ctx.nodes:
                        ctx.warn(
                            "W206",
                            f"option `{option_name}` 的 pipeline_override 指向不存在的节点 `{name}`",
                            file="assets/interface.json",
                        )

    return entries


def check_task_fragments(ctx: LintContext) -> set[str]:
    entries: set[str] = set()
    if not TASKS_DIR.is_dir():
        return entries
    for path in sorted(TASKS_DIR.rglob("*.json")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            fragment = load_jsonc(path)
        except JsoncError as error:
            ctx.error("E001", f"解析失败：{error}", file=rel)
            continue
        for task in as_list(fragment.get("task")):
            if isinstance(task, dict) and task.get("entry"):
                entry = str(task["entry"])
                entries.add(entry)
                if entry not in ctx.nodes:
                    ctx.error("E206", f"任务 entry 指向不存在的节点 `{entry}`", file=rel)
                elif entry.startswith("__"):
                    ctx.error("E209", f"任务 entry 不能是内部节点 `{entry}`", file=rel)
    return entries


# --------------------------------------------------------------------------- #
# agent registration scan
# --------------------------------------------------------------------------- #


def scan_agent_registrations() -> tuple[set[str], set[str]]:
    actions: set[str] = set()
    recognitions: set[str] = set()
    if not AGENT_DIR.is_dir():
        return actions, recognitions
    for path in AGENT_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        actions.update(CUSTOM_ACTION_RE.findall(text))
        recognitions.update(CUSTOM_RECOGNITION_RE.findall(text))
    return actions, recognitions


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def run_lint() -> LintContext:
    ctx = LintContext()
    collect_nodes(ctx)
    registered_actions, registered_recognitions = scan_agent_registrations()

    for node in ctx.nodes.values():
        check_node_shape(ctx, node)
        check_templates(ctx, node)
        check_roi(ctx, node)
        check_coordinates(ctx, node)
        check_action_params(ctx, node)
        check_self_loop(ctx, node)
        check_ocr_expected(ctx, node)
        check_custom_ids(ctx, node, registered_actions, registered_recognitions)
        check_business_entry(ctx, node)

    interface_entries = load_interface(ctx)
    task_entries = check_task_fragments(ctx)
    entries = interface_entries | task_entries | {name for name in ctx.nodes if name.endswith("Entry")}
    check_graph(ctx, entries)
    check_unused_templates(ctx)

    default_pipeline = RESOURCE_DIR / "default_pipeline.json"
    if default_pipeline.is_file():
        try:
            load_jsonc(default_pipeline)
        except JsoncError as error:
            ctx.error("E001", f"default_pipeline.json 解析失败：{error}", file="assets/resource/default_pipeline.json")

    return ctx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Houkai2Maa pipeline lint")
    parser.add_argument("--strict", action="store_true", help="warning 也视为失败")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--show-allowed", action="store_true", help="显示允许清单豁免的规则明细")
    args = parser.parse_args(argv)

    ctx = run_lint()
    ordered = sorted(ctx.diagnostics, key=lambda item: (item.file, item.line, item.code))

    if args.json:
        payload = {
            "errors": len(ctx.errors),
            "warnings": len(ctx.warnings),
            "nodes": len(ctx.nodes),
            "allowed": len(ctx.allowed),
            "diagnostics": [
                {
                    "severity": item.severity,
                    "code": item.code,
                    "message": item.message,
                    "file": item.file,
                    "line": item.line,
                    "node": item.node,
                }
                for item in ordered
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in ordered:
            print(item.render())
        if args.show_allowed:
            for item in ctx.allowed:
                print(item.render().replace("(error)", "(allowed)").replace("(warning)", "(allowed)"))
        print(
            f"\n已检查 {len(ctx.nodes)} 个节点：{len(ctx.errors)} error / "
            f"{len(ctx.warnings)} warning / {len(ctx.allowed)} allowed"
        )

    if ctx.errors:
        return 1
    if args.strict and ctx.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
