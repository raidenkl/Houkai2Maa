# 30_daily — 日常业务

一个玩法一个文件：`SignIn.json`、`FamiliarExplore.json`、`ResonanceRefresh.json`、
`FireRescue.json`、`WorldTravel.json`、`PowerBoost.json`、`ClubStamina.json`、`ActivityFarm.json`。

每个文件的最小契约：

1. `<Task>Entry` 入口节点，`next` 末尾挂
   `[JumpBack]CommonPopupAny`、`[JumpBack]NavHome`；
2. 「界面判定」节点与「操作」节点分开，操作后必须能识别到下一界面；
3. 「已领取/已完成」可跳过（`PanelState` 或 `max_hit`）；
4. 参数（次数/开关/目标）通过 `tasks/` 的 option 注入，不写死。

模板图放在 `assets/resource/image/30_daily/<Task>/`，尺寸按 720p 截图裁剪。
细节见 `.agents/skills/add-daily-task/SKILL.md`。

## OneClickDaily — 编排层

`OneClickDaily.json` 不含任何业务识别，只放一组 `OneClickDaily*Gate` 的「分流闸」，
把上面的单条链路串成一条流程。配合 `assets/tasks/oneclick/OneClickDaily.json` 使用。

机制：

- 每个 Gate 默认是 `DirectHit`（永远命中、不截图），**默认 `next` 指向下一个 Gate**，
  也就是「跳过这一步」；
- 每个业务步骤对应一个 `checkbox` case，勾选时把该 Gate 的 `next` 改成业务 `Entry`，
  同时把 Gate 的识别换成「主界面就绪」判据（左栏入口图标模板）——
  这样它会等上一步的页面切换完成再往下走，跳过的 Gate 仍然零开销；
- 各链路原本 `next` 为空的收尾节点（`LaunchGameReady`、`*Done`、`*Home`），
  在 **task 级 `pipeline_override`** 里接到下一个 Gate —— 这是串联的关键。
  单跑某条业务任务时不会加载这份 override，所以两边互不影响。

改这个编排层时必须注意三点：

1. **不是所有收尾节点都会回主界面**。多数 `*Done` / `*Home` 会点一次「首页」，
   但 `FamiliarExploreDone` 只做 `DoNothing`，所以中间插了
   `OneClickDailyHomeFromFamiliar` 补一次点击。新增链路时要先确认它的收尾节点行为。
2. **交接后不能立刻点下一步**。上一步刚点完「首页」时页面还在切，立刻点左栏图标会被丢掉
   （实测 `ResonanceRefreshEntry` 命中并点击了，日志 `success: true`，页面却不动，
   最后 20s `reco_timeout`）。所以勾选分支把 Gate 的识别换成「左栏入口图标」模板匹配 ——
   图标出现即代表主界面可交互。不要用固定延迟：`DirectHit` 不截图，
   `post_wait_freezes` 拿不到新帧，等于没等，`post_delay` 又只是赌时长。
3. **编排开头要先回主界面**（`OneClickDailyNavHome`）。子页面顶部也有「首页」文案，
   会让 `LaunchGameHub` 误判成「已在主界面」，而主界面就绪判据（左栏图标模板）
   在子页面并不命中，登录链会一路卡到 timeout。
