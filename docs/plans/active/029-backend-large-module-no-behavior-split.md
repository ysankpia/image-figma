# Backend Large Module No-Behavior Split Program

- 状态：active
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

按顺序拆分 9 个后端大文件，让后端模块更高内聚、低耦合。所有阶段都是 no-behavior split：不改算法、阈值、JSON 输出 shape、storage path、API、upload pipeline stage 名或 runtime 语义。

## Scope

包含：

- `backend/app/text_aware_visual_object_refinement.py`
- `backend/app/visual_object_candidate_audit.py`
- `backend/app/symbol_fragment_grouping.py`
- `backend/app/visual_primitive_graph.py`
- `backend/app/text_masked_media_audit.py`
- `backend/app/text_visual_ownership_gate.py`
- `backend/app/visual_evidence_normalization.py`
- `backend/app/png_tools.py`
- `backend/app/source_ui_physical_graph.py`

不包含：

- 算法、阈值、owner、cleanup 授权、replay decision 或 detector 行为修改。
- API、DSL、storage、stage timing 或 artifact filename 修改。
- 测试语义重写。
- legacy runtime 恢复。

## Steps

1. Completed: split `text_aware_visual_object_refinement` into a same-name package.
2. Completed: split `visual_object_candidate_audit` into a same-name package.
3. Completed: split `symbol_fragment_grouping` into a same-name package.
4. Completed: split remaining `visual_primitive_graph` responsibilities into `visual_primitive/`.
5. Completed: split `text_masked_media_audit` into a same-name package.
6. Completed: split `text_visual_ownership_gate` into a same-name package.
7. Completed: split `visual_evidence_normalization` into a same-name package.
8. Split `png_tools` into a same-name package.
9. Split `source_ui_physical_graph` into a same-name package.
10. Move this plan to completed and update completed plan index.

Each implementation phase must preserve the original public import surface via package `__init__.py` or compatibility re-exports.

## Phase Log

- 2026-05-24: Phase 1 split `backend/app/text_aware_visual_object_refinement.py` into `backend/app/text_aware_visual_object_refinement/` with public import compatibility preserved. Focused regression passed: `cd backend && uv run pytest tests/test_text_aware_visual_object_refinement.py -q`.
- 2026-05-24: Phase 2 split `backend/app/visual_object_candidate_audit.py` into `backend/app/visual_object_candidate_audit/` with public import compatibility preserved. Focused regression passed: `cd backend && uv run pytest tests/test_visual_object_candidate_audit.py -q`.
- 2026-05-24: Phase 3 split `backend/app/symbol_fragment_grouping.py` into `backend/app/symbol_fragment_grouping/` with public import compatibility preserved. Focused regression passed: `cd backend && uv run pytest tests/test_symbol_fragment_grouping.py -q`.
- 2026-05-24: Phase 4 split remaining raw M29 detector/support/relation/artifact/validation responsibilities into `backend/app/visual_primitive/`, leaving `backend/app/visual_primitive_graph.py` as a thin orchestration and compatibility entry. Focused regression passed: `cd backend && uv run pytest tests/test_visual_primitive_graph.py -q`. High-risk mainline regression passed: `cd backend && uv run pytest tests/test_visual_primitive_graph.py tests/test_source_ui_physical_graph.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q`.
- 2026-05-24: Phase 5 split `backend/app/text_masked_media_audit.py` into `backend/app/text_masked_media_audit/` with public import compatibility preserved, including `text_boxes_from_ocr_document`. Focused regression passed: `cd backend && uv run pytest tests/test_text_masked_media_audit.py -q`.
- 2026-05-24: Phase 6 split `backend/app/text_visual_ownership_gate.py` into `backend/app/text_visual_ownership_gate/` with public import compatibility preserved. Focused regression passed: `cd backend && uv run pytest tests/test_text_visual_ownership_gate.py -q`. Three-phase backend regression passed: `cd backend && uv run pytest -q`.
- 2026-05-24: Phase 7 split `backend/app/visual_evidence_normalization.py` into `backend/app/visual_evidence_normalization/` with public import compatibility preserved, including `parse_bbox` and `parse_metrics`. Focused regression passed: `cd backend && uv run pytest tests/test_visual_evidence_normalization.py -q`. Import-dependent regression passed: `cd backend && uv run pytest tests/test_visual_evidence_normalization.py tests/test_visual_object_candidate_audit.py tests/test_text_aware_visual_object_refinement.py tests/test_text_visual_ownership_gate.py -q`.

## Acceptance

- The 9 target files are split, or `visual_primitive_graph.py` remains only as a thin orchestration/compatibility entry.
- Public imports used by application code and tests continue to work.
- New modules have clear responsibility and do not create `utils`, `common`, or `misc` dumping grounds.
- No output behavior, artifact path, JSON shape, API, DSL, stage timing, or runtime contract changes.
- Each phase is committed independently with scoped code, tests, docs, and plan updates only.

## Validation

Per phase:

```bash
git diff --check
cd backend
uv run pytest <matching focused test file> -q
```

High-risk current-mainline phases also run:

```bash
cd backend
uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  -q
```

Every 3 implementation phases:

```bash
cd backend
uv run pytest -q
```

Final validation:

```bash
cd backend
uv run pytest -q
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
git status --short --branch
```

## Notes

- Continue directly on `main`.
- Tests remain the behavior safety net and should not be structurally split in this program.
- If a real bug is exposed, make only the minimum fix required to preserve behavior and record it in this plan.
