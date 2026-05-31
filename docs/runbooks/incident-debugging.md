# 事故调试

当前 Draft runtime 的调试围绕 `taskId` 和 task artifact 展开。不要先猜 Renderer 或插件问题；先确认 backend 合同是否有效。

## Debug Order

1. 确认用户上传的是 PNG。
2. 查询 `/api/draft-preview/{taskId}`，记录 `status`、`stage`、`errorCode` 和 `message`。
3. 查看 task artifact 目录。
4. 检查 `source.png` 是否存在且可读。
5. 检查 OCR 输出。
6. 检查 M29 physical evidence。
7. 检查可选 vision artifacts。如果 vision 失败，确认是否有 fallback artifact，且 task 是否按预期继续。
8. 检查 `draft/editable_layer_graph.v1.json`。
9. 检查 `draft/draft_validation_report.md`。
10. 检查 `draft/draft_runtime.dsl.v1.json`。
11. 检查 `assets/asset_manifest.json` 和 referenced PNG 是否存在。
12. 检查 Renderer/plugin warnings。

## Common Failures

上传失败：

- MIME 不合法。
- 文件过大。
- PNG signature 或 IHDR 无法读取。

OCR / M29 失败：

- OCR provider token 缺失或 provider 超时。
- OCR 输出为空但当前样图需要文字证据。
- M29 physical evidence 生成失败。

Vision 失败：

- `VISION_API_KEY` 缺失。
- provider TLS / timeout / 5xx。
- 模型返回非 JSON 或 bbox 越界。

默认情况下，vision failure 不应失败整个 Draft task。它应写入 fallback artifact，并继续走 OCR/M29 Draft fallback，除非请求显式要求 vision。

Draft 失败：

- `editable_layer_graph.v1.json` 未生成。
- TextLayer 被同区域 RasterLayer/ShapeLayer 覆盖。
- visible full-page backing 被 emit。
- RasterLayer asset ref 无法解析。
- ShapeLayer 携带前景文字像素。
- Draft Runtime DSL 缺必填字段或 child order 错误。

渲染失败：

- DSL version 不支持。
- assetId 不存在。
- 图片 URL 不可访问。
- Figma image creation 失败。
- root Frame 创建失败。

## Owning Layer

按归属层修：

```text
source image/OCR -> OCR adapter or source normalization
physical bbox/crop -> M29 or image package
semantic label/missing candidate -> vision detector/review
emit/consume/suppress -> draft/assemble
asset reference -> draft/asset or app/server
DSL shape/order -> draft/exportdsl
render warning -> renderer after confirming DSL is valid
plugin flow -> plugin route/wiring
```

不要在 Renderer 或 Plugin 里掩盖 backend ownership bug。

## Required Bug Record

如果是 bug，必须创建或更新 bug 记录并写明：

- 复现输入。
- 失败 taskId 和 artifact 路径。
- 失败阶段。
- 根因归属层。
- 修复。
- 回归保护。
- 验证命令和真实 artifact 证据。
