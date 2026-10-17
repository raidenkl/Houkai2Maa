#!/usr/bin/env python3
"""一键准备本地开发环境（幂等）。

做四件事：

1. 把 `maafw`（MaaFramework 的 Python 绑定）与校验依赖装到 `<repo>/.pylib`；
2. 准备 OCR 模型到 `assets/resource/model/ocr/`（优先子模块，其次官方下载）；
3. 检查 Node 侧依赖（`npm install` 后的 `node_modules`）；
4. 检查 `adb` 与可选的 `maafw-cli`（AI 联调用）。

之所以自己装 `.pylib` 而不用 venv：部分环境缺少 `python3-venv`，
或不允许写用户 site-packages；放在仓库内既能跑，也让 AI/CI 版本一致。

用法：

    python tools/dev/setup.py            # 缺什么装什么
    python tools/dev/setup.py --check    # 只体检，不安装（CI 用）
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_LIB = REPO_ROOT / ".pylib"
PIP_CACHE = REPO_ROOT / ".pip-cache"
OCR_DIR = REPO_ROOT / "assets" / "resource" / "model" / "ocr"
OCR_SUBMODULE = REPO_ROOT / "assets" / "MaaCommonAssets" / "OCR" / "ppocr_v5" / "zh_cn"
OCR_URL = "https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v5/ppocr_v5-zh_cn.zip"
OCR_FILES = ("det.onnx", "rec.onnx", "keys.txt")
PIP_PACKAGES = ("maafw>=5.14,<6", "jsonschema==4.26.0", "referencing==0.37.0", "pytest")


def log(message: str) -> None:
    print(f"[setup] {message}")


def warn(message: str) -> None:
    print(f"[setup][warn] {message}", file=sys.stderr)


def fail(message: str) -> None:
    print(f"[setup][error] {message}", file=sys.stderr)


def module_available(module: str, extra_path: Path | None = None) -> bool:
    code = f"import sys; sys.path.insert(0, {str(extra_path)!r}) if {extra_path is not None} else None; import {module}"
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return completed.returncode == 0


def install_python_deps(check_only: bool) -> bool:
    if module_available("maa", LOCAL_LIB) and module_available("jsonschema", LOCAL_LIB) and module_available("pytest", LOCAL_LIB):
        log(f"Python 依赖已就绪：{LOCAL_LIB.relative_to(REPO_ROOT)}")
        return True

    if check_only:
        fail("缺少 Python 依赖（maa / jsonschema / pytest），请执行 python tools/dev/setup.py")
        return False

    log("安装 Python 依赖到 .pylib ...")
    LOCAL_LIB.mkdir(parents=True, exist_ok=True)
    PIP_CACHE.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--target",
        str(LOCAL_LIB),
        "--cache-dir",
        str(PIP_CACHE),
        "--upgrade",
        *PIP_PACKAGES,
    ]
    completed = subprocess.run(command)
    if completed.returncode != 0:
        fail("Python 依赖安装失败，请检查网络或手动执行上面的 pip 命令")
        return False
    return module_available("maa", LOCAL_LIB)


def ocr_ready() -> bool:
    return all((OCR_DIR / name).is_file() for name in OCR_FILES)


def copy_ocr_from(path: Path) -> bool:
    missing = [name for name in OCR_FILES if not (path / name).is_file()]
    if missing:
        return False
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    for name in OCR_FILES:
        shutil.copy2(path / name, OCR_DIR / name)
    log(f"OCR 模型已从 {path.relative_to(REPO_ROOT)} 复制到 assets/resource/model/ocr")
    return True


def download_ocr(check_only: bool) -> bool:
    if check_only:
        fail("缺少 OCR 模型，请执行 python tools/dev/setup.py（或 git submodule update --init）")
        return False

    log(f"下载 OCR 模型：{OCR_URL}")
    with tempfile.TemporaryDirectory() as temp_dir:
        archive = Path(temp_dir) / "ppocr.zip"
        try:
            with urllib.request.urlopen(OCR_URL, timeout=120) as response, archive.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except OSError as error:
            fail(f"下载失败：{error}")
            warn("可以手动下载上面的 URL，把 det.onnx / rec.onnx / keys.txt 放到 assets/resource/model/ocr/")
            return False

        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(temp_dir)
        extracted = Path(temp_dir)
        missing = [name for name in OCR_FILES if not (extracted / name).is_file()]
        if missing:
            fail(f"压缩包结构与预期不符，缺少：{', '.join(missing)}")
            return False
        return copy_ocr_from(extracted)


def prepare_ocr(check_only: bool) -> bool:
    if ocr_ready():
        log("OCR 模型已就绪：assets/resource/model/ocr")
        return True
    if copy_ocr_from(OCR_SUBMODULE):
        return True
    return download_ocr(check_only)


def check_node(check_only: bool) -> bool:
    node_modules = REPO_ROOT / "node_modules"
    if (node_modules / "@nekosu" / "maa-tools").is_dir():
        log("Node 依赖已就绪：node_modules")
        return True
    if check_only:
        fail("缺少 node_modules，请执行 npm install")
        return False
    log("安装 Node 依赖 ...")
    env_cache = str(REPO_ROOT / ".npm-cache")
    completed = subprocess.run(["npm", "install", "--no-audit", "--no-fund", "--cache", env_cache], cwd=REPO_ROOT)
    if completed.returncode != 0:
        fail("npm install 失败")
        return False
    return (node_modules / "@nekosu" / "maa-tools").is_dir()


def check_device_tools() -> None:
    if shutil.which("adb"):
        log("adb 已找到")
    else:
        warn("未找到 adb。真机/模拟器联调需要它；也可以用 MaaFramework 自带的 adb 路径。")
    if shutil.which("maafw-cli"):
        log("maafw-cli 已找到（AI 联调推荐）")
    else:
        warn("未找到 maafw-cli，可用 `uvx maafw-cli` 临时运行（AI 联调推荐）")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Houkai2Maa 开发环境准备")
    parser.add_argument("--check", action="store_true", help="只体检，不安装")
    args = parser.parse_args(argv)

    ok = install_python_deps(args.check)
    ok = prepare_ocr(args.check) and ok
    ok = check_node(args.check) and ok
    check_device_tools()

    if ok:
        log("环境就绪。下一步：")
        log("  npm run check     # 框架静态检查")
        log("  npm run lint      # 本项目规范检查")
        log("  npm run test      # Agent 单元测试")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
