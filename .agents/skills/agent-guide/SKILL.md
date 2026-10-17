---
name: agent-guide
description: 在 Houkai2Maa 的 agent/ 下新增或修改自定义动作/自定义识别（MaaFramework AgentServer）。包含职责边界、注册与命名、参数约定、日志、单测与 lint 校验方式。用于实现需要计数、组合判定、动态改流程或设备操作的逻辑。
---

# Agent 自定义件开发指南（Houkai2Maa）

本项目采用 **方案二**：pipeline(JSON) 管流程与识别，Agent(Python) 只做
「代码才自然」的事。新增 Custom 之前先自问：

| 需求                                | 放哪                                             |
| ----------------------------------- | ------------------------------------------------ |
| 单步识别 + 点击 / 跳转              | JSON                                             |
| 常量比较、开关                      | JSON（option + `enabled`）                       |
| 组合判定（模板 + OCR + 数值）       | **Agent**（CustomRecognition）                   |
| 计数 / 到点结束 / 按条件改 `next`   | **Agent**（CustomAction）                        |
| 跨节点状态（已领、已刷次数）        | **Agent**（模块级状态 + FarmReset 之类重置动作） |
| 设备/环境操作（截图落盘、包名探测） | **Agent**（CustomAction）                        |

## 目录与注册

```tree
agent/
├── main.py                     # 唯一入口：register_all() + AgentServer.start_up
├── actions/
│   ├── __init__.py             # MODULES + register_all() -> list[str]
│   ├── farm_loop.py            # FarmLoop / FarmReset
│   ├── scene_guard.py          # SceneGuard
│   └── save_shot.py            # SaveShot
├── recognitions/
│   ├── __init__.py
│   ├── stamina.py              # StaminaInsufficient
│   └── panel_state.py          # PanelState
├── common/                     # 纯逻辑（禁止 import maa，便于 pytest）
│   ├── params.py               # 参数校验
│   ├── state.py                # 循环/面板状态（纯函数）
│   ├── context.py              # 读取 PI_* 环境变量
│   └── log.py
└── tests/                      # pytest：只测 common + 纯函数
```

新增一个自定义件：

1. 在 `actions/` 或 `recognitions/` 新建模块；
2. 用 `@AgentServer.custom_action("<ID>")` / `@AgentServer.custom_recognition("<ID>")` 注册；
3. 模块里定义 `REGISTERED = ["<ID>"]`；
4. 在对应 `__init__.py` 的 `MODULES` 里加上模块；
5. pipeline 里写同名字符串；`npm run lint` 会校验 ID 是否存在（E204）。

命名：ID 用 PascalCase，和 pipeline 完全一致；节点名可以不同，但建议一致便于排查。

## 参数约定

- pipeline 传进来的是 **JSON 字符串**（`argv.custom_action_param`），必须自行 `json.loads`；
- 解析统一走 `common/params.py`（`as_int` / `as_bool` / `as_str` / `as_str_list`），
  非法参数抛 `ParamError`，在 `run/analyze` 里捕获后**记日志并返回 False/None**，
  不要静默吞掉；
- 参数名用小写 snake_case（`max_times`、`until_no_stamina`、`claimed_node`）；
- 不要在参数里塞大对象；阈值/节点名这类「可变配置」放参数里，别硬编码。

## 实现要点

- 点击/滑动一律 `context.tasker.controller.post_click(x, y).wait()` 这类异步接口，
  保证能被 `RecordController` 录制、被回放复现；
- 需要截图用 `context.tasker.controller.post_screencap().wait().get()`，
  或读 `cached_image`（省一次截图）；
- 复用已有识别：
    1. 节点名：`context.run_recognition(node_name, image)`；
    2. 临时参数：`context.run_recognition_direct(JRecognitionType.OCR, JOCR(...), image)`；
- 改流程：`context.override_next(argv.node_name, ["Xxx"])`（传 `[]` 即结束该链）；
- 需要「当前在哪」时用 `SceneGuard` 思路：拿一个已有判定节点跑一次识别，别自己造判定；
- 需要读 Client/资源信息：`common.context.client_context()`（读取 `PI_*` 环境变量）；
- 日志用 `common.log.get_logger("action.xxx")`，会同时写 stdout 和 `debug/agent.log`。

## 单测与验证

```bash
npm run test        # pytest agent/tests
npm run lint        # 校验 pipeline 里引用的 Custom ID 是否注册
uvx maafw-cli action custom FarmLoop --raw '{"max_times":1}'
```

- 把**纯逻辑**（计数、状态推导、参数校验）放 `common/`，单测直接 import；
- 涉及 MAA API 的部分保持薄，只做「取数据 → 调纯逻辑 → 执行副作用」；
- 新增/修改行为时同步更新 `.agents/skills/agent-guide/SKILL.md` 里的示例。

## 反模式

- ❌ 在 agent 里写「大流程」（整条日常用 Python 串起来）→ 失去可视化与统一 UI；
- ❌ 在 custom_action 里用 `time.sleep` 等界面 → 用识别节点 / `pre_wait_freezes`；
- ❌ 把游戏坐标写死在 Python 里 → 坐标属于 pipeline；
- ❌ 自定义件里直接 `print` 调试 → 用 logger，日志才会进 `debug/agent.log`。
