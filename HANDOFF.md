# 交接文档（HANDOFF）

> 给「在新环境里继续开发的 AI / 人」看的单一入口。
> 本文件自包含，不依赖之前会话的对话历史。项目根另有 `AGENTS.md`（会被自动加载）
> 与 `docs/zh_cn/develop/phase_status.md`（进度快照），本文件是它们的汇总与补充。

最后更新：重构进行至「Phase 0 完成、Phase 1 的 Agent/工具/契约就绪，日常节点等待游戏事实」。

---

## 0. 一分钟了解现状

- **项目**：`Houkai2Maa`，基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework)
  的《崩坏学园2》自动化（目标：日常任务一键完成）。
- **技术路线**：**方案二** —— Pipeline(JSON) 负责识别/操作/流程，Agent(Python) 负责
  计数、组合判定、动态改流程、设备准备。**不要**把整条流程写成 Python。
- **基准**：Android ADB 优先；所有 ROI/模板/坐标按 **1280×720（16:9）**；
  `interface.json` 的 `display_short_side` 固定 720。
- **当前可跑通**：`npm run verify` 全绿（73 个 pytest、pipeline lint 0 error/1 allowed、
  schema、replay、ruff、prettier）。阵营战（旧功能）保留在 `90_activity/`。
- **当前阻塞**：日常玩法节点（`00_launch`/`10_common`/`20_nav`/`30_daily`）需要**真实
  游戏截图与流程**才能写；在此之前不要编造坐标/文案。详见 §6。

---

## 1. 新环境 5 分钟上手

### 1.1 前置

| 依赖    | 版本（本机实测） | 说明                                             |
| ------- | ---------------- | ------------------------------------------------ |
| Python  | 3.10+            | 本机 3.10.12                                     |
| Node.js | 22               | CI 用 22；`maa-tools` 需要 Node                  |
| npm     | 10.x             | 本项目用 npm（`package-lock.json` 是权威锁文件） |
| git     | 任意             | 子模块 `assets/MaaCommonAssets` 可选（见 1.3）   |
| adb     | 可选             | 只有真机联调/录制需要                            |

### 1.2 一次性准备

```bash
npm install                      # 若沙箱内 npm 缓存不可写，加 --cache .npm-cache
python tools/dev/setup.py        # 安装 .pylib 依赖（maafw/pytest/pillow/ruff…）+ 准备 OCR 模型
npm run verify                   # 期望：全部通过
```

`setup.py` 做的事：把 Python 依赖装到仓库内 `.pylib`（不用 venv）、把 OCR 模型放进
`assets/resource/model/ocr/`（优先子模块，缺失时从官方 URL 下载）、检查 `node_modules`、
打印 `adb` / `maafw-cli` 的可用性。

### 1.3 本机环境坑（已在仓库里绕过，换机器可能复现）

| 现象                                                                         | 原因                                                      | 仓库里的处理                                                                         |
| ---------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `python -m venv` 失败                                                        | 本机缺 `python3-venv`                                     | 依赖装到 `.pylib`，脚本用 `tools/shared/bootstrap.py` 注入 `sys.path`                |
| `pip install --target .pylib X` 后没有 `bin/`                                | 目标 `bin/` 已存在时 pip 跳过脚本                         | 需要时用 `pip install --target .pylib --upgrade X`（ruff 就是这么装上的）            |
| `npm install` 报 `EACCES ~/.npm`                                             | home 不可写                                               | `npm install --cache .npm-cache`；`tools/dev/maa_tools.py` 已为 maa-tools 设置该 env |
| `maa-tools` 报 `mkdir ~/.maa-tools` 失败                                     | 默认缓存写 home                                           | `maatools.config.mts` 里设了 `maaCache: '.maa-tools'`                                |
| `maa-tools` 偶发 `FetchError ... registry.npmjs.org`                         | 首次要下载 MaaFramework node 包，网络抖动                 | `tools/dev/maa_tools.py` 内置 3 次重试                                               |
| `git submodule update --init` 拉 `MaaCommonAssets` 失败（本机实测失败）      | 网络/协议问题                                             | `tools/configure.py` 在子模块缺失时回退官方 `ppocr_v5` 下载；本地 OCR 已就位         |
| `MaaDbgControllerCreate` 失败                                                | pip 版 maafw 未带 `MaaDbgControlUnit`                     | 自研 `tools/dev/static_controller.py`（用 `CustomController` 把图片当设备）          |
| `Failed to create resource` + 日志含 `MaaAgentServer Not implement this API` | 同进程 import 了 `maa.agent.agent_server`（会替换框架库） | 绝不在驱动 Tasker 的进程里 import Agent 模块；测试用子进程（见 §5.3）                |

