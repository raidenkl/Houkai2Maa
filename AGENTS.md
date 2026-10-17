# Houkai2Maa 项目指南（给人，也给 AI）

崩坏学园2 的 MaaFramework 自动化项目。目标是把「游戏日常」做成一键任务：
启动/登录 → 回主界面 → 领奖（签到/邮件/社团福利）→ 体力刷指定关卡 → 回主界面。

## 技术路线（不要偏离）

**方案二：JSON 流水线 + Agent 自定义逻辑扩展。**

- `assets/resource/pipeline/**`（JSON）：识别、点击、跳转、循环骨架；
- `assets/agent/**`（Python）：只在「代码才自然」的地方介入——
    1. 组合/数值判定（例：体力不足 = 弹窗模板 + OCR 数值）；
    2. 动态流程改写（`context.override_next`）；
    3. 跨节点状态（已刷次数、失败次数、已领状态）；
    4. 设备/环境操作（包名探测、截图落盘）。
- 不要为了「方便」把整条流程写成 Python；那样会失去可视化编辑、可视化调试与统一 UI。

## 目录地图

```tree
assets/interface.json             # 项目接口（PI v2）：controller/resource/group/option/import
assets/resource/
├── default_pipeline.json         # 全局默认参数（rate_limit / threshold 等）
├── pipeline/
│   ├── 00_launch/                # 启动、登录、公告
│   ├── 10_common/                # 通用按钮、弹窗、等待
│   ├── 20_nav/                   # 回主界面、各功能入口
│   ├── 30_daily/                 # 日常业务（签到/邮件/社团/刷本）
│   └── 90_activity/              # 活动业务（阵营战等，随版本变动）
├── image/                        # 模板图（与 pipeline 同构的子目录）
└── model/ocr/                    # OCR 模型（gitignore，由 tools/configure.py 注入）
assets/tasks/                     # PI v2 import 片段（相对 interface.json 解析）
assets/agent/                     # AgentServer：actions/ recognitions/ pretask/ common/ tests/
tools/                            # lint / record / replay / setup
tests/                            # cases(回放) 与 node-cases(离线识别)
docs/zh_cn/develop/               # 开发文档
```

## 六条硬规则（`tools/lint/pipeline_lint.py` 会检查）

1. **状态驱动**：识别 → 操作 → 再识别；禁止假设操作后的画面。
2. **禁止 >1000ms 的固定延迟**：用 `pre_wait_freezes` / `post_wait_freezes`，
   或插入一个识别节点等待目标出现。
3. **业务入口必须有兜底**：`*Entry` 节点的 `next`（或 `on_error`）里必须出现
   `[JumpBack]` 项，处理弹窗/加载/回导航。
4. **坐标基准 1280×720**：所有 `roi`、`target`、模板图都按 720p；
   `interface.json` 的 `display_short_side` 必须是 720。
5. **命名规范**：节点名/文件名/图片路径用 ASCII PascalCase；内部节点 `__` 前缀，
   且禁止被 `assets/tasks/` 直接引用。中文只出现在 `label`/`description`/OCR `expected`。
6. **Custom ID 必须真实注册**：pipeline 里写的 `custom_action` / `custom_recognition`
   必须在 `assets/agent/` 中有同名装饰器，否则 lint 报 E204。

## 常用命令

```bash
python tools/dev/setup.py          # 一次性准备：.pylib 依赖 / OCR 模型 / node_modules 检查
npm run check                      # 框架语义检查（任务树、图片、结构）
npm run test:node                  # 离线节点测试（tests/node-cases）
npm run lint                       # 本项目 pipeline 规范检查（--strict）
npm run lint:py                    # Python 静态检查（ruff）
npm run format:py                  # Python 格式检查（ruff format）
npm run schema                     # JSON Schema 校验
npm run test                       # Agent 单元测试（pytest）
npm run replay                     # 回放录制的端到端用例
npm run verify                     # 以上全部串起来跑
npm run release:check -- --tag vX.Y.Z --strict-git   # 发布前自检（版本/路径/工作区）
npm run format                     # prettier 格式化（含 pipeline 字段排序）
```

联调设备（AI/脚本推荐）：

