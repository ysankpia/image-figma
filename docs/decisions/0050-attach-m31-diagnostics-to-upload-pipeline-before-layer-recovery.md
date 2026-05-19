# ADR: Attach M31 Diagnostics To Upload Pipeline Before Layer Recovery

- 状态：accepted
- 日期：2026-05-20

## Context

M31.0 已经证明可以从 source PNG、OCR JSON 和 M29 `nodes.json` 生成 reconstruction UI tree、unit fallback crops 和结构质量 report。

但 M31.0 只是 script-only diagnostic。它还没有跑在真实插件上传样本上，因此无法回答最关键的问题：

```text
M29 primitive evidence
在真实用户上传图上是否能稳定组织成 reconstruction units
```

如果直接进入 M32 layer recovery，就会重复之前 M29.0.x 的错误：在没有稳定 ownership/fallback tree 的情况下继续堆局部规则。

## Decision

把 M31 作为诊断旁路接入 `/api/upload-m30-preview`，但不改变可见输出：

```text
OCR + M29 nodes.json
-> M31 reconstruction diagnostics
-> M29.0.x + M30 DSL
```

新增：

```text
M31_UPLOAD_DIAGNOSTICS_ENABLED=true
M31_UPLOAD_DIAGNOSTICS_STRICT=false
GET /api/tasks/{taskId}/m31-reconstruction
```

默认行为：

- 每次 M30 preview 上传都生成 M31 tree/report。
- M31 失败默认不阻断 M30 DSL 和 Figma 渲染。
- strict 模式用于开发验收，M31 失败会让 task failed。
- M31 只消费 source PNG、OCR document/JSON、M29 document/`nodes.json`。
- M31 report 只用于质量观测，不进入 DSL children。

## Consequences

好处：

- 真实上传样本会自动留下 M31 ownership/fallback quality evidence。
- 后续是否进入 M32 可以基于 `primitiveOwnershipRate`、`unitFallbackCoverage`、`reviewBucketCount`、`rootLeafPrimitiveCount` 判断。
- M31 作为组织层接受真实压力测试，但不会破坏当前 M30 preview 产品路径。

代价：

- 上传 pipeline 多一个诊断 stage，默认会增加少量耗时。
- 每个 task 会多生成 M31 tree/report 和 unit fallback crops。
- optional failure 语义要求调试时同时看 endpoint、`stage_timings.json` 和 `error_logs`。

明确不做：

- 不把 M31 tree materialize 成 DSL。
- 不改 Renderer 或 Figma plugin contract。
- 不删除 M29.0.2-M29.0.5。
- 不用 M29.0.x/M30 DSL 作为 M31 tree 结构事实来源。

后续：

```text
如果 M31 指标稳定 -> 进入 M32 layer recovery plan
如果 M31 指标不稳定 -> 继续修 M31 grouping/ownership
```
