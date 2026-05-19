# ADR: Route Plugin Upload Through M29 to M30 Preview Pipeline

- 状态：accepted
- 日期：2026-05-19

## Context

The plugin upload path still used the legacy fallback-first route. That route was useful for M6-M25 diagnostics, but it does not exercise the current evidence chain. The current source of truth for object ownership is OCR + M29+ evidence, and M30 materializes trusted M29.0.5 evidence into DSL v0.1.

Keeping the plugin on the old route creates the wrong product signal: users see a Figma render, but it is mostly deterministic fallback plus old hidden candidates rather than the M29/M30 path we need to validate.

## Decision

Add a new preview endpoint:

```text
POST /api/upload-m30-preview
```

The endpoint keeps the existing upload result shape, creates a task immediately, and runs OCR + M29 + M30 in a FastAPI background task. On success, the task's DSL result points at:

```text
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
```

The plugin default upload action uses the new endpoint. Legacy `POST /api/upload` remains available as a comparison path and is not deleted.

M30.1 does not change the DSL schema and does not allow mixed/future/audit-only evidence into visible DSL children. Local M30 DSL asset URLs are rewritten into `/files/assets/{taskId}/m30/...` URLs so the existing renderer can fetch images without a new renderer contract.

## Consequences

Benefits:

- The product entrypoint now validates the OCR + M29 + M30 bridge rather than the old fallback-first chain.
- Existing `GET /api/tasks/{taskId}/dsl` and renderer flow stay unchanged.
- Background task execution avoids the plugin staying in the upload phase while the pipeline runs.
- M19-M25 legacy diagnostics stop being part of the default plugin path.

Costs:

- Local processing is heavier than the legacy deterministic upload path.
- In-process background work is acceptable for local preview but not a production queue design.
- The first preview version may still show fallback underneath editable M30 nodes because M30.1 does not do text cover.

Hard boundaries:

- Do not change M29 classification rules in this stage.
- Do not run M29.1.3, M29.0.3.2, M29.0.6, M19-M25, M26-M28 in the default preview pipeline.
- Do not modify M29 source JSON after each stage writes it.
- Do not create new bboxes or raw-pixel child crops outside the existing M29/M30 contracts.
- Do not emit DSL `icon` nodes.
- Do not implement Auto Layout, Components, SVG/vectorization, text cover, production auth, or a queue system.
