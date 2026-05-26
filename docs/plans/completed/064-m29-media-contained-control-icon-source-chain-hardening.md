# 064 M29 Media-Contained Control Icon Source-Chain Hardening

- 状态：completed
- 创建日期：2026-05-26
- 完成日期：2026-05-26
- 负责人：Codex

## Summary

The current failure is not in Renderer, Figma plugin, or materializer execution. Latest artifact `task_530c596b4d40` shows social/login button text is editable, but the icon candidates inside media-contained controls stop before final M29.2 ownership:

```text
M29.6 candidate exists
-> transparent asset rejects or keeps analysis-only
-> evidence contract stays report_only/reject
-> internal source promotion does not write raster_icon back into M29.2
-> final M29.5 has no icon_replay for those controls
```

Bridge fate trace is the diagnostic index only. This plan must not add Google/Facebook/Snapchat, visible text, file name, task id, fixed coordinate, fixed bbox, theme color, or screenshot-specific behavior.

## Root Cause

The failed candidates already existed in M29.6. The source-chain break was that a single media-contained control row icon plus OCR label had no generic execution evidence unless it also had high alpha confidence or repeated group support.

The failing artifact showed this pattern:

```text
accepted internal icon candidate
+ directional OCR anchor
+ low text overlap
+ low hero/texture penalty
+ same media containment
-> transparent alpha rejects or remains analysis-only
-> evidence contract cannot allow visible replay
-> no M29.2 promoted raster_icon
-> no final M29.5 icon_replay
```

This is a source-chain evidence gap, not a Renderer, Figma plugin, materializer, bridge fate, brand, text, filename, color, or coordinate problem.

## Owning Layer

Fix the source-chain evidence contract:

```text
M29.6 media internal decomposition
-> M29 transparent asset replay eligibility
-> M29 evidence contract
-> M29 internal source promotion
-> final M29.5 replay plan
```

Do not patch:

```text
Renderer
Figma plugin
materializer direct node creation
bridge fate trace behavior rules
```

## Key Changes

1. Add generic single-control-row support in M29.6 for an internal icon candidate that is tightly related to an OCR label inside the same media/control region.
2. Treat this evidence as a relation contract, not a brand/text rule:
   - candidate is accepted;
   - candidate has directional OCR anchor;
   - text overlap is low;
   - hero penalty is low;
   - same-media containment is high;
   - geometry is icon-like relative to the label.
3. Let transparent asset report distinguish visible replay evidence from cleanup safety:
   - strong control-contained evidence can support visible replay;
   - alpha edge/background risk can still block copied-media cleanup later;
   - weak/unanchored foreground remains rejected.
4. Let evidence contract allow visible replay when strong control relation evidence replaces the missing repeated group evidence.
5. Let internal source promotion write only evidence-contract-approved candidates back into promoted M29.2 as `raster_icon / icon_replay`.
6. Keep copied-media cleanup stricter than visible replay:
   - source-crop fallback can create selectable icon replay;
   - cleanup stays blocked without a transparent replacement;
   - transparent-asset bbox padding overlap with nearby text is explainable only when the promoted candidate carries low `textOverlapRatio` evidence.

## Implementation Notes

Implemented without public contract changes:

- M29.6 now sets `controlRowSupportedExecution` for accepted internal icons with strong directional OCR relation, low text overlap, low hero risk, compact icon-like geometry, and scale-aware size bounds.
- Transparent asset report now carries `controlRowSupportedExecution` and can set `controlRowSourceCropEligible` when alpha generation is unsafe but control-row evidence supports visible replay.
- Evidence contract can allow visible replay when `transparent_visible_replay_eligible` is true because of source-crop control-row support.
- Internal source promotion preserves `matchedOcrBoxId` in promoted source evidence and uses the original candidate bbox when no transparent asset path exists.
- M29.5 overlap and ownership conservation accept promoted control-row/source-crop icons as visible replay evidence, but copied-image cleanup still requires a real transparent replacement.
- Bridge fate remains read-only and only reflects the new source-chain outcome.

## Validation

Targeted tests:

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py -q
```

Regression path:

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py tests/test_m29_bridge_fate_trace.py -q
```

Real artifact verification:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

For the diagnostic image, bridge fate should move relevant button icon candidates from `m29_transparent_assets:internal_candidate_not_execution_supported` or `generic_foreground_not_visible_replay` into final replay, unless alpha/cleanup risk prevents only cleanup.

Executed validation:

```bash
cd backend
python -m py_compile \
  app/media_internal_decomposition/candidates.py \
  app/transparent_asset_report/candidates.py \
  app/transparent_asset_report/normalization.py \
  app/transparent_asset_report/pipeline.py \
  app/transparent_asset_report/gates.py \
  app/m29_evidence_contract/scoring.py \
  app/internal_source_promotion/pipeline.py \
  app/m29_replay_plan/overlap.py \
  app/ownership_conservation/conflicts.py
```

Result:

```text
passed
```

```bash
cd backend
uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_m29_evidence_contract.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_ownership_conservation.py \
  -q
```

Result:

```text
109 passed
```

```bash
cd backend
uv run pytest \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  tests/test_m29_bridge_fate_trace.py \
  -q
```

Result:

```text
27 passed
```

Single diagnostic image validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir tmp/validation/064_single_input \
  --output-dir tmp/validation/064_single_run \
  --poll-timeout 300
```

Result:

```text
inputCount: 1
supportedCompletedTaskCount: 1
supportedFailedCount: 0
missingArtifactCount: 0
assetFetchFailedCount: 0
totalVisibleOwnershipOverlapConflicts: 0
totalPromotedInternalSourceObjectCount: 11
```

The three target media-contained button icons moved to final replay:

```text
[176,1059,48,42] -> visible_replay_materialized -> m29_symbol_0019
[156,1181,69,72] -> visible_replay_materialized -> m29_symbol_0018
[155,1329,69,71] -> visible_replay_materialized -> m29_symbol_0017
```

525 real-sample validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --output-dir tmp/validation/064_525_run_2 \
  --poll-timeout 300
```

Result:

```text
inputCount: 6
supportedCompletedTaskCount: 6
supportedFailedCount: 0
missingArtifactCount: 0
assetFetchFailedCount: 0
totalVisibleReplayClaimCount: 426
totalVisibleOwnershipOverlapConflicts: 0
totalPromotedInternalSourceObjectCount: 66
totalBStageRepairCost: 36
ownershipConflictTypeCounts: {}
```

## Acceptance Criteria

- Bridge fate trace still remains read-only diagnostic infrastructure.
- No public DSL/API/Renderer/plugin protocol changes.
- No sample-specific labels, brands, filenames, task ids, fixed bboxes, fixed coordinates, or theme-color rules.
- Media-contained login/social-style control icons can become promoted `raster_icon` source objects through M29.2 and final M29.5.
- Unanchored texture fragments and hero graphics remain blocked.
- Cleanup remains authorized only by final M29.5.

## Anti-Specialization Check

No production rule was added for:

```text
Google / Facebook / Snapchat
visible label text
file names
task ids
fixed bboxes
fixed coordinates
theme colors
single screenshot structure
```

New logic is based on generic evidence:

```text
directional OCR relation
text overlap
hero/texture penalty
compactness
scale-aware icon geometry
same-media containment
transparent visible replay eligibility
M29.5 cleanup risk
ownership conservation
```
