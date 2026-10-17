import argparse
from pathlib import Path

import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from shared.bootstrap import enable_local_lib

    enable_local_lib()
except ImportError:  # tools/shared 缺失时退化为系统环境
    pass

try:
    import jsonc
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments\n"
        "Or add it to your project's requirements."
    ) from e

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.resolve()

parser = argparse.ArgumentParser(description="把资源/Agent/依赖组装成可分发的 install 目录")
parser.add_argument("version", help="版本号，例如 v1.0.0")
parser.add_argument("os_name", choices=["win", "macos", "linux", "android"], help="目标系统")
parser.add_argument("arch", choices=["x86_64", "aarch64"], help="目标架构")
parser.add_argument("--install-dir", default=str(working_dir / "install"), help="安装输出目录（默认 install/）")
parser.add_argument("--no-deps", action="store_true", help="跳过 MaaFramework 运行时拷贝（仅本地验证打包结构）")
args = parser.parse_args()

install_path = Path(args.install_dir).resolve()
version = args.version
os_name = args.os_name
arch = args.arch


def get_dotnet_platform_tag():
    """自动检测当前平台并返回对应的dotnet平台标签"""
    if os_name == "win" and arch == "x86_64":
        platform_tag = "win-x64"
    elif os_name == "win" and arch == "aarch64":
        platform_tag = "win-arm64"
    elif os_name == "macos" and arch == "x86_64":
        platform_tag = "osx-x64"
    elif os_name == "macos" and arch == "aarch64":
        platform_tag = "osx-arm64"
    elif os_name == "linux" and arch == "x86_64":
        platform_tag = "linux-x64"
    elif os_name == "linux" and arch == "aarch64":
        platform_tag = "linux-arm64"
    else:
        print("Unsupported OS or architecture.")
        print("available parameters:")
        print("version: e.g., v1.0.0")
        print("os: [win, macos, linux, android]")
        print("arch: [aarch64, x86_64]")
        sys.exit(1)

    return platform_tag


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print('Please download the MaaFramework to "deps" first.')
        print('请先下载 MaaFramework 到 "deps"。')
        sys.exit(1)

    if os_name == "android":
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
    else:
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path / "runtimes" / get_dotnet_platform_tag() / "native",
            ignore=shutil.ignore_patterns(
                "*MaaDbgControlUnit*",
                "*MaaThriftControlUnit*",
                "*MaaRpc*",
                "*MaaHttp*",
                "plugins",
                "*.node",
                "*MaaPiCli*",
            ),
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "libs" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "bin" / "plugins",
            install_path / "plugins" / get_dotnet_platform_tag(),
            dirs_exist_ok=True,
        )



def install_resource():

    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    interface["version"] = version

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )


def install_agent():
    shutil.copytree(
        working_dir / "assets" / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc"),
    )


def verify_install():
    """安装后自检：interface 里引用的 import / pretask / agent 脚本是否都在包内。"""

    interface_file = install_path / "interface.json"
    if not interface_file.is_file():
        raise SystemExit("自检失败：安装目录缺少 interface.json")

    from shared.jsonc import load_jsonc

    interface = load_jsonc(interface_file)
    missing: list[str] = []

    for item in interface.get("import") or []:
        if not (install_path / item).is_file():
            missing.append(f"import: {item}")

    pretask = interface.get("pretask")
    pretasks = pretask if isinstance(pretask, list) else ([pretask] if pretask else [])
    for item in pretasks:
        if not isinstance(item, dict):
            continue
        for arg in item.get("args") or []:
            if isinstance(arg, str) and arg.startswith("./") and not (install_path / arg).is_file():
                missing.append(f"pretask args: {arg}")

    agent = interface.get("agent")
    agents = agent if isinstance(agent, list) else ([agent] if agent else [])
    for item in agents:
        if not isinstance(item, dict):
            continue
        for arg in item.get("child_args") or []:
            if isinstance(arg, str) and arg.startswith("./") and not (install_path / arg).is_file():
                missing.append(f"agent args: {arg}")

    if missing:
        for entry in missing:
            print(f"  [missing] {entry}")
        raise SystemExit("安装自检失败：存在引用不到的路径")

    print("安装自检通过：import / pretask / agent 路径均可解析")


def install_tasks():
    """interface.json 的 `import` 片段（tasks/）必须随安装包一起分发。"""

    # interface.json 会被拷到 install 根目录，PI 的 import 路径相对它解析，
    # 因此把 assets/tasks 分发为 install/tasks
    tasks_dir = working_dir / "assets" / "tasks"
    if not tasks_dir.is_dir():
        return
    shutil.copytree(tasks_dir, install_path / "tasks", dirs_exist_ok=True)


if __name__ == "__main__":
    install_path.mkdir(parents=True, exist_ok=True)
    if not args.no_deps:
        install_deps()
    install_resource()
    install_chores()
    install_agent()
    install_tasks()
    verify_install()

    print(f"Install to {install_path} successfully.")