### 1.4 工具版本（本机实测，保持一致更省事）

`maafw==5.14.3`、`jsonschema==4.26.0`、`referencing==0.37.0`、`pillow==12.3.0`、
`pytest==9.1.1`、`ruff==0.17.1`、`json-with-comments==1.3.0`；
Node 侧：`@nekosu/maa-tools@1.1.3`、`prettier@3.9.10`、
`prettier-plugin-multiline-arrays@4.1.11`、`@nekosu/prettier-plugin-maafw-sort@1.1.0`。
`maatools.config.mts` 里 `maaVersion: '5.14.3'`（与 Python 侧同版本，避免 beta 漂移）。

> `pnpm-lock.yaml` 是模板遗留、已过期；CI 用的是 `npm ci` + `package-lock.json`。

---

## 2. 仓库结构（谁负责什么）

```tree
assets/interface.json            # PI v2：controller / resource / group / task / preset / option / pretask / agent / import
assets/resource/
├── default_pipeline.json        # 全局默认参数（rate_limit 300、无默认延迟、TM 0.85、OCR 0.4）
├── pipeline/
│   ├── 00_launch/README.md      # 启动/登录契约（暂无节点）
│   ├── 10_common/README.md      # 通用按钮/弹窗契约（暂无节点，等模板）
│   ├── 20_nav/README.md         # 导航契约（暂无节点）
│   ├── 30_daily/README.md       # 日常契约（暂无节点）
│   └── 90_activity/FactionWar.json   # 唯一现有业务：阵营战（旧脚本迁移版）
├── image/{双倍.png,双倍体力兑换.png}  # 阵营战模板（1080p 时代裁的，待按 720p 重拍）
└── model/ocr/                   # gitignore；由 tools/configure.py 生成
assets/tasks/                    # PI import 片段（★ 路径相对 interface.json 所在目录）
├── activity/FactionWar.json     # 任务 + FactionWarDouble（使用双倍券）开关
└── options/                     # 预留
assets/agent/                    # ★ Agent 也必须在 assets/ 下（理由见 §5.1）
├── main.py                      # 入口：注册自定义件 + AgentServer.start_up
├── actions/{farm_loop,save_shot,scene_guard}.py
├── recognitions/{stamina,panel_state}.py
├── pretask/device_prepare.py    # pretask：启动前分辨率体检（--image 可离线）
├── common/{params,state,frame,log,png,context}.py   # 纯逻辑，pytest 覆盖
└── tests/                       # 35 项 agent 测试
tools/
├── configure.py                 # OCR 模型注入（子模块→官方下载回落）
├── install.py                   # 打包（--install-dir/--no-deps + 安装自检）
├── validate_schema.py           # JSON Schema（支持 --exclude-files / --task-dirs）
├── lint/pipeline_lint.py        # 项目规范（见 §4）+ allowlist.json
├── shared/{bootstrap,jsonc,lists,recording,version}.py   # 纯逻辑，pytest 覆盖
├── dev/{setup,snapshot,crop,probe,dryrun,nodecase,record,replay,static_controller,
│        run_tests,run_ruff,maa_tools,release_check}.py
└── tests/                       # 38 项 tools 测试
tests/
├── cases/smoke.json (+README)   # 回放用例（目前只有夹具）
├── fixtures/smoke/              # 纯色/图案夹具：resource+pipeline+screens
├── fixtures/replay/smoke/       # 手写 MaaRecording JSONL + 截图
└── node-cases/                  # maa-tools 节点用例（example.json + README）
docs/zh_cn/develop/              # conventions / ai_workflow / debugging / game_facts /
                                 # flow_template / phase_status / release
AGENTS.md                        # 项目指南（DSH/Claude 自动加载）
.agents/skills/                  # pipeline-guide / agent-guide / add-daily-task（自动发现）
```

---

## 3. 已完成的工作（按 Phase）

### Phase 0 — 地基 ✅

