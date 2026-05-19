# ADR: Freeze Pre-M29 Legacy Upload Surface

- 状态：superseded-by-0048
- 日期：2026-05-20

## Supersession

This ADR records the intermediate M30.2.1 freeze. It was superseded by [0048-remove-frozen-pre-m29-legacy-backend-chain.md](0048-remove-frozen-pre-m29-legacy-backend-chain.md), which removed the legacy recovery flag, old upload route, old debug endpoints, and frozen pre-M29 backend modules from active source.

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

At the time of M30.2.1, the legacy upload path and debug endpoints remained available when explicitly enabled for regression checks or historical diagnostics. That is no longer current runtime behavior after ADR 0048.

M1-M28 active plan documents move to `docs/plans/archive/pre_m29/`. Old ADRs stay in place because they are decision history.

## Consequences

Benefits:

- The default backend surface now matches the M29/M30 plugin path.
- Old diagnostics became isolated before later physical source removal.
- Physical archiving can happen later with a cleaner import and test boundary.

Costs:

- This intermediate state was intentionally temporary.
- After ADR 0048, legacy regression through active source is no longer supported.

Hard boundaries:

- Do not move or delete pre-M29 implementation modules in this stage.
- Do not delete database tables or storage helpers.
- Do not change M29/M30 algorithms, OCR, DSL schema, renderer, or plugin behavior.
- Do not implement fallback masking, web preview, or new recognition rules.
