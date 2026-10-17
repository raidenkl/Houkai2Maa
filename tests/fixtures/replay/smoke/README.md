# replay smoke fixture

一份手写的 MaaFramework 录制文件（JSONL），用于验证 `tools/dev/replay.py`
与框架 `ReplayController` 的链路。

格式（每行一个 JSON，来自框架 `RecordTypes.h` / `RecordParser.cpp`）：

```jsonc
{"type":"connect","uuid":"smoke","version":"fixture","width":1280,"height":720,"success":true,"cost":0,"timestamp":...}
{"type":"screencap","path":"smoke-Screenshot/01-home.png","success":true,"cost":0,"timestamp":...}
{"type":"click","x":160,"y":140,"success":true,"cost":0,"timestamp":...}
```

- `path` 相对于本 JSONL 所在目录；
- 截图是 `tests/fixtures/smoke/screens/` 的副本（1280×720）；
- 对应流水线是 `tests/fixtures/smoke/resource` 的 `SmokeEntry`。

这不是真实录制（真实录制由 `tools/dev/record.py` 生成），只覆盖回放链路本身。