- 720p 基准（interface + default_pipeline.json）；旧 1080p 痕迹清除
- 目录分层；阵营战迁入 `90_activity/FactionWar.json`，节点名改 ASCII PascalCase
- 清理：`empty.png`(1 字节)、未引用模板、`阵营战(使用助战).jsonbak`、`my_action.py`/`my_reco.py`
- schema 刷新到 MaaFramework main；`@nekosu/maa-tools` 1.0.23 → 1.1.3
- CI（`.github/workflows/check.yml`）扩为 10 步：maa-tools check、node 用例、pip 依赖、
  OCR 准备、schema、pipeline lint、ruff check、ruff format、pytest、prettier、replay
- `docs/`、`AGENTS.md`、`.agents/skills/`、PR 模板、分层 README

### Phase 1 — Agent 骨架 ✅ / L0·L1 节点 ⛔（缺事实）

- 自定义动作：`FarmLoop`（计数+收敛）、`FarmReset`、`FarmFail`（失败上限）、
  `FarmNote`（体力不足打标，一次性消费）、`SceneGuard`（用已有节点做场景校验）、
  `SaveShot`（截图落盘，标准库 PNG 编码，无 Pillow 依赖）
- 自定义识别：`StaminaInsufficient`（可复用节点或直接 OCR）、`PanelState`（已领/可领）
- `common/`：参数校验、循环状态机、尺寸判定、日志（stdout + `debug/agent.log`）、
  PNG 编码、`PI_*` 上下文
- `pretask DevicePrepare`：启动前分辨率体检（单设备严格、多设备仅告警、
  支持 `MAAHOUKAI2_ADB_ADDRESS`）
- 离线工具链（见 §4.2）与 46 项 tools 测试

### Phase 4 — 契约提前完成 🟡

- PI `import`（`assets/tasks/`）、`preset ActivityOnly`、`pretask`、`option`
  （`FactionWarDouble` 开关 → `pipeline_override`）
- 安装包自检：`install/interface.json` 的 import / pretask.args / agent.child_args 必须可解析
- 阵营战去掉 30s 固定等待（`timeout=120000 + rate_limit=2000` 识别驱动），删除 E105 豁免
- 未完成：阵营战 720p 模板重拍（需要 720p 截图，步骤见 `game_facts.md` §8）、
  日常任务的 option/global_option/setting（要有节点才有意义）

### Phase 2 / 3 / 5 ⛔

全部依赖真实界面事实（见 §6）。

### 提交历史（本重构，最近 → 最早）

```
455a6c0 工具与文档: crop 支持非 720p 截图自动缩放；Win32 实测与阵营战重拍清单
efca79c 阵营战: 去掉 30s 固定等待，改为识别驱动（删除 E105 豁免）
f3b5f62 发布基建: release_check 自检、版本一致性工具、发布清单与仓库占位符
e2e59aa 文档: 新增 phase_status.md（进度快照 / 阻塞项 / 技术债清单）
ed3df13 质量: 引入 ruff（静态检查 + 格式化），接入 verify 与 CI
15594b6 测试与打包: Agent 入口冒烟、安装自检、Agent/框架不能同进程的硬限制
71c2385 工具与契约: nodecase 生成器、dryrun 序列断言、preset 与校验
8505330 预任务: 多设备安全策略与 PI_* 事实修正
4b29c64 布局与预任务: agent 迁入 assets/agent，新增启动前分辨率体检
f222135 工具: snapshot --grid 生成坐标网格图，便于按图报坐标
48fe77f 工具: 录制文件校验（shared/recording.py）接入 record/replay
6cefacb 契约: 任务片段迁到 assets/tasks 并接入 PI import（含阵营战选项）
d792e34 工具: probe.py 单节点探测 + 回放夹具与引擎回归
f81790a Agent: FarmNote 显式打标「体力不足」，供循环决策消费
84a8137 质量: interface 引用校验、排障手册、schema 同步修正与 replay 健壮性
06c85e6 测试: 离线流程回归（smoke fixture + dryrun 集成测试）与 tasks 脚手架
3868b46 工具: 离线工作流（snapshot --image / dryrun / 静态控制器）与更严的 lint
07ac5aa 工具: 新增 crop.py（裁剪模板+生成节点片段）与流程描述模板
bda16ab 文档: 分层目录说明、PR 模板与离线节点用例模板
d487f0c 重构: Phase 0 地基（720p 基准 / Agent 骨架 / 工具链 / CI）
```

---

## 4. 验证体系与命令

### 4.1 一条命令

```bash
npm run verify
# = check && test:node && lint && lint:py && schema && test && replay && format:check && format:py
```

