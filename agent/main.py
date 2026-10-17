"""Agent 进程入口。

MaaFramework 的「方案二」：pipeline(JSON) 负责识别与流程，本 Agent 负责
只有代码才自然的部分——组合/数值判定、动态流程改写、跨节点状态、设备操作。

启动方式由 `interface.json` 的 `agent` 字段决定：

    { "child_exec": "python", "child_args": ["./agent/main.py"] }

Client 会以 `<python> agent/main.py <socket_id>` 启动，并注入 `PI_*` 环境变量
（PI_CLIENT_NAME / PI_CONTROLLER / PI_RESOURCE / PI_VERSION ...）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from maa.agent.agent_server import AgentServer  # noqa: E402
from maa.toolkit import Toolkit  # noqa: E402

from actions import register_all as register_actions  # noqa: E402
from common.context import client_context  # noqa: E402
from common.log import get_logger  # noqa: E402
from recognitions import register_all as register_recognitions  # noqa: E402

logger = get_logger("agent")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("Usage: python agent/main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        return 2

    socket_id = args[-1]

    # 与模板一致：以 interface.json 所在目录作为工作目录的基准
    Toolkit.init_option("./")

    actions = register_actions()
    recognitions = register_recognitions()

    context = client_context()
    logger.info(
        "agent 启动 socket=%s client=%s client_version=%s maafw=%s controller=%s resource=%s version=%s",
        socket_id,
        context.client_name,
        context.client_version,
        context.maafw_version,
        context.controller_name,
        context.resource_name,
        context.version,
    )
    logger.info("已注册动作：%s", ", ".join(actions) or "(无)")
    logger.info("已注册识别：%s", ", ".join(recognitions) or "(无)")

    AgentServer.start_up(socket_id)
    try:
        AgentServer.join()
    finally:
        AgentServer.shut_down()
    return 0


if __name__ == "__main__":
    sys.exit(main())
