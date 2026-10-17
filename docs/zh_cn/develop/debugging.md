# 排障手册

出问题时按这个顺序看，90% 的情况前两步就能定位。

## 1. 日志与现场在哪

| 路径                | 内容                                          | 何时产生     |
| ------------------- | --------------------------------------------- | ------------ |
| `debug/maa.log`     | MaaFramework 框架日志（节点识别、动作、超时） | 每次运行     |
| `debug/on_error/`   | 失败时的自动截图                              | 任务失败     |
| `debug/shots/`      | `SaveShot` 自定义动作主动落盘的截图           | 命中该节点   |
| `debug/agent.log`   | Agent 自身日志（Custom 入参、判定结果）       | Agent 启动后 |
| `debug/probe/`      | `snapshot.py` 采集的截图 / OCR 标注 / JSON    | 手动采集     |
| `debug/screenshot/` | VSCode `maa-support` 插件的截图               | 插件截图命令 |

看框架日志推荐用 [MaaLogAnalyzer](https://mla.maafw.com/)（VSCode 插件或网页版），
它会把节点执行流画出来，比 grep 快得多。

## 2. 先判断「卡在哪一层」

| 现象                 | 可能原因                                  | 下一步                                                         |
| -------------------- | ----------------------------------------- | -------------------------------------------------------------- |
| 任务一开始就失败     | 资源没加载（缺 OCR 模型）、入口节点不存在 | `npm run check`；确认 `assets/resource/model/ocr/` 有 3 个文件 |
| 卡在某个界面反复识别 | `next` 没覆盖当前画面                     | 用 `snapshot.py` 截图 + OCR，确认界面文案/图标                 |
| 一直点同一个按钮     | 点击后没有识别新界面，`next` 又命中自己   | 加中间识别节点；给该节点 `max_hit`                             |
| 误点到别的界面       | ROI 太大 / 模板太宽泛                     | 缩小 ROI、裁更独特的局部；用 `tests/node-cases` 做离线验证     |
| 识别分数不上不下     | 模板不是 720p 裁的，或游戏画质不同        | 重新用 `crop.py` 从 720p 截图裁模板                            |
| Custom 动作没生效    | ID 拼写不一致                             | `npm run lint` 会报 E204（未注册 ID）                          |
| Agent 起不来         | 用户环境没装 `maafw`                      | `python -m pip install -r assets/agent/requirements.txt`       |
| 循环不结束           | 计数逻辑或 `max_hit` 缺失                 | 看 `debug/agent.log` 里的 FarmLoop 日志                        |

## 预任务失败（DevicePrepare）

预任务在 Controller 启动前执行，失败会中止启动。典型输出与处理：

| 输出                          | 原因                             | 处理                                                     |
| ----------------------------- | -------------------------------- | -------------------------------------------------------- |
| `未找到 ADB 设备`             | 模拟器没启动 / adb 看不到        | 启动模拟器；`adb devices` 确认连接                       |
| `截图是 1600x720（…非 16:9）` | 手机是 20:9，短边缩放后不是 16:9 | 模拟器设为 1280×720，或用 `adb shell wm size 1280x720`   |
| `截图是 1920x1080`            | 分辨率不是 720p                  | 改为 1280×720（识别更快、字更清晰）                      |
| `截图是竖屏`                  | 游戏未横屏                       | 转横屏后再启动                                           |
| `缺少 maafw`                  | 用户环境没装 Python 依赖         | `python -m pip install -r assets/agent/requirements.txt` |

离线校验某张截图：`python assets/agent/pretask/device_prepare.py --image shot.png`。

## 3. 离线复现（推荐先做）

```bash
# 单张截图，看 OCR 文案与坐标
python tools/dev/snapshot.py --image shots/xxx.png --json

# 一组截图，跑流程结构
python tools/dev/dryrun.py --images shots/xxx --entry <Entry> --json

# 识别参数回归
npm run test:node

# 录制回放（有设备时录制，之后离线回放）
python tools/dev/record.py --case <case> --entry <Entry>
npm run replay
```

## 4. 真机复现

```bash
uvx maafw-cli connect adb 127.0.0.1:16384
uvx maafw-cli --json ocr
uvx maafw-cli --json reco TemplateMatch template=双倍.png threshold=0.85
uvx maafw-cli pipeline run <Entry>          # 跑一条 pipeline
uvx maafw-cli action custom SaveShot --raw '{"tag":"probe"}'
```

## 5. 提交 issue 时请附上

1. `debug/maa.log`（最近一次运行的，不要截断）；
2. `debug/on_error/` 里的截图；
3. 设备信息：模拟器/机型、分辨率、是否 16:9；
4. 使用的任务名与选项；
5. 复现步骤（从哪个界面开始）。

## 6. 常见误判

- **「改了节点没生效」**：pipeline 文件在 `assets/resource/pipeline/` 下，
  但 Client 可能加载的是 `install/` 里的旧副本 —— 重新安装或直接指向资源目录。
- **「OCR 完全不工作」**：`assets/resource/model/ocr/` 缺 `det.onnx`/`rec.onnx`/`keys.txt`。
- **「模板明明一样却匹配不到」**：分辨率不是 720p，或游戏内 UI 缩放/画质设置不同。
- **「CI 挂了但本地没问题」**：本地可能有 `debug/` 产物或未提交的图片；
  CI 只认仓库内容，跑 `git status` 确认。
