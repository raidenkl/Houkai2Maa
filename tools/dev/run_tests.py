#!/usr/bin/env python3
"""运行 Agent 单元测试（自动使用仓库内 `.pylib` 依赖）。

`python -m pytest` 在受限环境里不一定能找到 pytest（依赖装在 `.pylib`），
因此统一走这个入口，CI 与本地行为一致。

用法：

    python tools/dev/run_tests.py            # 跑 agent/tests
    python tools/dev/run_tests.py -k farm    # 透传 pytest 参数
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.bootstrap import enable_local_lib  # noqa: E402

enable_local_lib()


def main(argv: list[str]) -> int:
    try:
        import pytest
    except ImportError:
        print("未找到 pytest，请先执行：python tools/dev/setup.py", file=sys.stderr)
        return 2

    args = argv or ["agent/tests", "tools/tests", "-q"]
    return int(pytest.main(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
