# 00_launch — 启动与登录

放「从设备桌面到进入游戏主界面」的节点：

- 启动游戏（`Shell` + `monkey`，`StartApp` 只填 package 在 ADB 控制器上不可用，见 game_facts §12）
- 热更新/下载包/版本公告
- 登录界面检测（**命中即 `StopTask`**，禁止自动输入账号密码）——**尚未实现**，登录界面未采集
- 首充/活动弹窗（与 `10_common` 的弹窗兜底配合）

约定：

- 入口节点命名 `Launch*`；
- 只做「能进到主界面」的最少步骤，业务逻辑不要写在这里；
- 包名等可变参数通过 `preset`/`option` 注入，不写死。

## 现有节点

`LaunchGame.json`（2026-10-19 真机跑通）：

| 节点                    | 作用                                                                  |
| ----------------------- | --------------------------------------------------------------------- |
| `LaunchGameEntry`       | `DirectHit` 入口，分流「标题画面 / 已在游戏内 / 需要启动」            |
| `LaunchGameStart`       | `Shell` + `monkey` 拉起官服客户端（`max_hit 1`）                      |
| `LaunchGameTitle`       | 标题画面点「抚摸屏幕继续」，`timeout 180s` 覆盖更新检查与文案淡入     |
| `LaunchGameHub`         | 分流中枢：就绪判定 + 关活动广告 + 关公告板 + 签到的 `[JumpBack]` 调用 |
| `LaunchGameCloseAd`     | 模板匹配活动弹窗右上的蓝色 ×（位置随弹窗浮动，不能用固定坐标）        |
| `LaunchGameCloseNotice` | 公告板右上大 ×（`(1169,78)`）                                         |
| `LaunchGameReady`       | 就绪判定：左栏第 1 个图标模板（弹窗下必 miss），`threshold 0.8`       |

签到两个弹窗的节点在 `30_daily/SignIn.json`（`DailySignInClaim` / `DailySignInEvent`），
由 `LaunchGameHub` 用 `[JumpBack]` 调用，执行完自动回到分流。

## 入口为什么是 `DirectHit`

入口节点的识别必须命中，否则任务在入口就失败、`next` 不会执行。桌面（launcher）上没有任何
游戏文案，所以入口用 `DirectHit`，把「当前在哪」的判断交给 `next` 的候选列表。
