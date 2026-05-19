# ADR: Freeze Pre-M29 Legacy Upload Surface

- 状态：accepted
- 日期：2026-05-20

## Context

The plugin now uses `/api/upload-m30-preview`, which runs OCR + M29 + M30 and returns `m30_materialized_dsl.json` through the existing task DSL endpoint.

The old `/api/upload` path still registers a long M8-M28 diagnostic chain by default. That path is no longer the product mainline, but its live API surface can still distort testing, documentation, and future refactors by making legacy diagnostics look like required runtime behavior.

## Decision

Add `LEGACY_PRE_M29_UPLOAD_ENABLED=false` and make the old upload path plus pre-M29 task debug endpoints opt-in only.

Default runtime exposes the current product surface:

```text
/api/upload-m30-preview
/api/tasks/{taskId}
/api/tasks/{taskId}/dsl
/api/tasks/{taskId}/m30-materialization
/files/uploads/*
/files/assets/*
```

The legacy upload path and debug endpoints remain available when explicitly enabled for regression checks or historical diagnostics.

M1-M28 active plan documents move to `docs/plans/archive/pre_m29/`. Old ADRs stay in place because they are decision history.

## Consequences

Benefits:

- The default backend surface now matches the M29/M30 plugin path.
- Old diagnostics remain recoverable without staying in the product runtime by accident.
- Physical archiving can happen later with a cleaner import and test boundary.

Costs:

- Legacy regression tests must use a legacy-enabled client.
- Old `/api/upload` consumers now need to opt in through an environment flag.

Hard boundaries:

- Do not move or delete pre-M29 implementation modules in this stage.
- Do not delete database tables or storage helpers.
- Do not change M29/M30 algorithms, OCR, DSL schema, renderer, or plugin behavior.
- Do not implement fallback masking, web preview, or new recognition rules.