| 子命令                                  | 作用                                                             | 需要设备 |
| --------------------------------------- | ---------------------------------------------------------------- | -------- |
| `npm run check`                         | `@nekosu/maa-tools check`：任务树、图片路径、pipeline 结构       | 否       |
| `npm run test:node`                     | `maa-tools test`：`tests/node-cases` 的「截图→命中节点」         | 否       |
| `npm run lint`                          | 项目规范（§4.3，`--strict`）                                     | 否       |
| `npm run lint:py` / `format:py`         | ruff 检查 / 格式检查（`tools/dev/run_ruff.py`）                  | 否       |
| `npm run schema`                        | JSON Schema（interface + pipeline + `--task-dirs assets/tasks`） | 否       |
| `npm run test`                          | pytest：`assets/agent/tests`（35）+ `tools/tests`（38）= 73 项   | 否       |
| `npm run replay`                        | 回放 `tests/cases/*.json`（目前只有 fixture 用例）               | 否       |
| `npm run format` / `format:check`       | prettier（含 pipeline 字段排序插件）                             | 否       |
| `npm run release:check -- --tag vX.Y.Z` | 版本/tag 一致性、路径、工作区                                    | 否       |

### 4.2 离线开发工具（无设备也能干活）

| 命令                                                                                         | 用途                                                                        |
| -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `python tools/dev/snapshot.py [--image x.png] [--grid]`                                      | 设备截图或离线截图 → OCR 文本+坐标、标注图、网格图                          |
| `python tools/dev/crop.py --screen <png> --box x,y,w,h --out 30_daily/X/btn.png --node Name` | 裁模板 + 生成节点片段；**非 720p 自动缩放**（box 用原图坐标），非 16:9 拒绝 |
| `python tools/dev/probe.py --node X --image <png>`                                           | 单节点命中/框/分数（会校验节点是否存在）                                    |
| `python tools/dev/dryrun.py --images <dir> --entry E --expect A,B`                           | 用一组截图跑流程并断言节点序列                                              |
| `python tools/dev/nodecase.py --node X --images <dir>`                                       | 批量生成 `tests/node-cases` 用例（截图自动归档）                            |
| `python tools/dev/record.py --case c --entry E`                                              | 真机录制（含录制文件校验）                                                  |
| `python tools/dev/replay.py --all [--require]`                                               | 离线回放（缺录制默认跳过，`--require` 视为失败）                            |
| `python tools/dev/release_check.py --tag vX`                                                 | 发布前自检                                                                  |
| `python assets/agent/pretask/device_prepare.py --image x.png`                                | 分辨率体检（与 pretask 同逻辑）                                             |

