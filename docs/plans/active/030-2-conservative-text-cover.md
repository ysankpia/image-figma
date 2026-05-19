# M30.2 Conservative Text Cover

- 状态：active
- 创建日期：2026-05-20
- 负责人：Codex

## Goal

M30.2 reduces the most visible M30.1 preview artifact: editable text rendered over the same text still present in the fallback image.

The stage adds conservative `m30_text_cover` DSL shape nodes under accepted `m30_text_member` nodes. It does not change OCR, M29 classification, DSL schema, renderer behavior, fallback visibility, or asset promotion.

## Contract

M30.2 runs inside M30 evidence-grounded DSL materialization:

```text
M29.0.5 textMembers
-> M30 text nodes
-> conservative background sampling from the existing text bbox
-> m30_text_cover shape nodes
-> existing DSL v0.1 renderer
```

Layer order is fixed:

```text
fallback / original reference
m30_shape_candidate
m30_visual_asset
m30_text_cover
m30_text_member
```

Cover nodes are ordinary DSL `shape` elements with `style.fill`. They reuse source text bboxes and record source trace in `meta`.

## Acceptance

- Stable solid-background text members produce `m30_text_cover`.
- Complex or risky text members are skipped with generic reasons.
- Covers never use mixed, future, or audit-only evidence as visible sources.
- Fallback remains visible and complete.
- `createdNewBBoxCount`, `permissionViolationCount`, `visibleAuditOnlyChildCount`, and `forbiddenHitCount` remain `0`.
- M30.1 production profile still skips diagnostic preview artifacts.

## Validation

```bash
cd backend && uv run pytest \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_m30_upload_pipeline.py -q
```

```bash
cd backend && uv run pytest \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_upload_flow.py -q

pnpm run check
git diff --check
git status --short
```

## Notes

M30.2 is not fallback masking. M30.3 will decide whether materialized layers can hide fallback regions. M30.2 only covers text bboxes when the local background sample is stable enough.
