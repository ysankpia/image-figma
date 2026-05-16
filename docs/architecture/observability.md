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

## Metrics

开发阶段优先从日志中观察：

- 上传耗时。
- OCR 耗时。
- AI 调用耗时。
- primitive extraction 成功/失败数量。
- DSL 生成耗时。
- 资产裁切耗时。
- Renderer 渲染耗时。
- 成功/失败数量。

不接入复杂 metrics 平台。

## Traces

v0.1 不做分布式 trace。

任务内用 `taskId` 串起：

```text
upload -> preprocess -> asset_crop -> primitive_extract -> dsl_build -> dsl_validate
```

插件渲染阶段用 `taskId` 和 DSL `version` 关联。

## Debug Artifacts

建议保留：

- 原始 PNG。
- 预处理结果。
- OCR 摘要。
- AI 输出摘要。
- visual primitive JSON。
- DSL 文件。
- 资产 metadata。
- Renderer warning。

不默认保存完整模型输入输出，避免隐私和成本问题。
