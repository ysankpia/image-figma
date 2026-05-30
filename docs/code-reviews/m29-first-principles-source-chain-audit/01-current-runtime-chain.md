# 01 Current Runtime Chain

> Historical Python M29 preview audit. Current Codia Beta `Generate Beta` debugging starts from Go `services/backend-go/cmd/codiaserver` and `/api/codia-preview`, not from `/api/upload-preview`.

## Source Truth

当前产品主链以 `POST /api/upload-preview` 上传的 PNG 为 source input。正式 Figma-visible 设计输出来自 `GET /api/tasks/{taskId}/dsl` 返回的 `materialized_design/design.dsl.json`。

关键代码：

```text
backend/app/routes/upload_preview.py:16
backend/app/upload_preview/pipeline.py:48
backend/app/routes/tasks.py:37
```

`upload_preview.py` 只接受 PNG，并保存 upload，再把 `run_upload_preview_pipeline` 放入 FastAPI background task。它不执行 M29 决策，不写 DSL。见：

```text
backend/app/routes/upload_preview.py:21-35
backend/app/routes/upload_preview.py:45-65
```

`tasks.py` 的 DSL endpoint 只读数据库记录中的 DSL path，再读 JSON 返回。它没有 fallback 或二次 materialization 逻辑。见：

```text
backend/app/routes/tasks.py:37-77
```

## Input Artifacts

```text
storage/uploads/{taskId}/original.png
ocr/ocr.json
```

`run_pipeline` 从 `state.storage.upload_path(task_id)` 读 PNG bytes，并用 `read_png_metadata` 校验尺寸。见：

```text
backend/app/upload_preview/pipeline.py:51-56
```

OCR 输出由 `run_ocr` 写入 `ocr/ocr.json`，并保存数据库 OCR result。OCR failure 会抛出 pipeline error，不进入 M29。见：

```text
backend/app/upload_preview/stages.py:33-56
```

## Output Artifacts

路径布局由 `UploadPreviewPaths` 固定：

```text
ocr/
m29/
m29_2/
m29_3/
m29_4/
m29_5/
m29_ownership_conservation/
m29_media_internal_decomposition/
m29_transparent_assets/
m29_evidence_contract/
m29_internal_source_promotion/
m29_hierarchy_candidates/
m29_sibling_groups/
m29_layout_energy/
m29_auto_layout_permission/
m29_design_tokens/
m29_b_stage_quality/
m29_dsl_visual_comparison/
materialized_design/
```

代码位置：

```text
backend/app/upload_preview/paths.py:9-56
```

每个 stage 的 timing 写入：

```text
stage_timings.json
```

`run_stage` 会在 running、completed、failed 三种状态下写 timing。见：

```text
backend/app/upload_preview/timings.py:37-84
```

## Runtime Chain

当前 `run_pipeline` 的权威执行顺序是：

```text
ocr
-> m29
-> m29_2_source_ui_physical_graph
-> m29_3_relation_graph_report
-> m29_4_stable_design_cluster
-> m29_5_replay_plan
-> m29_ownership_conservation
-> m29_media_internal_decomposition
-> m29_transparent_assets
-> m29_evidence_contract
-> m29_internal_source_promotion
-> m29_3_relation_graph_report_promoted
-> m29_4_stable_design_cluster_promoted
-> m29_5_replay_plan_promoted
-> m29_ownership_conservation_promoted
-> m29_hierarchy_candidates
-> m29_sibling_groups
-> m29_layout_energy
-> m29_auto_layout_permission
-> m29_materialization
-> m29_design_tokens
-> m29_b_stage_quality
-> m29_asset_publish
-> m29_dsl_visual_comparison
-> database dsl result
-> task completed
```

代码证据：

```text
backend/app/upload_preview/pipeline.py:59-398
```

关键断点：

```text
promotion_result = run_m29_internal_source_promotion_stage(...)
m292_document = promotion_result.m292_document
```

见：

```text
backend/app/upload_preview/pipeline.py:189-203
```

这说明 promotion 是唯一把 M29.6/transparent/evidence 结果写回 M29.2 source ownership document 的桥。promotion 后，系统会重跑 M29.3、M29.4、M29.5、ownership conservation。见：

```text
backend/app/upload_preview/pipeline.py:205-255
```

## Decision Authority

### This layer can decide

`upload_preview/pipeline.py` 只决定 stage order、artifact wiring、final artifact persistence。它有编排权。

它决定：

```text
1. 哪个 M29.2 document 是 materializer 的输入。
2. promotion 后哪些 report 需要重跑。
3. 哪个 DSL path 被写入数据库。
4. 哪些 report 作为后续 stage 输入。
```

### This layer must not decide

它不应该决定：

