# M30.2.1 Legacy Pre-M29 Surface Freeze

- 状态：active
- 创建日期：2026-05-20
- 负责人：Codex

## Goal

M30.2.1 freezes the old pre-M29 upload and diagnostic API surface so it no longer shapes the default product runtime.

The current product path is:

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR + M29 + M30
-> GET /api/tasks/{taskId}/dsl
-> Renderer
```

The legacy path becomes an explicitly enabled diagnostic reference:

```text
LEGACY_PRE_M29_UPLOAD_ENABLED=true
-> POST /api/upload
-> legacy task debug endpoints
```

## Scope

This stage does not move the pre-M29 implementation modules. It only freezes runtime exposure and prepares physical archive inventory.

Default backend runtime keeps:

```text
GET /api/health
POST /api/upload-m30-preview
GET /api/tasks/{taskId}
GET /api/tasks/{taskId}/dsl
GET /api/tasks/{taskId}/m30-materialization
GET /api/assets/{assetId}
/files/uploads/*
/files/assets/*
```

Default backend runtime does not register:

```text
POST /api/upload
GET /api/tasks/{taskId}/primitives
GET /api/tasks/{taskId}/ocr
GET /api/tasks/{taskId}/dsl-patch
GET /api/tasks/{taskId}/text-replacements
GET /api/tasks/{taskId}/text-bindings
GET /api/tasks/{taskId}/component-structures
GET /api/tasks/{taskId}/component-annotations
GET /api/tasks/{taskId}/layer-separation-candidates
GET /api/tasks/{taskId}/asset-slice-candidates
GET /api/tasks/{taskId}/icon-candidates
GET /api/tasks/{taskId}/icon-coverage-audit
GET /api/tasks/{taskId}/icon-gap-candidates
GET /api/tasks/{taskId}/icon-placement-plan
GET /api/tasks/{taskId}/icon-visible-fallback
GET /api/tasks/{taskId}/icon-business-candidates
GET /api/tasks/{taskId}/perception-benchmark
GET /api/tasks/{taskId}/sam-visual-candidates
```

## Implementation

- Add `LEGACY_PRE_M29_UPLOAD_ENABLED=false` to settings.
- Register legacy upload and legacy task debug routers only when the flag is true.
- Keep `routes/upload.py` as legacy-only and a physical archive candidate.
- Split task endpoints so `tasks.py` exposes only current task, DSL, and M30 materialization endpoints by default.
- Keep old implementation modules, old database tables, and storage helpers in place.
- Move M1-M28 plan documents from `docs/plans/active/` to `docs/plans/archive/pre_m29/`.
- Add `docs/reference/legacy/pre-m29-archive-inventory.md` as the handoff list for M30.2.2.

## Acceptance

- Default `/api/upload` returns 404.
- Default legacy task debug endpoints return 404.
- `/api/upload-m30-preview` still completes and returns M30 DSL.
- `/api/tasks/{taskId}/m30-materialization` still returns report and stage timings.
- Setting `LEGACY_PRE_M29_UPLOAD_ENABLED=true` keeps the old upload regression path available.
- M29/M30 code, DSL schema, renderer, OCR behavior, database schema, and storage layout are not changed.
- M1-M28 plans are no longer in `docs/plans/active/`.

## Validation

```bash
cd backend && uv run pytest \
  tests/test_m30_upload_pipeline.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_upload_flow.py -q
```

```bash
cd backend && uv run pytest -q
pnpm run check
git diff --check
git status --short
```

## Follow-Up

M30.2.2 should physically archive or remove the frozen pre-M29 modules, tests, and scripts after this runtime freeze is verified.

