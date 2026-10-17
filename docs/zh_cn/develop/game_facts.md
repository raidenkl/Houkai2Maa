# 游戏事实表（game_facts）

> 本文件记录**实测**的游戏界面事实。所有坐标以 **1280×720（16:9）** 为基准。
> 未实测的项保持「待补」，禁止凭猜测填写。

## 采集方法

```bash
uvx maafw-cli connect adb 127.0.0.1:16384
uvx maafw-cli --json ocr                 # 文案 + 坐标 + 自动截图
uvx maafw-cli screenshot -o debug/probe/<场景>.png
```

截图后确认尺寸为 1280×720（`python -c "from PIL import Image; print(Image.open('x.png').size)"`）。

报坐标时建议让工具生成网格图，直接读刻度：

```bash
python tools/dev/snapshot.py --image shots/home.png --grid
# 输出 xxx-grid.png：100px 一格，交点标注 "x,y"
```

## 1. 基础信息

| 项                | 官服 | B 服 | 备注                                                          |
| ----------------- | ---- | ---- | ------------------------------------------------------------- |
| 包名              | 待补 | 待补 | `adb shell pm list packages \| grep -i houkai`                |
| 启动方式          | 待补 | 待补 | `StartApp` 能否直接拉起；否则用 `Shell` + `monkey -p <pkg> 1` |
| 是否需要热更新    | 待补 | —    | 更新进度界面形态                                              |
| 账号登录界面      | 待补 | 待补 | 出现即停止任务，禁止自动输入                                  |
| 分辨率/宽高比要求 | 16:9 | 16:9 | 非 16:9 设备需调整模拟器                                      |

## 2. 主界面（Home）

| 元素          | 类型 | 坐标/ROI | 文案 | 截图            |
| ------------- | ---- | -------- | ---- | --------------- |
| 主界面标志    | 待补 | —        | —    | `main-home.png` |
| 签到入口      | 待补 | —        | 待补 | —               |
| 邮件入口      | 待补 | —        | 待补 | —               |
| 社团入口      | 待补 | —        | 待补 | —               |
| 出击/关卡入口 | 待补 | —        | 待补 | —               |

## 3. 公告/弹窗

| 弹窗         | 识别特征 | 关闭方式 | 出现时机        |
| ------------ | -------- | -------- | --------------- |
| 每日签到弹窗 | 待补     | 待补     | 登录后          |
| 活动公告     | 待补     | 待补     | 登录后/活动更新 |
| 网络错误     | 待补     | 重试     | 随机            |
| 版本更新提示 | 待补     | 待补     | 版本更新后      |

## 4. 领奖

| 面板     | 未领取特征 | 已领取特征 | 一键领取按钮 | 备注 |
| -------- | ---------- | ---------- | ------------ | ---- |
| 签到     | 待补       | 待补       | 待补         | —    |
| 邮件     | 待补       | 待补       | 待补         | —    |
| 社团福利 | 待补       | 待补       | 待补         | —    |

## 5. 刷本

| 界面           | 识别特征       | 操作           | 备注                                |
| -------------- | -------------- | -------------- | ----------------------------------- |
| 关卡列表       | 待补           | 选择目标关卡   | —                                   |
| 备战页         | 待补           | 点击开战       | 原阵营战脚本的「备用装备/助战」逻辑 |
| 战斗中         | 无（不做操作） | 等待           | —                                   |
| 结算页         | 待补           | 再次挑战/返回  | 用于替代固定 30s 等待               |
| 体力不足弹窗   | 待补           | 补给/购买/停止 | 由 option 决定                      |
| 双倍体力券弹窗 | 待补           | 使用/取消      | 由 option 决定                      |

## 6. 已知版本差异

| 版本 | 变化 | 影响节点 |
| ---- | ---- | -------- |
| 待补 | —    | —        |

## 7. PC 端（Win32）实测步骤

> 目前 `interface.json` 的「桌面端」控制器是**实验性**配置，窗口类名/标题与截图方式都未验证。
> 按下面步骤实测后，把结果填回本节并决定是否转正（Phase 5）。

1. **找到窗口**：启动 PC 客户端后列出窗口，确认类名与标题正则：

    ```bash
    uvx maafw-cli device win32
    ```

2. **确定截图方式**：依次尝试 MFAAvalonia 控制器里的 `screencap`：
   `ScreenDC`（最兼容，前台）→ `PrintWindow`（后台）→ `BitBlt`。
   观察窗口被遮挡/最小化时是否还能截图。

3. **确定输入方式**：`Seize`（最直接）→ `PostMessageWithCursorPos` → `PostMessage`。
   记录哪种能真正点到按钮，以及是否需要管理员权限。

4. **确认分辨率**：Win32 截图尺寸 = 窗口客户区尺寸。需要把窗口调整到
   1280×720（或确认客户端是否自带缩放）；若 `display_short_side` 对 Win32 无效，
   则模板必须在**客户端实际窗口尺寸**下裁剪，并在本节记录。

5. **填回配置**：`assets/interface.json` 的 `controller[桌面端].win32`：

    ```jsonc
    {
        "class_regex": "<实测类名>",
        "window_regex": "<实测标题>",
        "screencap": "<可用方式>",
        "mouse": "<可用方式>",
        "keyboard": "<可用方式>",
    }
    ```

6. **验收**：用 `probe.py`（指向 PC 截图资源）确认关键模板命中分数 ≥0.9，
   再跑一条只读任务（如导航/领奖）。

## 8. 阵营战 720p 模板重拍步骤

现有 `assets/resource/image/双倍.png`（47×48）与 `双倍体力兑换.png`（300×79）是在
1080p 基准下裁的。按 720p 重拍后即可删除 `tools/lint/allowlist.json` 中的 E203 豁免前置条件。

1. 进入 bonus 关卡备战页，截图（`display_short_side=720`）：

    ```bash
    python tools/dev/snapshot.py
    ```

2. 用网格图定位两个按钮，重新裁剪（覆盖原文件）：

    ```bash
    python tools/dev/crop.py --screen debug/probe/<ts>-screen.png \
        --box <x>,<y>,<w>,<h> --out 双倍.png --node FactionWarDouble --pad 20 --dry-run  # 先看 ROI
    python tools/dev/crop.py --screen debug/probe/<ts>-screen.png \
        --box <x>,<y>,<w>,<h> --out 双倍体力兑换.png --node FactionWarExchangeDouble --pad 20
    ```

3. 验证命中：

    ```bash
    python tools/dev/probe.py --node FactionWarEntry --image debug/probe/<ts>-screen.png
    python tools/dev/probe.py --node FactionWarExchangeDouble --image debug/probe/<ts>-screen.png
    ```

4. 用同一张截图生成节点回归用例，后续每次改动都会验证：

    ```bash
    npm run nodecase -- --node FactionWarEntry --node FactionWarExchangeDouble --images debug/probe
    ```

5. 最后真机跑一遍：`uvx maafw-cli pipeline run FactionWarEntry`（前置：手动进入备战页），
   并 `python tools/dev/record.py --case faction-war --entry FactionWarEntry` 存档。
