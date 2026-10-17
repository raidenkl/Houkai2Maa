# AI 辅助开发流程

本仓库刻意做成「AI 可接手」的形状：约定写在 `AGENTS.md` 与 `.agents/skills/`，
校验写在 `tools/` 与 CI，游戏事实写在 `docs/zh_cn/develop/game_facts.md`。
AI 会话不需要历史上下文，也能按这套流程安全地改动。

## 可用技能（`.agents/skills/`）

| 技能             | 何时用                                            |
| ---------------- | ------------------------------------------------- |
| `pipeline-guide` | 写/改 pipeline JSON、选识别与动作、加兜底、调 ROI |
| `agent-guide`    | 在 `agent/` 加自定义动作/识别、参数与单测         |
| `add-daily-task` | 从零新增一个日常任务的完整 SOP                    |

DSH / Claude Code 会自动发现这些技能；其他工具可直接读 `SKILL.md`。

## 闭环

### 1. 看（取事实）

```bash
uvx maafw-cli connect adb 127.0.0.1:16384
uvx maafw-cli --json ocr                    # 屏幕文字 + 坐标 + 自动截图
uvx maafw-cli --json reco TemplateMatch template=双倍.png threshold=0.8
```

没有 `uvx` 的环境用仓库自带脚本：

```bash
python tools/dev/snapshot.py --json   # 720p 截图 + OCR + 标注图，输出文字与坐标
```

结论写进 `docs/zh_cn/develop/game_facts.md`；没有实测就不要写坐标与文案。
裁模板用 `tools/dev/crop.py`（会校验 720p 并直接生成节点片段）。

对已有截图做离线 OCR（不需要设备）：

```bash
python tools/dev/snapshot.py --image shots/signin.png --json
```

### 2. 改（受约束）

- 只改这些位置：`assets/resource/pipeline/**`、`assets/resource/image/**`、
  `assets/tasks/**`、`agent/**`、`tests/**`、文档；
- 不要手改 `deps/tools/*.schema.json`；
- 改完立刻跑 `npm run lint`，它会指出命名、ROI、兜底、Custom ID 等问题。

### 3. 验（离线优先）

| 命令                                 | 验证什么                     | 需要设备 |
| ------------------------------------ | ---------------------------- | -------- |
| `npm run check`                      | 框架语义（任务树/图片/结构） | 否       |
| `npm run lint`                       | 本项目约定                   | 否       |
| `npm run schema`                     | JSON Schema                  | 否       |
| `npm run test`                       | Agent 纯逻辑单测             | 否       |
| `npm run test:node`                  | 单识别在给定截图上是否命中   | 否       |
| `npm run replay`                     | 整条流程回放                 | 否       |
| `uvx maafw-cli pipeline run <Entry>` | 真机端到端                   | 是       |

### 4. 录（沉淀回归）

```bash
python tools/dev/record.py --case <case> --entry <Entry>
```

把新分支/异常分支录成用例，写 `tests/cases/<case>.json` 期望，提交进仓库。
之后任何人（或 AI）改坏了流程，`npm run replay` 会报出来。

### 5. 记（文档即上下文）

- 新的界面事实 → `game_facts.md`
- 新的约定/反模式 → `conventions.md` 或对应 `SKILL.md`
- 技术债豁免 → `tools/lint/allowlist.json`（写清移除时间点）

## 失败复盘顺序

1. `debug/maa.log` + [MaaLogAnalyzer](https://mla.maafw.com/)：看任务在哪个节点停住；
2. `debug/on_error/`：框架自动保存的失败截图；
3. `debug/shots/`：`SaveShot` 主动落盘的现场；
4. `debug/agent.log`：Custom 动作/识别的入参、判定结果；
5. 单节点复现：`uvx maafw-cli reco ...` 或 `tests/node-cases`。

## 不要做的事

- 凭截图之外的想象写坐标/文案；
- 为了让 CI 变绿而删除用例或放宽 lint（应走 allowlist 并登记）；
- 把流程搬进 Python（失去可视化与统一 UI 生态）；
- 自动输入账号密码。
