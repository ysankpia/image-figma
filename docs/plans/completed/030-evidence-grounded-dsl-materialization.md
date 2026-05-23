# M30 Evidence-Grounded DSL Materialization

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M30 是从 M29 evidence/audit 世界进入现有 DSL v0.1 / Renderer 世界的桥。它不继续识别、不恢复图标、不做 promotion、不追完整 Codia-like 效果，只把已经通过 M29 safety gates 的可信证据保守落成 DSL 可见节点。

目标链路：

```text
M29 trusted evidence
-> existing DSL v0.1
-> Renderer / Figma-capable output
```

M29 closure 源事实：

```text
valid batch: backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_20260519_200727
invalid batch: backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_20260519_193713
invalid reason: BAIDU_PADDLE_OCR_TOKEN_MISSING
M29 closure tightening review: 70 / 103 = 0.679612 < 0.70
decision: do not start M29.0.3.3 now; move to M30
```

第一版输出新的 DSL variant，不覆盖输入 DSL：

```text
m30_materialized_dsl.json
m30_materialization_report.json
m30_materialization_preview.png
```

## Scope

包含：

- 新增 script-only M30 materializer。
- 支持 `augment-existing-dsl` 和 `bootstrap-dsl-from-m29` 两种输入模式。
- 只消费 M29.0.5 `textMembers`、可信 `shapeCandidates`、可信 `visualAssets`。
- 保留 fallback，并把 M30 text / shape / image 节点追加到 DSL `root.children`。
- 输出 materialization report，记录 materialized / skipped / audit-only reference 统计。

不包含：

- 不接上传主链路。
- 不修改 M29.0.3、M29.1.3、M29.0.7、M29.0.4、M29.0.5 或任何 M29 JSON。
- 不重新 OCR、detector、classification，也不调 text overlap threshold。
- 不新增 bbox，不从 raw pixels 新切 child bbox。
- 不做 M29.1.4、promotion、图标恢复、Auto Layout、Figma Component/Instance、SVG/vectorization。
- 不做自动 text cover；M30.2 才能单独讨论。

## Contract

Mode A: `augment-existing-dsl`，默认路径。

```text
input:
  base_dsl.json
  M29.0.5 refined_visual_objects.json
  source image

behavior:
  preserve existing DSL structure
  preserve original_reference / fallback_region_* / fallback_full_image / candidate_text
  append M30 nodes
  do not edit base_dsl.json in place
```

Mode B: `bootstrap-dsl-from-m29`，无 base DSL 时使用。

```text
input:
  source image
  M29.0.5 refined_visual_objects.json

behavior:
  create minimal root frame
  register full-image fallback asset
  append M30 nodes
```

M30 visible DSL children 只能来自：

```text
M29.0.5 textMembers
M29.0.5 safe shapeCandidates
M29.0.5 safe visualAssets
```

这些只允许进 report/meta，不能进 visible DSL children：

```text
mixed_symbol_text_candidate
future_promotable_uncertain_symbol_candidate
candidate_for_future_uncertain_review
keep_mixed_symbol_text_conflict
text_owned_rejected_lineage audit examples
M29.1.3 output
M29.0.3.2 output
```

Text node：

```text
type = text
role = m30_text_member
layout = textMember.bbox
content.text = textMember.text or textMember.textPreview
style = conservative default
meta includes sourceTextMemberId, sourceTextBoxId, sourceEvidenceNodeId, sourceObjectId, sourceBBox, ocrConfidence, materializationConfidence, riskFlags
```

Shape node：

```text
type = shape
role = m30_shape_candidate
layout = shapeCandidate.bbox
style.fill = shapeCandidate.color
only materialize reliable solid fill candidates
```

Image node：

```text
type = image
role = m30_visual_asset
asset copied from existing M29.0.5 assetPath
source.assetId references a new DSL asset
imageFill.mode = fit
```

M30 不输出 DSL `icon` element。当前 Renderer 对 `icon` type 不支持，safe visual asset 必须先落成 `image`。

## Steps

1. 新增计划与 ADR，并同步 docs index、backend README、DSL architecture、testing strategy。
2. 新增 `backend/app/evidence_grounded_dsl_materialization.py`，实现双模式 materialization、report、preview、validation。
3. 新增 `backend/scripts/run_m30_evidence_grounded_dsl_materialization.py`，支持单图和 10 图 smoke batch。
4. 新增 focused tests，覆盖 DSL 合同、M29 输入只读、fallback 保留、audit-only 不进 visible children、forbidden contract term check。

## Acceptance

- `augment-existing-dsl` 保留 base DSL 和 fallback，只追加 M30 节点。
- `bootstrap-dsl-from-m29` 能创建最小 root frame + full-image fallback。
- M29.0.5 textMembers 生成可编辑 DSL text nodes，带 source trace。
- 可信 shapeCandidates 生成 shape nodes，不可靠 shape skip 并写 reason。
- 可信 visualAssets 生成 DSL image nodes 和 assets entries，不使用 DSL `icon` type。
- mixed/future/audit-only 只进入 report/meta，不进入 M30 visible DSL children。
- `createdNewBBoxCount = 0`。
- `permissionViolationCount = 0`。
- `fallbackPreserved = true`。
- `forbiddenHitCount = 0`。
- M29 source JSON 不被改写。

## Validation

```bash
cd backend && uv run pytest tests/test_evidence_grounded_dsl_materialization.py -q
```

```bash
cd backend && uv run pytest \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_text_aware_visual_object_refinement.py \
  tests/test_mixed_symbol_text_conflict_audit.py \
  tests/test_residual_mixed_boundary_review.py -q
```

```bash
pnpm run check
git diff --check
git status --short
```

## Notes

- `backend/storage/**` 是 diagnostic artifact，不提交。
- M31 才讨论 standalone web preview/export package。
- M32 才讨论 Figma import adapter。
- M40 才讨论 direct `.fig` / Figma file export。
