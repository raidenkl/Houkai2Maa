---
name: add-daily-task
description: 在 Houkai2Maa 中新增一个日常任务的完整步骤（取游戏事实 → 裁模板 → 写流水线节点 → 兜底 → 接 option → 注册任务 → 验证与录制）。用于扩展签到、邮件、社团福利、刷本之外的日常玩法。
---

# 新增一个日常任务

前置：已读 `AGENTS.md` 的六条硬规则；已有可连接的设备（模拟器）或现成截图。

## 0. 先确认三件事

1. 这个玩法是否**每天都要做**？只做一次的不要进 `daily`，放 `90_activity` 或工具。
2. 入口在哪里（主界面哪个按钮/菜单几层）？
3. 完成/已领取的状态长什么样？（决定「跳过」逻辑）

## 1. 取事实（不许猜）

```bash
uvx maafw-cli connect adb 127.0.0.1:16384
uvx maafw-cli --json ocr            # 文案 + 坐标 + 自动截图
uvx maafw-cli screenshot -o debug/probe/entry.png
```

把结果记到 `docs/zh_cn/develop/game_facts.md`：

| 场景       | 截图          | 关键文案       | 坐标（720p） | 备注 |
| ---------- | ------------- | -------------- | ------------ | ---- |
| 主界面入口 | `main-01.png` | 签到/邮件/社团 | …            |      |

截图必须缩放到 **1280×720** 后再量坐标。

## 2. 裁模板

```bash
python tools/dev/crop.py \
    --screen debug/probe/xxxx-screen.png \
    --box 980,560,120,60 \
    --out 30_daily/<TaskName>/button.png \
    --node <TaskName>Button --pad 20
```

- 工具会校验截图是 1280×720，裁剪模板并打印带 ROI 的节点片段，直接粘进 pipeline；
- 放在 `assets/resource/image/30_daily/<TaskName>/` 下，文件名 ASCII；
- 优先裁「文字旁边独有的图形元素」，避免裁大块渐变背景；
- 半透明/异形按钮：生成绿幕图并在节点里开 `green_mask: true`。

## 3. 写节点（`assets/resource/pipeline/30_daily/<TaskName>.json`）

顺序建议：**界面判定 → 操作 → 操作后界面判定 → 分支**。

```jsonc
{
    "DailySignInEntry": {
        "next": ["DailySignInMain", "[JumpBack]CommonPopupAny", "[JumpBack]NavHome"],
    },
    "DailySignInMain": {
        "recognition": {"type": "OCR", "param": {"expected": ["签到"], "roi": [40, 600, 260, 100]}},
        "action": {"type": "Click"},
        "next": ["DailySignInClaim"],
    },
    "DailySignInClaim": {
        "recognition": {
            "type": "TemplateMatch",
            "param": {"template": "30_daily/SignIn/claim.png", "roi": [800, 480, 400, 200]},
        },
        "action": {"type": "Click"},
        "post_wait_freezes": {"time": 200, "target": [0, 0, 0, 0]},
        "next": ["DailySignInDone"],
    },
    "DailySignInDone": {
        "recognition": {
            "type": "Custom",
            "param": {
                "custom_recognition": "PanelState",
                "custom_recognition_param": {"panel": "signin", "claimed_node": "DailySignInClaimed"},
            },
        },
        "next": ["[JumpBack]NavHome"],
    },
}
```

要点：

- 每个动作后面都要有「能证明操作成功」的识别；
- 入口必须挂 `[JumpBack]` 兜底；
- 已领取状态优先用 `PanelState` 判定，别盲目点击；
- 不要用 `post_delay` 硬等动画。

## 4. 接 option（可选但推荐）

需要次数/开关/目标时：

1. 在 `tasks/options/global.json` 或 `tasks/daily/<TaskName>.json` 定义 `option`；
2. 用 `pipeline_override` 覆盖节点字段（`enabled`、`custom_action_param`、`target` 等）；
3. 不要为了一个开关复制整份节点。

## 5. 注册任务

`tasks/daily/<TaskName>.json`：

```jsonc
{
    "task": [
        {
            "name": "DailySignIn",
            "label": "每日签到",
            "entry": "DailySignInEntry",
            "description": "打开签到面板并领取每日奖励（已领取时自动跳过）。",
            "group": ["daily"],
        },
    ],
}
```

然后把该文件路径加入 `assets/interface.json` 的 `import` 数组。

## 6. 验证

```bash
npm run lint       # 命名/ROI/兜底/Custom ID
npm run schema     # JSON Schema
npm run check      # 框架语义（任务树、图片）
npm run test       # Agent 单测（如果改了 agent）
```

先用手上的截图做离线流程验证（无需设备）：

```bash
python tools/dev/dryrun.py --images docs/zh_cn/develop/screens/<Task> --entry <Task>Entry
```

有设备时再跑一遍真机：

```bash
uvx maafw-cli pipeline load assets/resource
uvx maafw-cli pipeline run DailySignInEntry
```

## 7. 录回放用例（防回归）

```bash
python tools/dev/record.py --case signin --entry DailySignInEntry
```

在 `tests/cases/signin.json` 写期望（入口、命中节点、步数上限），然后：

```bash
npm run replay
```

提交时带上：pipeline 文件 + 模板图 + tasks 片段 + 用例 + `game_facts.md` 更新。

## 自检清单

- [ ] 节点名/文件名 ASCII PascalCase，内部节点 `__` 前缀
- [ ] 所有 ROI 在 1280×720 内，模板来自 720p 截图
- [ ] 入口有 `[JumpBack]` 兜底，兜底节点有 `max_hit`
- [ ] 没有 >1000ms 的固定延迟
- [ ] 已领取/已完成状态可跳过（`PanelState` 或 `max_hit`）
- [ ] option 走 `pipeline_override`，没有复制节点
- [ ] `npm run verify` 全绿
- [ ] `docs/zh_cn/develop/game_facts.md` 已更新
