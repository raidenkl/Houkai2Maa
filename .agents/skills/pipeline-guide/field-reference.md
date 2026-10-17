# Pipeline 字段速查（MaaFramework v5）

> 以官方协议为准：<https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.1-任务流水线协议.md>
> 本表只收录本项目常用字段，默认值来自框架（`default_pipeline.json` 会覆盖其中一部分）。

## 节点通用字段

| 字段                                              | 类型                   | 默认                    | 说明                                                 |
| ------------------------------------------------- | ---------------------- | ----------------------- | ---------------------------------------------------- |
| `recognition`                                     | object                 | `{"type": "DirectHit"}` | v2 形式 `{type, param}`；本项目禁止 v1 字符串形式    |
| `action`                                          | object                 | `{"type": "DoNothing"}` | 同上                                                 |
| `next`                                            | string / object / list | `[]`                    | 后继候选，按顺序识别，首个命中即执行                 |
| `on_error`                                        | 同上                   | `[]`                    | 识别超时或动作失败后执行                             |
| `timeout`                                         | int                    | 20000                   | `next` 识别超时（ms），-1 永不超时                   |
| `rate_limit`                                      | int                    | 1000（本项目默认 300）  | 两次识别的最小间隔                                   |
| `pre_delay`                                       | int                    | 200（本项目默认 0）     | 识别到 → 执行动作前的等待，**本项目 >1000 禁止**     |
| `post_delay`                                      | int                    | 200（本项目默认 0）     | 动作后 → 识别 next 前的等待，**同样限制**            |
| `pre_wait_freezes` / `post_wait_freezes`          | int / object           | 0                       | 等待画面静止（`{time, target, timeout, threshold}`） |
| `repeat` / `repeat_delay` / `repeat_wait_freezes` | int                    | 1 / 0 / 0               | 动作重复                                             |
| `inverse`                                         | bool                   | false                   | 反转识别结果                                         |
| `enabled`                                         | bool                   | true                    | 是否启用（option 常用来开关节点）                    |
| `max_hit`                                         | int                    | 无上限                  | 最大命中次数，超过后跳过（兜底节点必设）             |
| `anchor`                                          | string / list / object | ""                      | 设置锚点；配合 `[Anchor]Name` 动态引用               |
| `focus`                                           | object                 | null                    | 节点通知（可上报给 UI/日志）                         |
| `attach`                                          | object                 | {}                      | 附加配置，dict merge                                 |

## 识别类型

| 类型                               | 关键参数                                                              | 用法要点                      |
| ---------------------------------- | --------------------------------------------------------------------- | ----------------------------- |
| `DirectHit`                        | `roi`                                                                 | 不识别，直接动作（谨慎使用）  |
| `TemplateMatch`                    | `template`(必填), `roi`, `threshold`(0.85), `method`(5), `green_mask` | 最常用；先收窄 roi            |
| `FeatureMatch`                     | `template`, `detector`(SIFT), `ratio`(0.6), `count`                   | 缩放/遮挡更稳，速度较慢       |
| `ColorMatch`                       | `lower`, `upper`, `method`(HSV=40), `count`                           | 状态点、血条等纯色元素        |
| `OCR`                              | `expected`, `roi`, `threshold`(0.4)                                   | 写完整文本；可 `replace` 纠错 |
| `NeuralNetworkClassify` / `Detect` | `model`, `labels`, `expected`                                         | 需要模型文件，P0 暂不使用     |
| `And`                              | `all_of`                                                              | 多个识别同时命中              |
| `Or`                               | `any_of`                                                              | 任一命中                      |
| `Custom`                           | `custom_recognition`, `custom_recognition_param`                      | Agent 中注册，ID 由 lint 校验 |

## 动作类型

| 类型                                              | 关键参数                               | 说明                                          |
| ------------------------------------------------- | -------------------------------------- | --------------------------------------------- |
| `DoNothing`                                       | —                                      | 默认                                          |
| `Click`                                           | `target`(true), `target_offset`        | 点识别结果中心                                |
| `LongPress`                                       | `duration`                             | 本项目默认 300ms                              |
| `Swipe`                                           | `begin`, `end`, `duration`             | 列表滚动、返回手势                            |
| `MultiSwipe`                                      | `swipes`                               | 多指                                          |
| `Scroll`                                          | `target`, `dx`, `dy`                   | 仅 Win32                                      |
| `ClickKey` / `LongPressKey` / `KeyDown` / `KeyUp` | `key`                                  | 虚拟键码                                      |
| `InputText`                                       | `input_text`                           | 输入文本                                      |
| `StartApp` / `StopApp`                            | `package`                              | 启动/停止应用                                 |
| `StopTask`                                        | —                                      | 结束当前任务链                                |
| `Command`                                         | `exec`, `args`                         | 执行外部程序（支持 `{IMAGE}`/`{BOX}` 等替换） |
| `Shell`                                           | `cmd`                                  | ADB shell（如 `monkey -p <pkg> 1`）           |
| `Screencap`                                       | —                                      | 仅截图                                        |
| `Custom`                                          | `custom_action`, `custom_action_param` | Agent 中注册                                  |

## 节点属性（写在 next/on_error 的名字上）

| 语法                                                | 含义                                                      |
| --------------------------------------------------- | --------------------------------------------------------- |
| `[JumpBack]Xxx` / `{"name":"Xxx","jump_back":true}` | 命中后执行 Xxx 链并**跳回父节点**继续识别；错误路径不跳回 |
| `[Anchor]Name` / `{"name":"Name","anchor":true}`    | 引用「最后设置该锚点的节点」；锚点不存在则跳过            |

## 执行生命周期

```
pre_wait_freezes → pre_delay → action
  → [repeat_wait_freezes → repeat_delay → action] × (repeat-1)
  → post_wait_freezes → post_delay → 截图 → 识别 next
```

`next` 全未命中且超时 → 走 `on_error`；`next` 为空 → 任务结束（若有 `[JumpBack]` 先回跳）。

## 默认值文件

`assets/resource/default_pipeline.json` 可设置四类默认值，优先级：

```
节点显式字段 > 本文件「算法/动作名」下的默认 > 本文件 Default > 框架内置
```

本项目当前值：`rate_limit 300`、`timeout 20000`、`pre/post_delay 0`、
`TemplateMatch.threshold 0.85`、`OCR.threshold 0.4`。
