# 用例说明（node-cases）

本目录给 `@nekosu/maa-tools test` 使用：给一张截图，断言「哪些节点应当命中」，
**不需要设备**，适合在改阈值 / 改 ROI / 换模板后做回归。

## 文件格式

```jsonc
{
    "configs": {
        "name": "main-home", // 用例组名
        "resource": "官服", // 与 interface.json 的 resource.name 对应
        "controller": "安卓端", // 与 interface.json 的 controller.name 对应
        "imageRoot": "screens", // 截图相对本文件的目录
    },
    "cases": [
        {
            "image": "home-1280x720.png", // 720p 截图
            "hits": ["NavHomeFlag"], // 期望命中的节点，可写 {"node": "X", "box": [..]}
        },
    ],
}
```

## 使用方式

```bash
npm run test:node
```

也可以由截图自动生成（推荐，避免手写节点名出错）：

```bash
npm run nodecase -- --node NavHomeFlag --node DailySignInButton --images shots/home
# 产物：tests/node-cases/generated.json + tests/node-cases/screens/*.png
```

缺少截图时工具会打印 `not exists, ignored` 并跳过该用例。

## 截图要求

- 必须是 **1280×720**（16:9），与 `display_short_side: 720` 一致；
- 文件名带场景说明，例如 `farm-result.png`、`popup-stamina.png`；
- 一张截图尽量只放一个用例，便于失败定位。
