# 事故调试

v0.1 的调试围绕 `taskId` 展开。

## Debug Order

1. 确认用户上传的是 PNG。
2. 查询任务状态和 stage。
3. 查看后端 error log。
4. 检查原图是否保存。
5. 检查 OCR 是否输出。
6. 检查 AI 输出摘要。
7. 检查 DSL 文件是否存在。
8. 检查 DSL 校验结果。
9. 检查资产 URL 是否可访问。
10. 检查 Renderer warnings。

## Common Failures

上传失败：

- MIME 不合法。
- 文件过大。
- 图片无法读取。

识别失败：

- OCR 无输出。
- AI JSON 异常。
- DSL Builder 缺必填字段。

渲染失败：

- DSL version 不支持。
- assetId 不存在。
- 图片 URL 不可访问。
- root Frame 创建失败。

## Required Record

如果是 bug，必须创建 bug 记录并写明：

- 复现输入。
- 失败阶段。
- 根因。
- 修复。
- 回归保护。
