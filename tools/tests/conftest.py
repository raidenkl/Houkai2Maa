"""pytest 配置：把仓库内 dev 依赖与 tools 目录加入 import 路径。"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

for path in (REPO_ROOT / "tools", REPO_ROOT / "tools" / "dev", REPO_ROOT / ".pylib"):
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
