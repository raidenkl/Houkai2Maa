"""预任务（`interface.json` 的 `pretask`）脚本集合。

预任务在 Controller 创建之前由 Client 以子进程方式执行，失败会中止启动。
目前只有设备分辨率体检（`device_prepare.py`）。
"""
