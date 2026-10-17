"""pytest 配置：把仓库内的 dev 依赖与 agent 包加入 import 路径。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = REPO_ROOT / "agent"
LOCAL_LIB = REPO_ROOT / ".pylib"

for path in (str(AGENT_ROOT), str(LOCAL_LIB)):
    if Path(path).is_dir() and path not in sys.path:
        sys.path.insert(0, path)
