# M31.1 Attach Reconstruction Diagnostics To Upload Pipeline

- 状态：active
- 创建日期：2026-05-20
- 负责人：未指定

## Goal

M31.1 把 M31 reconstruction UI tree 接到真实 `/api/upload-m30-preview` 上传链路旁路。第一性原理目标不是改变 Figma 输出，而是验证：

```text
M29 primitive evidence
能不能在真实上传图上稳定组织成 reconstruction units
```

当前可见产品链路保持：

```text
/api/upload-m30-preview
-> OCR + M29 + M29.0.x + M30
-> DSL
-> Renderer
-> Figma
```

新增诊断旁路：

```text
OCR + M29 nodes.json
-> M31 reconstruction tree/report
-> GET /api/tasks/{taskId}/m31-reconstruction
```

## Scope

包含：

- `/api/upload-m30-preview` 默认在 M29 后运行 M31 diagnostics。
- M31 只消费 source PNG、OCR document/JSON、M29 document/`nodes.json`。
- 新增 `M31_UPLOAD_DIAGNOSTICS_ENABLED` 和 `M31_UPLOAD_DIAGNOSTICS_STRICT`。
- 新增 `GET /api/tasks/{taskId}/m31-reconstruction`，只返回 report 摘要，不返回完整 tree。
- M31 stage 写入现有 `stage_timings.json`。
- production profile 不生成 M31 overlay；development profile 生成 overlay。
- M31 默认非阻塞失败，strict 模式失败才让 task failed。
- 更新测试、文档和 ADR。

不包含：

- 不把 M31 写进 DSL。
- 不改变 Renderer 或 Figma plugin UI。
- 不替换 M30 materialization。
- 不删除 M29.0.2-M29.0.5。
- 不让 M31 读取 M29.0.2/M29.0.3/M29.0.4/M29.0.5/M30 DSL 作为结构输入。
- 不做 M32 layer recovery、M33 recomposition validation、M34 DSL materializer。

## Steps

1. 在配置中新增 M31 upload diagnostics enabled/strict 开关。
2. 在 M30 preview pipeline 的 M29 后插入 `m31_reconstruction` stage。
3. 默认用 optional stage 包裹 M31，失败只记录 `error_logs` 和 failed timing。
4. strict 模式把 M31 异常转换成 `M30UploadPipelineError(stage="m31_reconstruction")`。
5. 新增 `/api/tasks/{taskId}/m31-reconstruction` endpoint，读取 `m31_reconstruction_tree_report.json` 和 stage timings。
6. 更新 upload pipeline tests，覆盖默认生成、禁用、optional failure、strict failure、profile artifact 行为。
7. 更新文档、API contract、observability、reliability、env vars 和 ADR。

## Acceptance

- `/api/upload-m30-preview` 默认生成 `storage/m30_1_uploads/{taskId}/m31/m31_reconstruction_tree.json`。
- 默认生成 `m31_reconstruction_tree_report.json` 和 unit fallback assets。
- `GET /api/tasks/{taskId}/m31-reconstruction` 返回 summary、warnings、reviewBuckets、unitSummaries、outputTree、debugOverlayPath 和 stageTimings。
- `stage_timings.json` 包含 `m31_reconstruction`。
- production profile 下不生成 `m31_reconstruction_tree_overlay.png`。
- development profile 下生成 `m31_reconstruction_tree_overlay.png`。
- M31 report 保持 `createdDetectionBBoxCount=0`、`permissionViolationCount=0`、`rootLeafPrimitiveCount=0`、`unitFallbackCoverage=1.0`、`forbiddenHitCount=0`。
- M31 optional failure 在 strict=false 时不阻断 M30 DSL。
- M31 strict failure 在 strict=true 时让 task failed，stage 为 `m31_reconstruction`。
- `M31_UPLOAD_DIAGNOSTICS_ENABLED=false` 时不生成 M31 目录，endpoint 返回 `M31_RECONSTRUCTION_NOT_FOUND`。
- M30 DSL、Renderer asset URL 和 plugin 合同不变。

## Validation

Focused:

```bash
cd backend
uv run pytest tests/test_m30_upload_pipeline.py tests/test_reconstruction_ui_tree.py -q
```

Regression:

```bash
cd backend
uv run pytest \
  tests/test_m30_upload_pipeline.py \
  tests/test_reconstruction_ui_tree.py \
  tests/test_upload_flow.py \
  tests/test_config_env.py \
  tests/test_evidence_grounded_dsl_materialization.py -q
```

Full:

```bash
cd backend && uv run pytest -q
pnpm run check
git diff --check
git status --short
```

Manual smoke:

```bash
cd backend
M30_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then upload 1 to 3 PNGs from the plugin and inspect:

```text
GET /api/tasks/{taskId}/dsl
GET /api/tasks/{taskId}/m30-materialization
GET /api/tasks/{taskId}/m31-reconstruction
```

## Notes

M31.1 的通过标准不是“生成图像更像”，而是 reconstruction tree 的结构质量能在真实上传图上被观测：

```text
primitiveOwnershipRate
unitFallbackCoverage
rootLeafPrimitiveCount
orphanPrimitiveCount
reviewBucketCount
forbiddenHitCount
```

如果这些指标稳定，再进入 M32；如果 review bucket 爆炸或 ownership 不稳定，先修 M31 grouping/ownership。
