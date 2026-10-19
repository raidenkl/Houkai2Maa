# 重构进度与阻塞项

> 本文是给人和 AI 的**状态快照**：已经完成什么、还缺什么、缺的东西由谁提供。
> 计划原文见方案文档；每次 Phase 推进时同步更新本页。

最后更新：2026-10-19（启动/登录链 + 使魔探险/共鸣之力/火线救援/世界这么大/战力补强/社团领体力/活动清体力 + 一键日常编排 真机跑通，邮件待事实）

## 总览

| Phase | 内容                                                            | 状态                                                                                               |
| ----- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| 0     | 720p 基准、工具链、lint、record/replay、AGENTS/skills、CI、清理 | ✅ 完成                                                                                            |
| 1     | Agent 骨架 + 启动/导航层                                        | 🟡 Agent 与工具就绪；`00_launch/LaunchGame` 已跑通，`20_nav` 仍靠节点内联                          |
| 2     | 领奖三件套（签到/邮件/社团福利）                                | 🟡 签到（每日签到 + 连登福利）、社团福利已跑通；邮件等待事实                                       |
| 3     | 刷本循环（FarmLoop/FarmNote/FarmFail 已实现）                   | 🟡 「世界这么大」+「活动清体力」已跑通；通用刷本仍待事实                                           |
| 4     | interface v2 现代化 + 阵营战迁移                                | 🟡 import/preset/pretask/option/checkbox 已打通，一键日常用了 checkbox；阵营战 720p 重写待重拍模板 |
| 5     | 真机回归 20 次 + v2.0.0 发布                                    | ⛔ 依赖 1–4                                                                                        |

## 已完成（可验证）

- **基准与契约**：`display_short_side=720`；`default_pipeline.json`；`assets/tasks/` + PI `import`；
  `preset ActivityOnly`；`pretask DevicePrepare`（分辨率体检）
- **Agent**：`FarmLoop` / `FarmReset` / `FarmFail` / `FarmNote` / `SceneGuard` / `SaveShot`；
  `StaminaInsufficient` / `PanelState`；`common/`（params/state/frame/log/png/context）
- **工具链**：`snapshot`（含 `--image` / `--grid`）、`crop`、`probe`、`dryrun`（含 `--expect`）、
  `nodecase`、`record`、`replay`、`setup`、`maa_tools`、`run_ruff`、`run_tests`
- **校验**：`maa-tools check` / `test:node`、`pipeline_lint --strict`（E1xx/E2xx + allowlist）、
  JSON Schema（含 `--task-dirs`）、pytest（agent + tools）、ruff、prettier、replay
- **打包**：`install.py`（`--install-dir/--no-deps` + 安装自检：import/pretask/agent 路径）
- **编排层**：`30_daily/OneClickDaily`（8 个 Gate）+ `tasks/oneclick/OneClickDaily`（checkbox 逐步开关），
  已整条真机跑通；活动清体力默认关闭，可作为 option 打开并注入活动名
- **文档**：`AGENTS.md`、`.agents/skills/{pipeline-guide,agent-guide,add-daily-task}`、
  `conventions` / `ai_workflow` / `debugging` / `game_facts` / `flow_template`

## 阻塞项（需要真实游戏事实）

| 缺什么                               | 用于                               | 状态                   |
| ------------------------------------ | ---------------------------------- | ---------------------- |
| 邮件面板截图与「已领取」形态         | `30_daily/Mail`                    | 待需求方提供 720p 截图 |
| 通用刷本：主线关卡列表以外的刷本入口 | `30_daily/Farm`                    | 活动本已覆盖，主线待补 |
| 账号登录界面截图                     | `00_launch` 登录检测（命中即停）   | 待提供（换账号时）     |
| 签到 7 天全领完 / 奖励重置后的形态   | `30_daily/SignIn`                  | 待跨周实测             |
| B 服包名                             | `LaunchGameStart` 的 `monkey` 命令 | 待实测                 |
| 阵营战 720p 模板重拍                 | `90_activity/FactionWar` 重写      | 待真机                 |

已解决（2026-10-19）：主界面入口（左栏图标模板 + 顶部导航 OCR）、官服启动方式
（`Shell` + `monkey`）、登录后的签到/活动/公告弹窗。

拿到截图后的固定流程（无设备也能完成大半）：

```bash
python tools/dev/snapshot.py --image shots/xxx.png --grid      # 文案 + 坐标 + 网格图
python tools/dev/crop.py --screen shots/xxx.png --box x,y,w,h \
    --out 30_daily/<Task>/btn.png --node <Task>Btn             # 模板 + 节点片段
python tools/dev/probe.py --node <Task>Btn --image shots/xxx.png
python tools/dev/dryrun.py --images shots/ --entry <Task>Entry --expect ...
npm run nodecase -- --node <Task>Btn --images shots/xxx
```

## 已知技术债

| 债                                            | 位置                                     | 计划                        |
| --------------------------------------------- | ---------------------------------------- | --------------------------- |
| 阵营战仍有 30s 固定等待、缺 `[JumpBack]` 兜底 | `tools/lint/allowlist.json`（E105/E203） | Phase 4 重写时删除豁免      |
| `$__mpe_code` 元数据                          | `90_activity/FactionWar.json`            | 用 MPE 打开时会重写，属正常 |
| 真实流程回放放 `tests/cases/manual/`          | `tests/cases`                            | 等待型流程逐帧对齐会漂移    |
| `LaunchGame` 无登录检测                       | `00_launch/LaunchGame.json`              | 拿到登录界面截图后补        |
| Win32 控制器未验证                            | `interface.json`                         | Phase 5 实测后转正或移除    |
