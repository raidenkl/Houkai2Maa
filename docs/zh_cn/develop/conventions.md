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
| 入口分流    | `<Task>Start`               | `ResonanceRefreshStart`           |
| 内部节点    | `__<Task>*`                 | `__FarmWaitResult`                |
| 自定义件 ID | PascalCase，与节点名无关    | `FarmLoop`、`PanelState`          |
| 图片        | 与 pipeline 同构目录，ASCII | `30_daily/SignIn/claim.png`       |
| 用例        | kebab-case                  | `farm-normal`                     |

## 5. 延迟与等待

- **`pre_delay` / `post_delay` 全局默认 200 / 400**（`default_pipeline.json`），
  **不许改回 0**：转场期间的触摸会被客户端直接吞掉，实测表现为「点了没反应、
  1.4s 后又点一次」和「战斗里切装备没生效」（见 game_facts §18.6）。lint E107 把关；
- 单个节点写死小于 150 / 300 会报 E106（确需连点写进 `allowlist.json`）；
- 超过 1000ms 的固定延迟直接报错（E105）——那种情况用下面的等待手段；
- 等画面静止：`pre_wait_freezes` / `post_wait_freezes`，写成
  `{"time": 300, "timeout": 3000}` 这种带超时的形式（超时即放行，不会卡死）；
- 等目标：插一个识别节点（例如 `CommonLoading` 的 `inverse`）；
- 战斗这种「时长不可预测」的等待，用结算界面识别 + `timeout` + `on_error` 重试。

### 5.1 点击坐标

- **位置固定、且比识别框窄的目标一律写死 `action.param.target`**；
- `target_offset` 的基准是「识别框内随机点」，不是框心：框宽本身就是抖动范围。
  锚在宽文字上、偏移到旁边窄按钮时，命中概率 ≈ 目标宽 / 框宽，
  一键日常的共鸣之力就是 24/130 的按钮配 130 宽的锚点，约 37% 命中率（2026-10-22 崩掉）；
- 只有「目标随内容浮动」（列表行、条目标题）才用 `target_offset`，且偏移量按框**中心**算；
- 坐标一律 1280x720；窄按钮的圆心用像素测（`debug/step.py` 可现场截图 + OCR 复核）。

## 6. 预任务（pretask）

> **默认关闭**。`interface.json` 里 `pretask` 与 `agent` 两段是注释掉的：MFAAvalonia 把
> `pretask.exec` 无条件拼到 `<包根>/resource/base/` 下，裸 `python` 必然失败并让整条
> 初始化链中止（界面显示成「连不上模拟器」）。本项目目前没有 Custom 节点，用不到 Agent；
> 要启用必须随包分发嵌入式 Python，写法见 `interface.json` 里的注释。

启用后，`pretask` 会在 Controller 启动前执行（PI v2.7+），失败则中止启动。
它只做一件事：**检查截图分辨率是否为 1280×720**，避免「分辨率不对 → 全量坐标偏移 → 识别不到」。

- 脚本：`assets/agent/pretask/device_prepare.py`（`--image` 可离线校验单张截图）
- 多设备用 `MAAHOUKAI2_ADB_ADDRESS=<地址>` 指定目标；未指定时只告警不阻断
- MFAAvalonia 执行 pretask 时不注入 `PI_*`，控制器过滤靠 `pretask.controller` 字段
- 判定逻辑：`assets/agent/common/frame.py`（纯函数，有单测）
- 故障处理：见 [debugging.md](./debugging.md#预任务失败)

新增预任务时：`exec` 用 `python`，`args` 指向 `./agent/pretask/xxx.py`（相对 interface.json 所在目录；安装包里 agent/ 与 interface 同级），
并用 `controller` 限定适用控制器（lint 规则 E219 会检查脚本是否存在）。

## 7. option 与任务注册

- 参数一律走 `option` + `pipeline_override`，不要在 pipeline 里写死次数/开关；
- `option` 定义放 `assets/tasks/options/global.json`（跨任务）或 `assets/tasks/daily/<Task>.json`（任务内）；
- 新任务的 `assets/tasks/*.json` 必须加入 `interface.json` 的 `import`（路径相对 `assets/`）；
- 任务 `group` 只能是 `daily` / `activity` / `tools`。

## 8. 规则豁免

`tools/lint/allowlist.json` 只用于「已登记的技术债」：

```jsonc
{
    "E105": {
        "assets/resource/pipeline/90_activity/FactionWar.json": ["FactionWarStart"],
    },
}
```

新增豁免必须在 PR 描述里写清楚**移除时间点**；Phase 4 完成后应清空。

## 9. 提交前检查

```bash
npm run verify   # check + test:node + lint + lint:py + schema + test + replay + format:check + format:py
```

Python 侧规范由 `ruff.toml` 定义：`E4/E7/E9/F/I/UP/B`，行宽 120，目标 py310；
新增脚本时先 `python tools/dev/run_ruff.py check .` 和
`python tools/dev/run_ruff.py format .`（或 `npm run format:py` 只做检查）。

CI 会跑同样的命令；任何一项红都不合并。
