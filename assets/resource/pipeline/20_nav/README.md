# 20_nav — 场景导航

| 节点          | 作用                                                             |
| ------------- | ---------------------------------------------------------------- |
| `NavHomeFlag` | 判定「当前在主界面」                                             |
| `NavHome`     | 从任意界面回到主界面（关闭弹窗 → 连点返回 → 校验 `NavHomeFlag`） |
| `NavEnterXxx` | 主界面 → 某功能入口                                              |

约定：

- 用 `anchor: "Scene"` 记录「最后到达的界面」，供 `[Anchor]Scene` 回退；
- `NavHome` 必须自身闭环：从任何界面调用都能回到主界面；
- 入口节点的 `next` 末尾挂 `[JumpBack]CommonPopupAny`。