联调设备推荐 [maafw-cli](https://github.com/otowa-kotori/maafw-cli)（`uvx maafw-cli`）：
`connect adb / ocr / reco / click e3 / pipeline run / action custom`，`--json` 输出。

### 4.3 项目 lint 规则（`tools/lint/pipeline_lint.py`）

E001 JSONC 解析、E004 命名、E101 模板缺失、E102 扩展名大小写、E103 ROI 越界、
E105 >1000ms 固定延迟、E110 Adb `display_short_side≠720`、E111 坐标字段越界、
E204 Custom ID 未注册、E206 interface/任务 entry 不存在或任务重名、
E207 import 文件缺失、E209 用内部节点做 entry、E214 `max_hit`/`enabled` 类型、
E216 StartApp/Shell 缺参数、E217 group/controller/resource 引用不存在、
E218 option 引用不存在、E219 pretask 脚本缺失、E220 preset 引用不存在；
W004 非 PascalCase、W101 rate_limit 过小、W200 节点不可达、W206 override 指向不存在节点、
W211 自引用无 max_hit、W212/213 OCR 文案质量、W210 图片未引用。

豁免写在 `tools/lint/allowlist.json`（当前只剩 1 条：阵营战 E203，因通用弹窗
`CommonPopupAny` 需要真实模板才能建）。**新增豁免必须说明移除时间点。**

---

## 5. 关键事实与踩坑（不要重新发现）

### 5.1 PI 的相对路径 → `agent/` 与 `tasks/` 必须在 `assets/` 下

`agent.child_args` 与 `pretask.args`、`import` 都**相对 `interface.json` 所在目录**解析，
而 `interface.json` 在 `assets/`。所以目录是 `assets/agent/`、`assets/tasks/`，
安装包里则是 `install/agent/`、`install/tasks/`（`install.py` 负责重排）。

### 5.2 pretask（MFAAvalonia 实测，v2.7+ 支持）

- `WorkingDirectory = interface.json 目录`；
- **不注入 `PI_*`**（只有 Agent 子进程注入，见 `AgentHelper.ApplyPiEnvironmentVariables`）；
- 控制器过滤靠 `pretask.controller` 字段；
- 退出码非 0 = 中止启动。多设备时无法得知用户选了哪台 → 只告警不阻断。

### 5.3 Agent 与框架不能在同一进程

`import maa.agent.agent_server` 会把已加载的框架库替换为 `MaaAgentServerNotImpl`，
之后 `Resource()`/`Tasker()` 必然失败。Agent 模块只能由 Client 作为子进程启动；
测试要验证注册表时用子进程（`assets/agent/tests/test_entry.py` 已示范）。

### 5.4 Pipeline 行为（实测）

- `pipeline_override` 是**字段合并**：只写 `{"next": []}` 不会清掉 `recognition`；
- 入口未命中时框架会按 `timeout`（默认 20s）反复识别后才判失败 →
  离线探测把 `timeout` 调小（`probe.py` 默认 2000ms），否则一次 miss 空等 20s；
- `DirectHit` 节点在 `next` 里会无条件命中，不要拿它当兜底；
- 纯色/无纹理模板在 `TM_CCOEFF_NORMED` 下会退化误命中（本仓库 smoke 夹具踩过，
  已改成条纹/棋盘图案）。

### 5.5 录制/回放格式

`RecordController` 写 JSONL，每行 `{type,timestamp,success,cost,...}`：
`connect` 带 `uuid/width/height`，`screencap` 带 `path`（相对 JSONL 目录），
`click` 带 `x/y`。`tools/shared/recording.py` 会校验完整性；
手写样例见 `tests/fixtures/replay/smoke/smoke.jsonl`。

### 5.6 外部仓库地址变更

MFAAvalonia 已迁到 **`MaaXYZ/MFAAvalonia`**（`install.yml`、README 已更新）。
`maafw-cli` 仍是实验性项目（接口可能变），只用于开发期联调，不进 CI 关键路径。

### 5.7 环境隔离约定

所有本地依赖与产物都在仓库内且被 `.gitignore` 忽略：
`.pylib/`（Python 依赖）、`.pip-cache/`、`.npm-cache/`、`.maa-tools/`（Node 版 MaaFW）、
`node_modules/`、`debug/`（日志/截图/probe 产物）、`on_error/`。
**不要提交** `assets/resource/model/ocr/`。

---

## 6. 剩余工作与需要的输入（阻塞点）

### 6.1 必须由用户提供（三选一）

1. **720p 截图**（推荐）：主界面；签到/邮件/社团/出击入口；各自面板（含已领取形态）；
   刷本关卡列表、备战页、结算页；体力不足/双倍券/公告等弹窗。
   非 720p 可接受（`crop.py` 会缩放），带坐标需求可用 `snapshot.py --image x.png --grid`。
2. **流程文字**：按 `docs/zh_cn/develop/flow_template.md` 描述
   「在哪个界面 → 点什么 → 到哪个界面」+ 分支（已领取/体力不足/弹窗）/参数/结束条件。
3. **可达的 adb 地址**（如 `127.0.0.1:16384`）：直接采集与调试。

### 6.2 拿到输入后的固定 SOP（出节点不靠猜）

```bash
# 1) 事实：截图 → OCR 文案与坐标（+网格图）
python tools/dev/snapshot.py --image shots/home.png --grid
# 2) 模板 + 节点片段
python tools/dev/crop.py --screen shots/home.png --box <x>,<y>,<w>,<h> \
    --out 30_daily/SignIn/btn.png --node DailySignInButton --pad 20
# 3) 校阈值
python tools/dev/probe.py --node DailySignInButton --image shots/home.png
# 4) 写节点（按 .agents/skills/add-daily-task/SKILL.md 的 SOP）→ 兜底 → option
# 5) 离线验证
python tools/dev/dryrun.py --images shots/ --entry DailySignInEntry --expect DailySignInMain,DailySignInClaim
npm run nodecase -- --node DailySignInButton --images shots/
npm run verify
# 6) 真机（有设备时）
uvx maafw-cli pipeline run DailySignInEntry
python tools/dev/record.py --case signin --entry DailySignInEntry
```

### 6.3 建议的推进顺序

1. `10_common`：确认/取消/关闭/返回/加载/通用弹窗（用真实截图裁模板）→ 解除 E203 豁免；
2. `20_nav`：`NavHomeFlag` / `NavHome` / 各入口；
3. `00_launch`：启动（`StartApp` 失败回落 `Shell` + `monkey -p`）、登录检测（命中即 `StopTask`）；
4. `30_daily/SignIn`（最简单，打通闭环）→ `Mail` / `ClubWelfare`；
5. `30_daily/Farm`：`FarmLoop`/`FarmNote`/`FarmFail` 已就位，补节点与 option；
6. 阵营战 720p 模板重拍（`game_facts.md` §8）；
7. Phase 5：真机 20 次回归 → `release.md` 流程发 `v2.0.0`。

---

## 7. 质量约束（来自 AGENTS.md，违反会被 lint/CI 拦下）

1. 识别 → 操作 → 再识别，禁止假设操作后画面；
2. 禁止 >1000ms 固定延迟（用 `pre/post_wait_freezes` 或中间识别节点）；
3. 业务 `*Entry` 的 `next` 必须含 `[JumpBack]` 兜底，兜底节点要有 `max_hit`；
4. 一切坐标/ROI/模板按 1280×720；
5. 节点名/文件名/图片路径 ASCII PascalCase，内部节点 `__` 前缀且不能被 `tasks` 直接引用；
6. `Custom` 的 ID 必须在 `assets/agent/` 真实注册（E204）；
7. 不做自动登录/不输入账号密码；
8. 改动前跑 `npm run verify`，新增豁免登记到 `allowlist.json`。

---

## 8. 已知技术债 / 限制

| 项                                           | 位置                          | 处理                                             |
| -------------------------------------------- | ----------------------------- | ------------------------------------------------ |
| 阵营战缺通用弹窗兜底（E203 豁免）            | `tools/lint/allowlist.json`   | `10_common` 建好后删除                           |
| 阵营战模板仍是 1080p 时代裁的                | `assets/resource/image/*.png` | 按 `game_facts.md` §8 重拍                       |
| 回放用例只有 smoke 夹具                      | `tests/cases/`                | 有设备后录真实用例                               |
| Win32 控制器未验证（窗口类名/截图方式）      | `assets/interface.json`       | 按 `game_facts.md` §7 实测后转正或移除           |
| `pnpm-lock.yaml` 过期                        | 仓库根                        | 如改用 pnpm 请重新生成；当前以 npm 为准          |
| 子模块 `assets/MaaCommonAssets` 本机未初始化 | `.gitmodules`                 | CI 用 submodules；本地由 `configure.py` 回退下载 |

---

## 9. 交接自检清单

在新环境执行并全部通过，才算「环境可接手」：

- [ ] `npm install`（必要时 `--cache .npm-cache`）
- [ ] `python tools/dev/setup.py`（OCR 三个文件存在：`det.onnx`/`rec.onnx`/`keys.txt`）
- [ ] `npm run verify` → 全绿（期望 pytest 73、lint 0 error/1 allowed）
- [ ] `python tools/dev/dryrun.py --resource tests/fixtures/smoke/resource --images tests/fixtures/smoke/screens --entry SmokeEntry --once --expect SmokeStepA,SmokeStepB` → 成功
- [ ] `python tools/dev/probe.py --resource tests/fixtures/smoke/resource --node SmokeStepA --image tests/fixtures/smoke/screens/01-home.png` → HIT，box `[100,100,120,80]`
- [ ] `python tools/dev/release_check.py --tag v2.0.0-dev.1` → 通过（当前 `interface.version` 为 `2.0.0-dev.1`）
- [ ] 读 `AGENTS.md`、`.agents/skills/*`、`docs/zh_cn/develop/phase_status.md`
- [ ] 有设备时：`uvx maafw-cli connect adb <地址>` → `--json ocr` 有输出

---

## 10. 外部参考

- MaaFramework 文档：<https://maafw.xyz/docs/1.1-QuickStarted>（协议：`3.1-任务流水线协议`、`3.3-ProjectInterfaceV2`）
- 项目接口样例与 schema：MaaFramework 仓库 `tools/*.schema.json`（本仓库 `deps/tools/` 已同步）
- 社区工具：`maa-support`（VSCode）、`MaaPipelineEditor`、`MaaDebugger`、`MaaLogAnalyzer`、
  `maafw-cli`、`Auto Green Background`（绿幕模板）、`ImageCropperQt`
- 参考项目：MaaEnd（分层/技能/预任务写法）、MAABH3（旧版流派，仅历史参考）
