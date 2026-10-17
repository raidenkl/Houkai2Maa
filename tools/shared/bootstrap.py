"""本地依赖引导。

本仓库把 Python 依赖装在 `<repo>/.pylib`（而不是用户主目录），
原因有两个：

1. 与 AI/CI 保持同一套依赖版本，换机器可复现；
2. 某些环境没有 `python3-venv`，或不允许写用户 site-packages。

导入本模块后调用 `enable_local_lib()`，即可让后续 `import maa` 生效。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_LIB = REPO_ROOT / ".pylib"


def enable_local_lib() -> Path | None:
    """把 `<repo>/.pylib` 放到 `sys.path` 最前面（若存在）。"""

    if LOCAL_LIB.is_dir():
        path = str(LOCAL_LIB)
        if path not in sys.path:
            sys.path.insert(0, path)
        return LOCAL_LIB
    return None
