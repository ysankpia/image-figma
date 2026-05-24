# 可靠性

v0.1 的可靠性目标是让当前 M29 plan-driven preview path 稳定、可审计、失败可解释。

## Current Task States

当前运行时使用：

```text
processing
completed
failed
```

当前典型 stage：

```text
m29_queued
ocr
m29
m29_2_source_ui_physical_graph
m29_3_relation_graph_report
m29_4_stable_design_cluster
m29_5_replay_plan
m29_materialization
m29_asset_publish
m29_completed
```

M29 Direct、M29.0.x、M30、M31/M37/M38/M39/M39.1 stage names are historical and should not appear in new upload tasks.

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

There is no longer a non-blocking compare materializer in the product path. If M29.2, M29.3, M29.4, M29.5, materialization, or asset publish fails, `/api/tasks/{taskId}/dsl` must not pretend to be ready.

## OCR As Required Evidence

In the current M29 preview path, OCR is not a decorative diagnostic. It provides text evidence for M29 ownership and materialization.

Therefore:

- unsupported OCR provider fails the task.
- missing Baidu token fails the task when `OCR_PROVIDER=baidu_ppocrv5`.
- remote OCR timeout/failure fails the task.
- the backend must not mark a task completed with fake DSL after OCR failure.

This is different from the removed pre-M29 fallback-first chain, where OCR failure could still return a deterministic fallback DSL.

## M29 Safety

M29 required stages should fail fast when required evidence is invalid or missing. They must not fabricate visible DSL nodes from:

```text
mixed evidence
future candidates
audit-only references
missing source assets
newly invented bboxes
weak cluster hints
```

M29 materializer may preserve fallback and skip unsafe text/shape/image materialization. Skips must be recorded in `materialization_report.json`.

Cleanup must be plan-authorized:

```text
fallback erasure -> only if M29.5 cleanupTargets includes target=fallback
copied raster/media cleanup -> only if M29.5 cleanupTargets includes target=copied_image_asset
```

Materializer must not independently recompute cleanup ownership from contains/overlap.

## Artifact Timing

Every preview task writes:

```text
storage/upload_previews/{taskId}/stage_timings.json
```

`GET /api/tasks/{taskId}/materialization` returns the same timings so slow stages can be traced without scanning logs.

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

The old pre-M29 upload chain and M8-M28 diagnostic endpoints were removed in M30.2.2. M31-M39/M39.1 downstream experiments were later removed from backend runtime by M29 backend downstream pruning. M29 Direct compare and legacy M30 materialization product paths have also been removed from current runtime. Their fallback, optional diagnostics, ONNX proposer, hierarchy, grouping, and M30-specific behavior is historical only and must not be used to reason about the current product path.