```text
pixelOwner
visualKind
replayDecision
cleanupTargets
internal candidate acceptance
transparent allow/reject
evidence contract mode
DSL visible node content
```

当前代码符合这个边界：`stages.py` 只是薄 wrapper，把输入交给各 package 的 `extract_...` 或 `build_...` 函数。见：

```text
backend/app/upload_preview/stages.py:59-370
```

## Report-Only Surfaces

从 orchestrator 看，以下 report 会作为 materializer 前置 evidence，但不直接写 DSL：

```text
M29.3 relation graph
M29.4 stable design cluster
ownership conservation
M29.6 media internal decomposition
transparent asset report
evidence contract
hierarchy candidates
sibling groups
layout energy
auto layout permission
design token
B-stage quality
dsl visual comparison
```

其中需要特别注意：

```text
transparent asset report 会生成诊断/候选资产，但不能替代 source ownership。
evidence contract 可以 allow/report/reject，但本身不能创建 source object。
internal source promotion 才能把 allowed internal candidate 写回 M29.2。
M29.5 replay plan 才能授权 visible replay 和 cleanup。
```

## Batch Validation Authority

`backend/scripts/run_upload_preview_batch_validation.py` 是真实 HTTP flow 验证脚本，不绕过 API。它会启动独立 backend，逐个调用 `/api/upload-preview`，轮询 `/api/tasks/{taskId}`，然后收集 artifacts。见：

```text
backend/scripts/run_upload_preview_batch_validation.py:28-84
backend/scripts/run_upload_preview_batch_validation.py:132-160
backend/scripts/run_upload_preview_batch_validation.py:248-306
```

它只支持上传 PNG，非 PNG 记录为 `unsupported_input_format`。见：

```text
backend/scripts/run_upload_preview_batch_validation.py:18-19
backend/scripts/run_upload_preview_batch_validation.py:189-200
```

它收集的 artifact 清单足够覆盖当前 M29 主链，包括 M29、M29.2、M29.3、M29.4、M29.5、ownership、M29.6、transparent、evidence、promotion、materialization、quality 和 visual comparison。见：

```text
backend/scripts/run_upload_preview_batch_validation.py:309-360
```

## Information Loss

当前 orchestrator 的主要信息损失不是计算损失，而是 artifact replacement / naming loss：

```text
1. m29_3、m29_4、m29_5、ownership 的同一路径会在 promotion 后被重写为 final report。
2. stage_timings 仍保留 pre-promotion 和 promoted stage 名称，能证明重跑发生。
3. 如果要比较 promotion 前后的 M29.5 plan，需要依赖 stage timing 或临时复制，当前默认 artifact path 不保存两个版本。
```

这不是 P0，但会影响审计和 debug。它属于 P2 evidence quality gap：final artifact 是权威输出，但 pre-promotion artifact 对根因追踪也有价值。

## Known Failure Symptoms Mapped To This Layer

```text
文字可编辑但 icon 不可选:
  orchestrator 不是 owner。它已经正确把 M29.6 -> transparent -> evidence -> promotion 接起来。
  若 icon 不可选，应继续追 transparent/evidence/promotion/M29.5。

button 背景不可拖:
  orchestrator 不是 owner。若 source object 从未出现，应追 raw M29/M29.2/M29.6 control-background evidence。

single sample improvement 没有泛化:
  orchestrator 不是 owner。应追对应 layer 的 heuristic 和 tests。
```

## Findings

### P2: Pre-promotion artifacts are overwritten by final reports

Owner layer:

```text
upload_preview orchestration / artifact policy
```

Evidence:

```text
backend/app/upload_preview/pipeline.py:91-127
backend/app/upload_preview/pipeline.py:205-241
backend/app/upload_preview/paths.py:38-42
```

Problem:

```text
m29_3, m29_4, m29_5, ownership_conservation share one final path.
The promoted rerun is correct for runtime, but audit/debug loses the default pre-promotion JSON unless captured externally.
```

Do not fix by:

```text
changing API output
changing materializer input
skipping promoted rerun
```

Recommended next action:

```text
Consider a later report-only artifact split:
  m29_5_pre_promotion/
  m29_5/
or add explicit prePromotionSummary in promotion report.
Not required before source-chain audit continues.
```

### P3: Batch script has enough artifact coverage but still records filename fields

Owner layer:

```text
validation tooling
```

Evidence:

```text
backend/scripts/run_upload_preview_batch_validation.py:203-238
```

This is not product specialization because filename is ledger metadata only. The anti-specialization risk would exist only if production code consumed these names for decisions. Current evidence does not show that.

## Recommended Next Action

Continue to M29.0 raw primitive graph. The orchestrator is structurally correct enough for this audit: it preserves the intended bridge order and does not invent M29 facts. The next real risk starts in raw M29 evidence extraction and M29.2 ownership.
