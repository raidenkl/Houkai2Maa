# 10_common — 通用按钮与弹窗

被所有业务层 `[JumpBack]` 引用的「可复用兜底」：

| 节点               | 作用                               |
| ------------------ | ---------------------------------- |
| `CommonConfirm`    | 确认/确定                          |
| `CommonCancel`     | 取消                               |
| `CommonClose`      | 右上角关闭                         |
| `CommonBack`       | 返回                               |
| `CommonLoading`    | 加载中（配合 `inverse` 等待）      |
| `CommonPopupAny`   | 通用弹窗集合（公告/提示/网络错误） |
| `CommonPopupRetry` | 网络错误重试（`max_hit` 限制）     |

要求：

- 全部设置 `max_hit`，避免死循环；
- 只用「与本项目业务无关」的通用识别；
- 不允许引用 `30_daily/`、`90_activity/` 的节点。
