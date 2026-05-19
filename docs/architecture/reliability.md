# 可靠性

v0.1 的可靠性目标是让当前主链路稳定、可审计、失败可解释。

## Current Task States

当前运行时使用：

```text
processing
completed
failed
```

典型 stage：

```text
m30_queued
ocr
m29
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

## OCR As Required Evidence

In the current M30 preview path, OCR is not a decorative diagnostic. It provides text ownership evidence for M29 and source text for M30 materialization.

Therefore:

- unsupported OCR provider fails the task.
- missing Baidu token fails the task when `OCR_PROVIDER=baidu_ppocrv5`.
- remote OCR timeout/failure fails the task.
- the backend must not mark a task completed with fake M30 DSL after OCR failure.

This is different from the removed pre-M29 fallback-first chain, where OCR failure could still return a deterministic fallback DSL.

## M29/M30 Safety

M29/M30 failures should fail fast when required evidence is invalid or missing. They must not fabricate visible DSL nodes from:

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

## Removed Legacy Reliability Rules

The old pre-M29 upload chain and M8-M28 diagnostic endpoints were removed in M30.2.2. Their fallback-first reliability behavior is historical only and must not be used to reason about the current product path.
