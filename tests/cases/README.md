# 用例说明

本目录下的 `*.json` 会在 `python tools/dev/replay.py --all` 时被读取，
用于**离线回放**已经录制好的任务执行（无需设备）。

## 文件格式

```jsonc
{
    "case": "farm-normal", // 用例名，需与录制文件名一致
    "entry": "FarmStageEntry", // 任务入口节点
    "recording": "tests/recordings/farm-normal/farm-normal.jsonl", // 录制文件（相对仓库根）
    "expect": {
        "completed": true, // 任务是否应成功结束
        "hit_nodes": ["FarmStart", "FarmWaitResult", "FarmAgain"], // 需按顺序出现
        "max_steps": 120, // 节点数上限（防止死循环回归）
    },
}
```

## 录制方法

```bash
python tools/dev/record.py --case farm-normal --entry FarmStageEntry
```

录制会在 `tests/recordings/farm-normal/` 生成：

- `farm-normal.jsonl` 操作与截图索引
- `farm-normal-Screenshot/` 截图帧
- `farm-normal.summary.json` 本次执行摘要（节点序列、结果）

录制文件体积请控制在 50MB 以内（只保留关键分支即可），
否则请先裁剪截图或改用 `tests/node-cases` 做节点级测试。

## 与 node-cases 的区别

| 目录                               | 验证什么                                           | 依赖   |
| ---------------------------------- | -------------------------------------------------- | ------ |
| `tests/cases` + `tests/recordings` | 整条流程的分支与连通性（`ReplayController`）       | 无设备 |
| `tests/node-cases`                 | 单个识别在给定截图上的命中情况（`maafw` 离线识别） | 无设备 |
