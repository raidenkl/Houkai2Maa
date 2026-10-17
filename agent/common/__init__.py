"""Agent 的纯逻辑层。

这里只放不依赖 MaaFramework API 的代码（参数校验、状态机、日志、PI_* 上下文），
方便直接用 pytest 覆盖。

注意：本目录名与 `tools/common/` 同名但相互独立；
Agent 内一律用 `from common.<module> import ...`，测试通过 `agent/tests/conftest.py`
把 `agent/` 放到 `sys.path` 最前面来保证解析到本包。
"""
