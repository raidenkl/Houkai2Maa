# 开发约定（conventions）

本文件是 `AGENTS.md` 的展开版，面向人和 AI。规则由 `tools/lint/pipeline_lint.py` 自动检查。

## 1. 技术路线

- **Pipeline JSON** 负责：识别、点击、跳转、循环骨架；
- **Agent Python** 负责：组合判定、动态 `next`、跨节点状态、设备操作。

判断标准：如果逻辑能用「识别 → 点击」直白表达，就写 JSON；只有需要计算/记忆/组合时才写 Agent。

## 2. 目录与分层

| 层      | 目录            | 允许引用                     |
| ------- | --------------- | ---------------------------- |
| L0 通用 | `10_common/`    | 仅自身                       |
| L1 导航 | `20_nav/`       | L0                           |
| L2 日常 | `30_daily/`     | L0、L1                       |
| L2 活动 | `90_activity/`  | L0、L1                       |
| L3 编排 | `assets/tasks/` | 任意 L2 的 `*Entry` 与 L0/L1 |

`__` 前缀内部节点只允许在同文件内使用。

## 3. 六条硬规则

| #   | 规则                             | lint        |
| --- | -------------------------------- | ----------- |
| 1   | 识别 → 操作 → 再识别             | 人工审查    |
| 2   | 禁止 >1000ms 固定延迟            | E105        |
| 3   | 业务入口必须有 `[JumpBack]` 兜底 | E203        |
| 4   | 坐标基准 1280×720                | E103 / W108 |
| 5   | ASCII PascalCase 命名            | E004 / W004 |
| 6   | Custom ID 必须注册               | E204        |

## 4. 命名

| 对象        | 规则                        | 示例                              |
| ----------- | --------------------------- | --------------------------------- |
| 通用节点    | `Common*`                   | `CommonConfirm`、`CommonPopupAny` |
| 导航节点    | `Nav*`                      | `NavHome`、`NavEnterSignIn`       |
| 日常节点    | `<Task>*`                   | `DailySignInMain`                 |
| 任务入口    | `<Task>Entry`               | `DailyFullEntry`                  |
| 内部节点    | `__<Task>*`                 | `__FarmWaitResult`                |
| 自定义件 ID | PascalCase，与节点名无关    | `FarmLoop`、`PanelState`          |
| 图片        | 与 pipeline 同构目录，ASCII | `30_daily/SignIn/claim.png`       |
| 用例        | kebab-case                  | `farm-normal`                     |

## 5. 延迟与等待

- `pre_delay` / `post_delay` 默认 0，超过 1000ms 直接报错；
- 等画面：`post_wait_freezes: {"time": 200, "target": [0,0,0,0]}`；
- 等目标：插一个识别节点（例如 `CommonLoading` 的 `inverse`）；
- 战斗这种「时长不可预测」的等待，用结算界面识别 + `timeout` + `on_error` 重试。

## 6. option 与任务注册

- 参数一律走 `option` + `pipeline_override`，不要在 pipeline 里写死次数/开关；
- `option` 定义放 `assets/tasks/options/global.json`（跨任务）或 `assets/tasks/daily/<Task>.json`（任务内）；
- 新任务的 `assets/tasks/*.json` 必须加入 `interface.json` 的 `import`（路径相对 `assets/`）；
- 任务 `group` 只能是 `daily` / `activity` / `tools`。

## 7. 规则豁免

`tools/lint/allowlist.json` 只用于「已登记的技术债」：

```jsonc
{
    "E105": {
        "assets/resource/pipeline/90_activity/FactionWar.json": ["FactionWarStart"],
    },
}
```

新增豁免必须在 PR 描述里写清楚**移除时间点**；Phase 4 完成后应清空。

## 8. 提交前检查

```bash
npm run verify      # check + test:node + lint + schema + test + replay + format:check
```

CI 会跑同样的命令；任何一项红都不合并。
