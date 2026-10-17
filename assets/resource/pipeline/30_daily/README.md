# 30_daily — 日常业务

一个玩法一个文件：`SignIn.json`、`Mail.json`、`ClubWelfare.json`、`Farm.json`。

每个文件的最小契约：

1. `<Task>Entry` 入口节点，`next` 末尾挂
   `[JumpBack]CommonPopupAny`、`[JumpBack]NavHome`；
2. 「界面判定」节点与「操作」节点分开，操作后必须能识别到下一界面；
3. 「已领取/已完成」可跳过（`PanelState` 或 `max_hit`）；
4. 参数（次数/开关/目标）通过 `tasks/` 的 option 注入，不写死。

模板图放在 `assets/resource/image/30_daily/<Task>/`，尺寸按 720p 截图裁剪。
细节见 `.agents/skills/add-daily-task/SKILL.md`。
