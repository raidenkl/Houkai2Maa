"""Agent 与嵌入式 Python 的打包规则（纯函数，无副作用）。

背景：MFAAvalonia 只有在 `interface.json` 出现 `agent` 块时才会拉起 Agent 子进程；
而 `child_exec` 是相对「包根」解析的（`Path.Combine(DataRoot, ...)` + 存在性检查）。
项目里 `pretask` 走的是另一条路径（`ReplacePlaceholder(exec, ResourceBase)`，不检查
路径存在），写裸 `python` 一定会被拼成 `resource/base/python` —— 这就是 2026-10-21
「连不上模拟器」的真身。因此：

* **不在仓库的 interface.json 里写 agent 块**，改由 `tools/install.py` 打包时注入；
* 只有随包带了 Python 运行时（`deps/python`）才注入；
* 不支持的平台直接移除 `agent` / `pretask`，保持纯 JSON 可用。

这里只放判断与改写逻辑，真正的拷贝动作留在 `tools/install.py`，便于单测。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.jsonc import JsoncError, load_jsonc

#: 随包发 Python 运行时的平台组合。其它平台（macos/linux/android、win-arm64）
#: 只发纯 JSON：运行时体积与构建复杂度都不划算，且游戏本体是 Windows 模拟器。
AGENT_PLATFORMS = frozenset({("win", "x86_64")})

#: 包里 Python 运行时的目录名与入口（相对 install 根目录）。
RUNTIME_DIR = "python"
CHILD_EXEC = f"./{RUNTIME_DIR}/python.exe"
CHILD_ARGS = ["./agent/main.py"]

#: 复制运行时时可以丢掉的体积大头（标准库里的测试/示例/图形界面）。
RUNTIME_IGNORE = ("Lib/test", "Lib/idlelib", "Lib/tkinter", "Lib/lib2to3", "Lib/ensurepip", "__pycache__", "*.pyc")


def supports_agent(os_name: str, arch: str) -> bool:
    """该平台是否随包分发 Agent（及其 Python 运行时）。"""

    return (os_name, arch) in AGENT_PLATFORMS


def agent_block(has_python: bool) -> dict[str, Any] | None:
    """生成 interface.json 的 `agent` 块；没有运行时时返回 None。"""

    if not has_python:
        return None
    return {"child_exec": CHILD_EXEC, "child_args": list(CHILD_ARGS)}


def apply_agent(interface: dict[str, Any], os_name: str, arch: str, has_python: bool) -> dict[str, Any]:
    """就地改写 interface.json 的 agent / pretask 配置并返回。

    * 平台支持且带了运行时 → 注入 `agent` 块；
    * 否则 → 移除 `agent` 与 `pretask`（两者都依赖包内 Python，留着只会让启动链中止）。
    """

    block = agent_block(has_python) if supports_agent(os_name, arch) else None
    if block is None:
        interface.pop("agent", None)
        interface.pop("pretask", None)
    else:
        interface["agent"] = block
    return interface


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _package_relatives(value: Any) -> list[str]:
    """收集「相对包根」的路径（以 `./` 开头）；`{PROJECT_DIR}` 之类的占位符跳过。"""

    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, str) and item.startswith("./")]


def check_paths(interface: dict[str, Any], root: Path) -> list[str]:
    """校验 interface 里所有「相对包根」的引用在 `root` 下都存在。

    覆盖 `import`、`pretask.exec`/`args`、`agent.child_exec`/`child_args`。
    早期实现漏了 `child_exec`，于是「运行时没拷进包」这种致命问题能通过自检。
    """

    problems: list[str] = []

    for item in interface.get("import") or []:
        if isinstance(item, str) and not (root / item).is_file():
            problems.append(f"import 文件不存在：{item}")

    for label, key in (("pretask", "exec"), ("agent", "child_exec")):
        for block in _as_list(interface.get(label)):
            if not isinstance(block, dict):
                continue
            for relative in _package_relatives(block.get(key)):
                if not (root / relative).is_file():
                    problems.append(f"{label}.{key} 不存在：{relative}")
            for field in ("args", "child_args"):
                for relative in _package_relatives(block.get(field)):
                    if not (root / relative).is_file():
                        problems.append(f"{label} 脚本不存在：{relative}")

    return problems


def _node_type(section: Any) -> str:
    if isinstance(section, str):
        return section
    if isinstance(section, dict):
        value = section.get("type")
        return value if isinstance(value, str) else ""
    return ""


def count_custom_nodes(resource_dir: Path) -> int:
    """统计 pipeline 里 Custom 识别/动作的数量（用于「有 Custom 就必须有 Agent」检查）。"""

    if not resource_dir.is_dir():
        return 0
    total = 0
    for path in resource_dir.rglob("*.json"):
        if path.name == "default_pipeline.json":
            continue
        try:
            data = load_jsonc(path)
        except (JsoncError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for node in data.values():
            if not isinstance(node, dict):
                continue
            if _node_type(node.get("recognition")) == "Custom" or _node_type(node.get("action")) == "Custom":
                total += 1
    return total


def custom_requires_agent(interface: dict[str, Any], resource_dir: Path) -> list[str]:
    """有 Custom 节点却没有 agent 块 → 返回问题描述（发布包会在运行期直接失败）。"""

    count = count_custom_nodes(resource_dir)
    has_agent = bool(interface.get("agent"))
    if count and not has_agent:
        return [f"有 {count} 个 Custom 节点，但 interface 没有 agent 块（运行期不会注册自定义件）"]
    return []
