# 可靠性

v0.1 的可靠性目标是让当前 M29/M30 preview path 稳定、可审计、失败可解释。

## Current Task States

当前运行时使用：

```text
processing
completed
failed
```

当前典型 stage：

```text
m30_queued
ocr
m29
m29_2_source_ui_physical_graph
m29_3_relation_graph_report
m29_4_stable_design_cluster
m29_5_replay_plan
m29_direct_replay
m29_direct_asset_publish
m29_1
m29_0_2
m29_0_3
m29_0_7
m29_0_4
m29_0_5
m30_materialization
m30_asset_publish
m30_completed
```

M31/M37/M38/M39/M39.1 stage names are historical and should not appear in new upload tasks.

## Failure Strategy

Request-level failures reject upload immediately:

```text
invalid MIME
invalid PNG signature
unreadable image dimensions
file too large
```

Pipeline-level failures update the task:

```text
status = failed
stage = failing stage
message = concrete error
```

The backend also writes `error_logs`.

M29 Direct is a non-blocking compare variant. If `m29_2_source_ui_physical_graph` through `m29_direct_asset_publish` fail, the failure is recorded in `stage_timings.json` and `error_logs`, but the legacy M30 `/dsl` path may still complete. `GET /api/tasks/{taskId}/m29-direct-dsl` then returns `M29_DIRECT_DSL_NOT_FOUND` when the variant or asset publish is missing.

## OCR As Required Evidence

In the current M30 preview path, OCR is not a decorative diagnostic. It provides text evidence for M29 and M30.

Therefore:

- unsupported OCR provider fails the task.
- missing Baidu token fails the task when `OCR_PROVIDER=baidu_ppocrv5`.
- remote OCR timeout/failure fails the task.
- the backend must not mark a task completed with fake M30 DSL after OCR failure.

This is different from the removed pre-M29 fallback-first chain, where OCR failure could still return a deterministic fallback DSL.

## M29/M30 Safety

M29/M29.0.x/M30 required stages should fail fast when required evidence is invalid or missing. They must not fabricate visible DSL nodes from:

```text
mixed evidence
future candidates
audit-only references
missing source assets
newly invented bboxes
```

M30 may preserve fallback and skip unsafe text/shape/image materialization. Skips must be recorded in `m30_materialization_report.json`.

## Artifact Timing

Every M30 preview task writes:

```text
storage/m30_1_uploads/{taskId}/stage_timings.json
```

`GET /api/tasks/{taskId}/m30-materialization` returns the same timings so slow stages can be traced without scanning logs.

`GET /api/tasks/{taskId}/m29-direct-dsl` returns the same timings for compare-mode diagnosis when the direct variant is available.

## Timeouts

Suggested local preview targets:

- simple page: 15 to 30 seconds.
- medium page: 30 to 60 seconds.
- complex page: 60 to 90 seconds.
- over 120 seconds should be treated as a performance bug or provider timeout, not normal UI behavior.

## Retry Strategy

v0.1 does not implement automatic retry.

Allowed:

- user manually uploads again.
- provider-specific timeout tuning through environment variables.
- future explicit retry endpoint.

Not allowed:

- silent background reruns without task status updates.
- fabricating completed output after required evidence failure.

## Removed Reliability Rules

The old pre-M29 upload chain and M8-M28 diagnostic endpoints were removed in M30.2.2. M31-M39/M39.1 downstream experiments were later removed from backend runtime by M29 backend downstream pruning. Their fallback, optional diagnostics, ONNX proposer, hierarchy, and grouping behavior is historical only and must not be used to reason about the current product path.