```bash
uvx maafw-cli connect adb 127.0.0.1:16384
uvx maafw-cli --json ocr                        # 屏幕文字 + 坐标 + 自动截图
uvx maafw-cli --json reco TemplateMatch template=双倍.png threshold=0.8
uvx maafw-cli click e3                          # 点第 3 个 OCR 结果
uvx maafw-cli action custom SaveShot --raw '{"tag":"probe"}'
python tools/dev/snapshot.py                     # 设备截图 + 全屏 OCR + 标注图（无需 uv）
python tools/dev/snapshot.py --image shots/x.png  # 离线 OCR 一张截图（自动缩放到 720p）
python tools/dev/snapshot.py --image shots/x.png --grid  # 额外输出 100px 网格图，按图报坐标
python tools/dev/crop.py --screen <png> --box x,y,w,h --out 30_daily/<Task>/xxx.png --node <Node>
#   ↑ 非 720p 截图会自动缩放（--box 用原图坐标），且拒绝非 16:9
python tools/dev/dryrun.py --images shots/ --entry <Entry>   # 用截图离线跑流程（无需设备）
python tools/dev/probe.py --node <Node> --image shots/x.png  # 单节点命中/框/分数（调阈值）
python assets/agent/pretask/device_prepare.py --image shots/x.png   # 分辨率体检（预任务同款）
python tools/dev/nodecase.py --node <Node> --images shots/   # 截图 → node-case 回归用例
python tools/dev/record.py --case <case> --entry <Entry>
python tools/dev/replay.py --case <case>
```

## 新增一个日常任务（SOP）

1. **取事实**：`maafw-cli` 截图/OCR，把入口坐标、按钮文案、界面层级记到
   `docs/zh_cn/develop/game_facts.md`。**不要凭猜测写坐标或 OCR 文案。**
2. **裁模板**：从 720p 截图裁 `assets/resource/image/30_daily/<Task>/xxx.png`；
   用 `tools/dev/crop.py` 一步完成裁剪 + ROI 计算 + 节点片段生成；
   透明/异形按钮用 green_mask（可用 Auto Green Background 生成绿幕）。
3. **写节点**：在 `30_daily/<Task>.json` 新建文件，节点名用 `<Task>Xxx`；
   先写「界面判定」节点，再写「操作」节点，操作后必须能识别到下一个界面。
4. **写兜底**：入口 `*Entry` 的 `next` 末尾加 `[JumpBack]` 弹窗/加载处理；
   兜底节点都要 `max_hit`。
5. **接 option**：需要的参数（次数、开关、目标）走 `assets/tasks/` 里的 `option`
    - `pipeline_override`，不要写死在 pipeline。
6. **注册任务**：在 `assets/tasks/daily/<Task>.json` 写 `task` 条目，并加入
   `assets/interface.json` 的 `import` 列表，设置 `group`。
7. **验证**：`npm run lint && npm run test && npm run replay`；
   有条件时 `tools/dev/record.py` 录一条用例，提交到 `tests/cases`。

流程描述格式见 `docs/zh_cn/develop/flow_template.md`，需求方按模板描述一次即可转成节点。
当前进度与阻塞项见 `docs/zh_cn/develop/phase_status.md`（先读它再决定做什么）。

## 变更纪律

- 一个 Phase 一个 PR；活动相关代码只动 `90_activity/`，日常骨架保持稳定。
- 提交前跑 `npm run verify`；新增规则豁免必须写进 `tools/lint/allowlist.json`
  并注明移除时间点。
- 游戏事实（坐标、文案、包名、界面层级）以实测为准；未实测的内容标
  `TODO(game_facts)`，不要伪造。

## 禁止事项

- 不手改 `deps/tools/*.schema.json`（由 sync workflow / 手动刷新维护）。
- 不提交 `assets/resource/model/ocr/`（体积大，由 `tools/configure.py` 生成）。
- 不写死固定 sleep、不在 pipeline 里堆 `pre_delay`/`post_delay`。
- 不做自动登录、不输入账号密码；检测到登录界面应停止并提示用户。
- 不引入与框架版本耦合的私有脚本（优先用 `maa-tools` / `maafw-cli` 等社区工具）。

## 排障

完整清单见 `docs/zh_cn/develop/debugging.md`，速查：

1. `debug/maa.log`：框架日志；用 [MaaLogAnalyzer](https://mla.maafw.com/) 看任务流。
2. `debug/on_error/`：失败时的自动截图。
3. `debug/shots/`：`SaveShot` 自定义动作落盘的截图。
4. `debug/agent.log`：Agent 自身日志（含每次 Custom 调用的入参）。
5. 单节点验证：`uvx maafw-cli reco <Type> ...`，或 `tests/node-cases` 离线用例。
