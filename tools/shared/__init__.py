"""仓库内的公共 Python 小工具。

这些模块只依赖标准库，可被 `tools/` 下的脚本与 Agent 复用。
"""

from .bootstrap import REPO_ROOT, enable_local_lib
from .jsonc import JsoncError, load_jsonc

__all__ = ["REPO_ROOT", "enable_local_lib", "JsoncError", "load_jsonc"]
