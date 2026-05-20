# M30.2.2 Remove Frozen Pre-M29 Legacy Backend Chain

- 状态：completed
- 创建日期：2026-05-20
- 负责人：Codex

## Goal

Remove the frozen pre-M29 backend chain from active runtime source so the product entry only preserves the current path:

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR + M29 + M30
-> GET /api/tasks/{taskId}/dsl
-> Renderer
```

The deletion boundary is current product consumption, not historical milestone number. OCR, PNG helpers, DSL fallback, database, storage, asset routes, M29, and M30 stay because the current path still consumes them.

## Scope

Remove:

- `POST /api/upload`.
- M8-M28 legacy task debug endpoints.
- `LEGACY_PRE_M29_UPLOAD_ENABLED`.
- Frozen pre-M29 app modules used only by the old upload/debug path.
- Legacy M26-M28 smoke scripts.
- Pure legacy module tests.

Keep:

- `POST /api/upload-m30-preview`.
- `GET /api/tasks/{taskId}`.
- `GET /api/tasks/{taskId}/dsl`.
- `GET /api/tasks/{taskId}/m30-materialization`.
- `GET /api/assets/{assetId}`.
- `/files/uploads/*` and `/files/assets/*`.
- OCR provider code and tests.
- M29/M30 app modules, scripts, tests, and docs.
- Current database/storage helpers needed by M30 preview.

Do not:

- delete OCR.
- delete M29/M30.
- change DSL schema or Renderer.
- run database migration.
- delete local `backend/storage/**`.
- preserve legacy recovery through an env flag.

## Steps

1. Remove legacy routers and config flag.
2. Delete frozen pre-M29 modules, scripts, and pure legacy tests.
3. Rewrite current tests around `/api/upload-m30-preview`.
4. Keep shared current tests for OCR, assets, config, upload flow, M29, and M30.
5. Update active docs so current runtime no longer describes the old upload path as available.
6. Update legacy inventory from archive candidate to removed source status.
7. Run static guards, focused tests, full backend tests, frontend check, and diff hygiene.

## Acceptance

- `/api/upload` is permanently absent and returns 404.
- Legacy task debug endpoints are absent.
- `LEGACY_PRE_M29_UPLOAD_ENABLED` is absent from active backend source/tests.
- 17 frozen pre-M29 modules are deleted.
- 3 legacy smoke scripts are deleted.
- Pure legacy module tests are deleted.
- OCR provider tests still pass.
- Asset route tests still pass.
- M29/M30 tests still pass.
- M30 preview upload tests still pass.
- Active docs describe only the current product API and pipeline.
- Historical plans/ADRs remain as traceability evidence.

## Validation

Static guard:

```bash
rg "LEGACY_PRE_M29_UPLOAD_ENABLED|legacy_pre_m29_upload_enabled|legacy_router|routes/upload|legacy_tasks" \
  backend/app backend/tests
```

Focused backend tests:

```bash
cd backend
uv run pytest \
  tests/test_m30_upload_pipeline.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_upload_flow.py \
  tests/test_config_env.py \
  tests/test_assets.py \
  tests/test_baidu_ocr.py -q
```

Current M29/M30 chain tests:

```bash
cd backend
uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_symbol_fragment_grouping.py \
  tests/test_pre_ocr_symbol_lineage_audit.py \
  tests/test_text_masked_media_audit.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py \
  tests/test_visual_object_candidate_audit.py \
  tests/test_text_aware_visual_object_refinement.py \
  tests/test_member_boundary_quality_audit.py \
  tests/test_mixed_symbol_text_conflict_audit.py \
  tests/test_residual_mixed_boundary_review.py \
  tests/test_evidence_grounded_dsl_materialization.py -q
```

Full validation:

```bash
cd backend && uv run pytest -q
pnpm run check
git diff --check
git status --short
```

## Notes

This is a destructive source cleanup, not a historical data migration. Old local SQLite tables or storage files may remain on developer machines, but active source no longer initializes or consumes the removed legacy chain.
