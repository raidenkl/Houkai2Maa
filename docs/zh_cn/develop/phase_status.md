# 重构进度与阻塞项

> 本文是给人和 AI 的**状态快照**：已经完成什么、还缺什么、缺的东西由谁提供。
> 计划原文见方案文档；每次 Phase 推进时同步更新本页。

最后更新：Phase 4 部分提前完成阶段（工具链与契约就绪，日常节点待游戏事实）

## 总览

| Phase | 内容                                                            | 状态                                                               |
| ----- | --------------------------------------------------------------- | ------------------------------------------------------------------ |
| 0     | 720p 基准、工具链、lint、record/replay、AGENTS/skills、CI、清理 | ✅ 完成                                                            |
| 1     | Agent 骨架 + 启动/导航层                                        | 🟡 Agent 与工具就绪；L0/L1 节点**等待游戏事实**                    |
| 2     | 领奖三件套（签到/邮件/社团福利）                                | ⛔ 等待游戏事实                                                    |
| 3     | 刷本循环（FarmLoop/FarmNote/FarmFail 已实现）                   | 🟡 Agent 侧就绪；节点等待事实                                      |
| 4     | interface v2 现代化 + 阵营战迁移                                | 🟡 import/preset/pretask/option 已打通；阵营战 720p 重写待重拍模板 |
| 5     | 真机回归 20 次 + v2.0.0 发布                                    | ⛔ 依赖 1–4                                                        |

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
- **文档**：`AGENTS.md`、`.agents/skills/{pipeline-guide,agent-guide,add-daily-task}`、
  `conventions` / `ai_workflow` / `debugging` / `game_facts` / `flow_template`

## 阻塞项（需要真实游戏事实）

| 缺什么                                       | 用于                          | 谁提供         |
| -------------------------------------------- | ----------------------------- | -------------- |
| 主界面截图 + 入口位置                        | `20_nav/Home                  | Entries`       | 需求方提供 720p 截图 |
| 签到/邮件/社团面板截图与「已领取」形态       | `30_daily/*`                  | 同上           |
| 刷本：关卡列表、备战页、结算页、体力不足弹窗 | `30_daily/Farm`               | 同上           |
| 游戏包名（官服/B 服）与启动方式              | `00_launch/Launch`            | 同上           |
| 阵营战 720p 模板重拍                         | `90_activity/FactionWar` 重写 | 同上（或真机） |

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
| 回放用例仅 1 条 smoke 夹具                    | `tests/cases`                            | 有设备后录真实用例          |
| Win32 控制器未验证                            | `interface.json`                         | Phase 5 实测后转正或移除    |
