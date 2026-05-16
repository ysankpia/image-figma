# 可观测性

v0.1 只做能定位问题的日志，不做完整监控平台。

## Logs

后端任务日志至少包含：

- `taskId`
- `stage`
- `status`
- `errorCode`
- `message`
- `detail`
- `durationMs`
- `createdAt`

Renderer warning 至少包含：

- `elementId`
- `type`
- `code`
- `message`

M8 primitive result 至少包含：

- `taskId`
- `provider`
- `model`
- `status`
- `primitiveCount`
- `relationCount`
- `errorCode`
- `primitivePath`

M10 OCR/patch result 至少包含：

- `taskId`
- `provider` 或 `mode`
- `status`
- `blockCount`
- `patchCount`
- `warningCount`
- `errorCode`
- `ocrPath`
- `patchPath`

百度 PP-OCRv5 provider 的 OCR JSON `meta` 还应包含远端 `jobId`、提交耗时、轮询耗时、轮询次数和低置信度过滤数量，方便定位远端耗时和质量问题。

M12 text replacement result 至少包含：

- `taskId`
- `mode`
- `status`
- `acceptedCount`
- `rejectedCount`
- `warningCount`
- `errorCode`
- `replacementPath`

## Metrics

开发阶段优先从日志中观察：

- 上传耗时。
- OCR 耗时。
- AI 调用耗时。
- primitive extraction 成功/失败数量。
- DSL patch build 成功/失败数量。
- text replacement accepted/rejected 数量。
- DSL 生成耗时。
- 资产裁切耗时。
- Renderer 渲染耗时。
- 成功/失败数量。

不接入复杂 metrics 平台。

## Traces

v0.1 不做分布式 trace。

任务内用 `taskId` 串起：

```text
upload -> preprocess -> asset_crop -> primitive_extract -> ocr_extract -> dsl_patch_build -> text_replacement -> dsl_validate
```

插件渲染阶段用 `taskId` 和 DSL `version` 关联。

## Debug Artifacts

建议保留：

- 原始 PNG。
- 预处理结果。
- OCR 摘要。
- AI 输出摘要。
- visual primitive JSON。
- OCR JSON。
- DSL patch JSON。
- text replacement JSON。
- DSL 文件。
- 资产 metadata。
- Renderer warning。

不默认保存完整模型输入输出，避免隐私和成本问题。
