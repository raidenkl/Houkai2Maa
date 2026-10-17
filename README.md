# MaaHoukai2 · 崩坏学园2 小助手

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的图像识别自动化工具，
目标是把游戏日常做成一键任务：**启动/登录 → 回主界面 → 领奖（签到/邮件/社团福利）→ 体力刷指定关卡**。

> 当前处于重构中（v2）：骨架、工具链与 Agent 扩展位已就绪，
> 日常玩法按 `30_daily/` 逐个落地。原有的「阵营战」保留在 `90_activity/`。

## 特性

- **Pipeline + Agent 双轨**：流程用 JSON 描述（可视化可调试），
  计数/组合判定/动态流程交给 Python Agent，二者边界写在 `AGENTS.md`。
- **720p 统一基准**：所有 ROI 与模板按 1280×720（16:9），跨设备更稳定。
- **可离线验证**：静态检查 + 项目规范 lint + Agent 单测 + 节点截图测试 + 录制回放，
  全部不需要设备即可在 CI 跑。
- **AI 可接手**：仓库内置 `AGENTS.md` 与 `.agents/skills/`（pipeline / agent / 新增日常任务），
  配合 `maafw-cli` 可在无 GUI 环境下完成「截图 → 调参 → 验证」闭环。

## 快速开始

```bash
# 1. 准备环境（Python 依赖装在 .pylib，OCR 模型自动注入）
python tools/dev/setup.py

# 2. 静态检查
npm run verify

# 3. 真机联调（示例）
uvx maafw-cli connect adb 127.0.0.1:16384
uvx maafw-cli --json ocr

# 没有设备时的离线手段
python tools/dev/snapshot.py --image shots/home.png        # 对截图做 OCR，拿 720p 坐标
python tools/dev/dryrun.py --images shots/ --entry <Entry> # 用截图跑流程结构
```

发布包：使用 [MFAAvalonia](https://github.com/SweetSmellFox/MFAAvalonia) 打开
`assets/interface.json`，或使用 Release 中的整合包。

## 目录结构

```tree
assets/interface.json        # 项目接口（控制器/资源/任务分组/选项）
assets/resource/
├── default_pipeline.json    # 全局默认参数
├── pipeline/                # 00_launch / 10_common / 20_nav / 30_daily / 90_activity
├── image/                   # 模板图（720p）
└── model/ocr/               # OCR 模型（构建时注入）
tasks/                       # 任务与选项片段（interface import）
agent/                       # AgentServer：自定义动作/识别 + 单测
tools/                       # lint / record / replay / setup
tests/                       # cases（回放）与 node-cases（离线识别）
docs/zh_cn/develop/          # 约定、AI 工作流、游戏事实表
```

## 文档

- 开发约定：[docs/zh_cn/develop/conventions.md](docs/zh_cn/develop/conventions.md)
- AI 辅助开发：[docs/zh_cn/develop/ai_workflow.md](docs/zh_cn/develop/ai_workflow.md)
- 游戏事实表：[docs/zh_cn/develop/game_facts.md](docs/zh_cn/develop/game_facts.md)
- 流程描述模板：[docs/zh_cn/develop/flow_template.md](docs/zh_cn/develop/flow_template.md)
- 上手说明：[docs/zh_cn/develop/how_to_develop.md](docs/zh_cn/develop/how_to_develop.md)

## 鸣谢

本项目由 **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** 强力驱动！

感谢以下开发者对本项目作出的贡献:

[![Contributors](https://contrib.rocks/image?repo=MaaXYZ/MaaFramework&max=1000)](https://github.com/MaaXYZ/MaaFramework/graphs/contributors)
