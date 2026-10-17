---
name: pipeline-guide
description: 编写/修改 Houkai2Maa 的 MaaFramework Pipeline JSON 指南。用于新增或审查 assets/resource/pipeline 下的节点、选择识别算法与动作、处理弹窗兜底、调整延迟与 ROI。包含本项目六条硬规则、字段速查与常见错误。
---

# Pipeline 编写指南（Houkai2Maa）

本项目是 **MaaFramework Pipeline v2**（`recognition` / `action` 为对象）。
完整协议见官方文档：
<https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.1-任务流水线协议.md>

## 六条硬规则（违反会被 `npm run lint` 拦下）

1. **状态驱动**：识别 → 操作 → 再识别。每次点击后必须能识别到「操作成功后的界面」，
   不要假设操作成功。
2. **禁止 >1000ms 的固定延迟**。需要等待时用：
    - `post_wait_freezes: {"time": 200, "target": [0,0,0,0]}`（等画面静止）
    - 或插入一个「目标界面」识别节点作为中间步骤
3. **业务入口必须有 `[JumpBack]` 兜底**（`*Entry` 节点），例如：

    ```jsonc
    "DailySignInEntry": {
        "next": [
            "DailySignInMain",
            "[JumpBack]CommonPopupAny",
            "[JumpBack]CommonLoading",
            "[JumpBack]NavHome"
        ]
    }
    ```

    兜底节点自身要设 `max_hit`，避免死循环。

4. **坐标基准 1280×720（16:9）**：`roi`、`target`、模板图全部按 720p。
   `interface.json` 的 `display_short_side` 固定 720。
5. **命名规范**：节点名 ASCII PascalCase（`DailySignInMain`），内部节点 `__` 前缀
   （`__FarmWaitResult`）且禁止被 `tasks/` 直接引用；文件名/图片路径同样 ASCII。
6. **Custom ID 必须注册**：`custom_action` / `custom_recognition` 的字符串必须在
   `agent/` 中有同名装饰器（lint 规则 E204）。

## 目录分层（放对地方）

| 层          | 目录           | 放什么                                 |
| ----------- | -------------- | -------------------------------------- |
| L0 通用     | `10_common/`   | 确认/取消/关闭/返回/加载/网络错误/公告 |
| L1 导航     | `20_nav/`      | `NavHome`、各功能入口 `NavEnterXxx`    |
| L2 日常业务 | `30_daily/`    | 签到、邮件、社团福利、刷本             |
| L2 活动业务 | `90_activity/` | 随版本变动的活动（阵营战等）           |

不跨层反向依赖：L2 可以引用 L0/L1；L0 不能引用 L2。

## 推荐写法

### 找图（最常用）

```jsonc
{
    "recognition": {
        "type": "TemplateMatch",
        "param": {"template": "30_daily/SignIn/button.png", "roi": [900, 500, 300, 200]},
    },
    "action": {"type": "Click"},
}
```

- 模板图从 **720p 截图**裁剪；先限定 `roi` 再匹配，命中率与性能都更好；
- 阈值默认 0.85（见 `default_pipeline.json`）；反复误命中时优先缩小 roi，
  而不是无限调高阈值；
- 异形/透明按钮用 `green_mask: true` + 绿幕图（Auto Green Background 生成）。

### OCR（大字号按钮、数值）

```jsonc
{
    "recognition": {
        "type": "OCR",
        "param": {"expected": ["签到"], "roi": [40, 600, 260, 100]},
    },
    "action": {"type": "Click"},
}
```

- `expected` 写**完整**文本，不要写单个字；
- OCR 不稳时用 `And` 组合（按钮背景模板 + 文字），比调阈值可靠。

### 组合判定

```jsonc
{"recognition": {"type": "And", "param": {"all_of": ["XxxFrame", "XxxTitle"]}}}
{"recognition": {"type": "Or",  "param": {"any_of": ["XxxA", "XxxB"]}}}
```

### 显式场景校验（需要「确认现在在哪」时）

```jsonc
{
    "action": {
        "type": "Custom",
        "param": {
            "custom_action": "SceneGuard",
            "custom_action_param": {"node": "NavHomeFlag", "expect": "Home", "on_mismatch": ["NavHome"]},
        },
    },
}
```

### 循环计数

```jsonc
{
    "action": {
        "type": "Custom",
        "param": {
            "custom_action": "FarmLoop",
            "custom_action_param": {"max_times": 0, "until_no_stamina": true},
        },
    },
    "next": ["FarmAgain"],
}
```

达到停止条件时 `FarmLoop` 会清空 `next`，任务自然结束。

体力不足不要靠猜：用「识别 → 打标 → 由循环决策」三段式：

```jsonc
{
    "FarmStaminaPopup": {
        "recognition": {
            "type": "Custom",
            "param": {
                "custom_recognition": "StaminaInsufficient",
                "custom_recognition_param": {"node": "CommonPopupStamina"},
            },
        },
        "action": {
            "type": "Custom",
            "param": {"custom_action": "FarmNote", "custom_action_param": {"stamina_insufficient": true}},
        },
        "next": ["FarmAfterStamina"],
    },
}
```

`FarmNote` 的标记只被下一次 `FarmLoop` 消费一次；若用户选「停止」，
再加一个自定义动作/`StopTask` 收尾，不要让流程自己猜。

## 常见错误速查

| 症状             | 原因                                      | 处理                             |
| ---------------- | ----------------------------------------- | -------------------------------- |
| 一直点同一个按钮 | 点击后没识别新界面，`next` 立刻又命中自己 | 加中间识别节点；必要时 `max_hit` |
| 卡在加载界面     | 没有加载兜底                              | `[JumpBack]CommonLoading`        |
| 误触发别的界面   | roi 太大 / 模板太宽泛                     | 缩小 roi、裁剪更独特的局部       |
| ROI 越界         | 用非 720p 截图算的坐标                    | 重算坐标（lint E103 会报）       |
| 改了 ID 但没生效 | Custom ID 拼错                            | lint E204 会指出未注册的 ID      |

## 调参与覆盖（实测结论）

- `pipeline_override` 是**字段合并**：只写 `{"next": []}` 不会清掉 `recognition`，
  所以 option 覆盖只写需要改的字段即可。
- 调阈值先用 `probe.py` 在真实截图上量：「命中框 + 分数」比盲调 0.8/0.9 可靠。
- 未命中的节点在任务里会按 `timeout`（默认 20s）反复重试；
  离线探测时把 `timeout` 调小（`probe.py` 默认 2000ms），否则批量探测很慢。

## 字段速查

见同目录 `field-reference.md`（按生命周期顺序）。
