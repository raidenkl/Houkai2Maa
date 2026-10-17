# 发布流程（v2.0.0 及以后）

本文是发布清单。目标是「一次发版只做机械操作，不做技术决策」。

## 0. 前置条件

| 项       | 要求                                      | 检查方式                                             |
| -------- | ----------------------------------------- | ---------------------------------------------------- |
| CI 全绿  | check 工作流所有步骤通过                  | GitHub Actions 页面                                  |
| 发布自检 | 版本号/路径/工作区干净                    | `npm run release:check -- --tag vX.Y.Z --strict-git` |
| 真机回归 | `DailyFull` 连续 20 次 ≥95%（Phase 5）    | `debug/` 里的日志与截图                              |
| 文档同步 | `phase_status.md`、`game_facts.md` 为最新 | 人工                                                 |

## 1. 版本号

GIthub tag 形如 `v2.0.0`；`assets/interface.json` 的 `version` 写同一版本号
（可带 `v` 也可不带，CI 写入安装包时用 tag 原文）。预发布用
`2.0.0-beta.1` / `2.0.0-rc.1` 这类后缀，CI 会把它们标成 prerelease。

```bash
# 1) 改版本
#    assets/interface.json -> "version": "2.0.0"
# 2) 自检
npm run release:check -- --tag v2.0.0 --strict-git
# 3) 提交
git add -A && git commit -m "release: v2.0.0"
```

## 2. 打 tag 触发 CI

```bash
git tag v2.0.0
git push origin HEAD --tags
```

CI（`.github/workflows/install.yml`）会：

1. 下载 MaaFramework（`MAAFW_VERSION` 为空 = latest）与 MFAAvalonia（`MaaXYZ/MFAAvalonia`）；
2. 对 `win/macos/linux/android × aarch64/x86_64` 八个组合执行 `tools/install.py`；
3. `install.py` 复制 `resource/`、`interface.json`、`agent/`、`tasks/`，并做安装自检
   （import / pretask / agent 路径必须可解析）；
4. 用 git-cliff 生成更新日志，创建 Release 并上传 zip。

> 第一次发布前需确认仓库设置：`Settings → Actions → General → Workflow permissions`
> 选择 **Read and write permissions**，否则 release job 无法创建 Release。

## 3. 发布后验证（10 分钟）

1. 下载 **win-x86_64** 包解压，确认目录里有：
   `interface.json`、`resource/pipeline/**`、`resource/model/ocr/{det,rec}.onnx,keys.txt`、
   `agent/main.py`、`tasks/activity/FactionWar.json`；
2. 用 MFAAvalonia 打开 `interface.json`，能看到「活动」分组与 `FactionWar` 任务、
   选项「使用双倍体力券」；
3. 启动前预任务会检查分辨率（非 1280×720 会给出提示）；
4. 跑一次 `FactionWar`（前置：手动进入 bonus 备战页），确认无回归；
5. 下载 **android-aarch64** 包，确认 `MaaAgentBinary/` 与 `resource/` 结构一致。

## 4. 回滚

```bash
# 删除错误 tag（本地 + 远端）与 Release，修好后重新打 tag
git tag -d v2.0.0
git push origin :refs/tags/v2.0.0
```

## 5. Mirror酱（可选，默认关闭）

开启前需要：

1. 在 [Mirror酱](https://mirrorchyan.com/) 申请项目，拿到 `rid`；
2. `assets/interface.json` 填 `"mirrorchyan_rid": "<rid>"`（需要多平台包时加
   `"mirrorchyan_multiplatform": true`）；
3. 两个 workflow 里把 `if: false` 改成实际条件，并把 `mirrorchyan_rid` /
   `owner` / `filename` 前缀与本项目对齐（当前已改为 `MaaHoukai2` / `raidenkl`）；
4. 在仓库 Secrets 配置 Mirror酱 所需的 token。

未开通前**不要**直接打开开关：仓库里的 workflow 只是模板，直接开启不会生效。

## 6. 发版检查清单（复制到 Release note 或 PR）

- [ ] `npm run verify` 全绿
- [ ] `npm run release:check -- --tag vX.Y.Z --strict-git` 通过
- [ ] `phase_status.md` 反映本次支持的玩法与已知限制
- [ ] 真机回归记录（次数/成功率）已写入 PR 或 Release note
- [ ] 安装包抽检（Win + Android 各一次）
- [ ] 旧版本 tag 保留（便于回滚）
