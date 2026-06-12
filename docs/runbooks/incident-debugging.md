# 事故调试

当前默认调试对象是 Slice Studio。先确认保存状态和导出合同，不要先猜旧 Draft、Renderer 或插件问题。

## Slice Studio Debug Order

1. 确认用户上传的是受支持图片，且没有超过 `SLICE_STUDIO_MAX_UPLOAD_BYTES` 或 batch 上限。
2. 打开 `/projects`，确认项目、页面、缩略图可读。
3. 检查 `storage/app.sqlite` 是否存在。
4. 检查 `storage/projects/{projectId}/originals/` 是否有源图。
5. 检查页面和 slices 是否能通过 API 读回。
6. 如果是 AI 画框问题，检查 `/ai-boxes` response diagnostics、provider 配置、tile/overview 解析和前端 merge/save。
7. 如果是保存问题，检查 `PUT /api/projects/:projectId/slices` 和 SQLite state。
8. 如果是 crop/cutout 问题，检查 `shape-cutout.ts`、`exporter.ts`、源图 bbox 和 cut mode。
9. 如果是 `assets.zip` 问题，检查 manifest、slice 文件、originals 和 package-local 路径。
10. 如果是 `project.zip/design.pen` 问题，检查 `pencil-exporter.ts`、`pencil-package.ts`、visible refs、remainder、slice placement。
11. 如果是 OCR/M29 text 问题，检查 OCR provider result、text quality gate、`m29-physical-evidence`、`m29-text-locator.ts` 和 manifest metadata。

## Common Slice Studio Failures

上传失败：

- 文件过大。
- 图片解码失败。
- batch 总大小超过限制。
- local storage 不可写。

AI 画框失败：

- `SLICE_STUDIO_AI_SLICE_API_KEY` 缺失。
- provider TLS / timeout / 5xx。
- 模型返回非 JSON 或 bbox 越界。
- tile/overview merge 后被过滤。
- 前端没有把返回 boxes 保存成 SliceRecord。

OCR / M29 失败：

- `BAIDU_PADDLE_OCR_TOKEN` 缺失或 provider 超时。
- OCR 输出低置信度或过宽，被 text quality gate 跳过。
- M29 physical evidence 生成失败。
- Go fallback 路径不存在但被显式配置为 `go_m29extract`。

导出失败：

- 项目没有 slices。
- 源图缺失。
- bbox 越界或尺寸非法。
- visible refs 不是 package-local。
- `.pen` package 缺 required assets。

## Owning Layer

按归属层修：

```text
project/page/slice persistence -> server/projects.ts or server/db.ts
source image access -> page source route or storage path
AI bbox -> ai-slice-boxes provider/tiling/parsing/filtering/merge/prompt
save/undo/merge -> Review Workbench state and shared/ai-slices.ts
crop/cutout -> shape-cutout.ts or exporter.ts
assets.zip -> exporter.ts
project.zip/design.pen -> pencil-exporter.ts or pencil-package.ts
OCR text -> text-ocr.ts and text quality gate
physical text bbox -> m29-physical-evidence or m29-text-locator.ts
historical Draft -> archive/legacy-code/services/backend-go only when explicitly targeted
```

不要用样例名、固定坐标、固定文案、固定页面数量去修。

## Historical Draft Debugging

如果任务明确针对 Go Draft，再使用旧顺序：

```text
/api/draft-preview/{taskId}
task artifact directory
source.png
ocr.json
m29_physical_evidence.v1.json
vision artifacts
editable_layer_graph.v1.json
draft_validation_report.md
draft_runtime.dsl.v1.json
asset_manifest.json
Renderer/plugin warnings
```

## Required Bug Record

如果是 bug，必须创建或更新 bug 记录并写明：

- 复现输入；
- 失败项目或 task；
- 失败阶段；
- 根因归属层；
- 修复；
- 回归保护；
- 验证命令和真实 artifact 证据。
