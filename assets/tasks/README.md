# tasks — interface 片段（PI v2 `import`）

本目录存放任务的 ProjectInterface 片段，一个任务（或一组相关的任务+选项）一个文件，
由 `assets/interface.json` 的 `import` 数组引入。

> PI 的 `import` 路径**相对 `interface.json` 所在目录**解析，所以片段放在 `assets/tasks/`，
> 而 `interface.json` 里写 `"tasks/activity/FactionWar.json"`；打包时 `install.py` 会把它
> 复制成 `install/tasks/`。合并规则见
> [MaaFramework 文档](https://github.com/MaaXYZ/MaaFramework/blob/main/docs/zh_cn/3.3-ProjectInterfaceV2协议.md)
> （`task` 追加、`option` 同名覆盖、`global_option` 去重追加）。

规划中的结构：

```tree
tasks/
├── options/global.json        # 跨任务选项（刷本次数、体力策略、包名）
├── daily/DailyFull.json       # 日常全套编排
├── daily/SignIn.json          # 每日签到
├── daily/Mail.json            # 邮件领取
├── daily/ClubWelfare.json     # 社团福利
├── daily/FarmStage.json       # 体力刷本
└── activity/FactionWar.json   # 阵营战（活动）
```

约定：

- `entry` 必须指向已存在的 pipeline 节点（lint 规则 E206）；
- 入口节点不能是 `__` 内部节点（E209）；
- 每个任务声明 `group`（`daily` / `activity` / `tools`）与中文 `label`；
- 参数一律放在 `option` + `pipeline_override`，不要复制节点。

**当前尚未启用**：日常节点还没落地（等待游戏事实），所以 `interface.json` 里
还没有 `import`；新增任务时按 `.agents/skills/add-daily-task/SKILL.md` 的步骤接上。
