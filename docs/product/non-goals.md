# 当前不做事项

本文档是当前 Slice Studio 主线边界。没有新的 active plan 前，不要把这些功能塞回默认路径。

## Product Non-Goals

当前不做：

- 账号系统。
- 团队协作。
- 云同步。
- 额度、计费、支付。
- 正式 SaaS 多租户。
- 长期在线任务队列。
- 质量评分看板。
- 复杂用户教程平台。

## Design / Figma Non-Goals

当前不做：

- 真正 Figma Component。
- Figma Instance。
- Auto Layout 自动推断。
- Responsive Layout。
- Hug Content / Fill Container 推断。
- 完整设计系统还原。
- 前端代码生成。
- 官方 Codia JSON byte-for-byte clone。
- 自动 semantic UI control tree 作为产品合同。

原因：输入是截图/设计稿图片，系统无法可靠知道真实布局意图。当前可交付目标是用户确认后的切图和 Pencil/Figma handoff，不是全自动设计系统重建。

## Recognition / AI Non-Goals

当前不做：

- 让 AI 直接生成最终 Figma tree。
- 让 M29/OCR/YOLO/VLM 直接决定 visible ownership。
- 将 AI boxes 作为单独持久 proposal 系统。
- 给 AI 输入 M29/OCR evidence 做二次复杂判断。
- 自动判断 `rect | subject | card`。
- 用样本名、固定坐标、品牌、可见文案写规则。

AI 只是批量画框工具。多切可删，漏切更贵；最终仍由用户确认的 saved slices 决定。

## Legacy Non-Goals

当前不恢复：

- Go Draft 作为默认 delivery route。
- Python `/api/upload-preview` 作为默认 route。
- `services/pencil-python-backend` 作为默认主线。
- `services/pencil-go` revival。
- Figma plugin runtime revival。
- Codia assembly/control/tree/emitter 作为产品生成路径。
- M29 Direct Replay 作为默认交付。

旧代码保留为 reference/research/fallback。恢复前必须先写新的 active plan、truth source 和验证门。
