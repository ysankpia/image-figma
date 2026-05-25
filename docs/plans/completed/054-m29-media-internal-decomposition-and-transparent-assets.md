# M29.6 Media Internal Decomposition And Transparent Assets

- 状态：completed
- 创建日期：2026-05-25
- 负责人：Codex

## Goal

修复复合 `preserve_raster` media 吞掉内部普通 UI foreground 的通用能力缺口。目标不是为某张图、某个轮播、某些中文文案、某个行业或固定 bbox 写补丁，而是补齐一条 source-truth 链路：

```text
preserve_raster media
-> internal OCR/raw foreground evidence
-> M29.6 report-only decomposition
-> transparent asset candidate report
-> execution-supported source promotion experiment
-> M29.5 replay/cleanup authorization
-> materializer consumes only M29.5-authorized internal assets
```

这个计划覆盖用户指定的 Phase 1-7，同时把 C0-C6 后续阶段记录到同一个执行文档中，避免后续实现漂到 materializer/plugin/Renderer 特化。

## First-Principles Boundary

源事实只来自：

```text
source PNG pixels
OCR boxes
raw M29 primitive graph
M29.2 source objects
M29.3.1 relation graph
M29.5 replay plan
existing report artifacts
```

禁止使用：

```text
file name
task id
literal text such as specific labels
industry or app category
theme/color special case
fixed bbox
single-sample hand-tuned rule
Renderer/plugin/materializer guesswork
```

任何 visible owner、cleanup 或 materialization 行为必须继续由 source ownership、relation 和 M29.5 plan 授权。M29.6 第一版只能报告候选，不能直接改变 DSL、asset、replay plan 或 materialization。

## Problem Statement

当前 M29.2 的保守规则：

```text
large complex image-like region
-> media_region
-> preserve_raster
-> image_replay
```

能保住复杂视觉，但会把复合媒体内部的普通 UI foreground 吞掉，例如：

```text
internal icon above or near OCR label
bottom navigation icon inside raster nav bar
card/table internal small marker or circle
thin internal separator
small visual asset that should become transparent PNG later
```

这些不是 UI 语义分类失败，而是 source object promotion 缺口：raw M29 可能已经有 symbol/shape/unknown 证据，但 M29.2 没有把它提升成可见或候选 source object，因为它被更大的 `preserve_raster` media 包住。

## Mathematical Contract Summary

完整公式写入：

- [M29 之后 Codia 级数学合同，第 1A 章](../../architecture/m29-to-codia-math-contract-v0.1.md)
- [M29 当前数学合同，当前薄弱点与下一步](../../architecture/m29-experimental-mathematical-contract.md)

核心公式：

```text
CompositeMedia(M) iff
  pixelOwner(M) = preserve_raster
  and replayDecision(M) = image_replay
  and (
    count(TextInside(M)) >= 1
    or count(RawInside(M)) >= 2
    or "contains_internal_text" in risks(M)
  )
```

文字保护：

```text
TextMask_M(p) = 1
iff exists t in TextInside(M), p in expand(B(t), px, py)
```

局部背景：

```text
bg_M(p) =
  median({P(q) | q in Window(p,R), q not in TextMask_M, q not high_contrast})
```

相对前景：

```text
ForegroundScore_M(p) =
  a * ColorDiff(p)
+ b * SaturationDiff(p)
+ c * LocalContrast(p)
+ d * EdgeStrength(p)
- e * BackgroundTexturePenalty(p)
```

内部候选：

```text
C_M = connected_components(FG_M)
```

图标候选评分：

```text
IconScore(c,M) =
  a * SizeScore(c)
+ b * CompactnessScore(c)
+ c * ColorCoherenceScore(c)
+ d * TextAnchorScore(c, TextInside(M))
+ e * RepetitionScore(c, C_M)
+ f * LocalControlRegionScore(c)
- g * TextOverlapPenalty(c)
- h * HeroGraphicPenalty(c,M)
- i * TextureFragmentPenalty(c)
```

透明资产：

```text
Out(p) = [R(p), G(p), B(p), Alpha(p)]
```

其中 `Alpha(p)` 来自前景分数或 component mask。工程上这是 `bbox crop + alpha mask`，不是方形视觉抠图，也不是通用 remove-background。

## Phase Plan

### Phase 1: Math Contract And Active Plan

补齐数学合同和 active plan。

Acceptance:

```text
M29.6 formula exists
transparent asset formula exists
C0-C6 recorded
Phase 1-7 recorded
no runtime code changes
no sample-specific language in rules
```

### Phase 2: M29.6 Report-Only

新增 `backend/app/media_internal_decomposition/` 或等价 focused package。

Inputs:

```text
source PNG
OCR
raw M29 nodes
M29.2 source objects
M29.3.1 relation graph
M29.5 replay plan
```

Output:

```text
storage/upload_previews/{taskId}/m29_media_internal_decomposition/media_internal_decomposition_report.json
```

Required invariants:

```text
schemaName = M29MediaInternalDecompositionReport
schemaVersion = 0.1
reportOnly = true
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
blockingUpload = false
```

Initial report fields:

```text
summary
compositeMediaItems
textMasks
internalCandidates
matchedInternalGroups
rejectedFragments
warnings
meta
```

### Phase 3: Batch Validation On `/Users/luhui/Downloads/m29`

Run every image in `/Users/luhui/Downloads/m29`, not a single sample.

Acceptance:

```text
all upload-preview tasks complete
M29.6 report artifact present for every image
false-positive ledger records candidate counts and rejection reasons
no blocking upload caused by M29.6
no sample-specific rules introduced
```

The latest uploaded task may be used as evidence, but must not become a hardcoded test rule.

### Phase 4: Transparent Asset Extraction Report-Only

Add transparent asset candidate report. It may generate debug RGBA PNG files, but must not replace materialized assets yet.

Output:

```text
storage/upload_previews/{taskId}/m29_transparent_assets/transparent_asset_report.json
```

Required invariants:

```text
reportOnly = true
dslChanged = false
assetChanged = false
materializerConsumesAssets = false
```

Allowed candidate sources:

```text
existing raster_icon source objects
execution-supported M29.6 internal_icon_candidate
```

Not allowed:

```text
all media images
photos/person/product general segmentation
text-overlapping components
unstable backgrounds
```

### Phase 5: Execution-Supported Internal Source Promotion Experiment

Only accepted internal candidates with transparent asset allow may become experimental source objects. Medium confidence candidates require explicit structural support; confidence alone is not the only execution gate.

Expected rule:

```text
PromoteInternalSource(c,M) iff
  M29.6 accepted(c)
  and transparentAssetAllowed(c)
  and (
    M29.6 confidence(c) = high
    or groupSupportedExecution(c) = true
  )
  and textMaskOverlap(c) <= threshold
  and heroGraphicPenalty(c) <= threshold
  and repeatedItem or strong local icon evidence exists
  and ownership conservation can explain the claim
```

This phase must stay upstream of materializer:

```text
raw M29 / M29.2 source ownership layer
```

It must not be implemented as Renderer/plugin/materializer patching.

### Phase 6: M29.5 Replay/Cleanup Authorization

M29.5 must explicitly authorize:

```text
internal icon replay
transparent asset consumption
copied media cleanup target
fallback cleanup target
suppression of duplicates
```

No cleanup can be inferred from M29.6 alone.

### Phase 7: Materializer Consumes M29.5-Authorized Results

Only consume M29.5-authorized internal assets.

Allowed:

```text
create visible internal icon/image node from authorized plan item
use transparent PNG asset if allow decision exists
erase copied media asset only if M29.5 cleanup target exists
```

Not allowed:

```text
reclassify owner
invent icon from bbox
create Auto Layout/Component/Variant/Vector
clean copied media asset without authorization
```

## C-Stage Program

This plan records the broader C-stage roadmap so implementation order remains clear.

### C0: Quality Benchmark / Repair-Cost Calibration

Calibrate B/C-stage quality report and visual diff against actual repair cost. Do not optimize only for candidate count.

### C1: Hierarchy + Sibling Group Confidence Calibration

Use batch artifacts to calibrate high-confidence structure groups. This does not create new source owners.

### C2: Auto Layout Permission Calibration

Tune Auto Layout permission thresholds. Permission remains report-only until a later controlled materialization phase.

### C3: Component Isomorphism Report-Only

Add report-only component family/isomorphism candidates. No Figma Component/Instance.

### C4: Variant Report-Only

Add report-only variant axis candidates after component family evidence exists. No variant materialization.

### C5: Vectorization Report-Only / Opt-In

Add report-only or explicit opt-in vectorization. No automatic vector replacement for complex texture or unknown media.

### C6: Controlled Materialization Experiment

Continue controlled materialization only after source owner, relation, quality, and permission reports explain the change. Existing C6-lite transparent groups are allowed precedent; internal asset materialization requires M29.5 authorization.

## Test Plan

Phase 2 expected tests:

```text
backend/tests/test_media_internal_decomposition.py
backend/tests/test_upload_preview_pipeline.py
```

Cases:

```text
composite media with internal OCR text is reported
text mask prevents glyphs from becoming internal icon candidates
raw symbols inside media can become report-only internal candidates
large hero/texture fragments are rejected
repeated icon-label row is grouped by geometry, not literal text
bottom-nav-like repeated labels/icons are handled by same generic rules
table/card internal small markers are reported or rejected with reasons
report remains dslChanged=false and assetChanged=false
upload-preview includes stage timing and artifact
```

Phase 4 expected tests:

```text
stable solid-background icon produces transparent asset candidate
unstable gradient/photo background is rejected
text overlap is rejected
report-only invariant holds
materializer consumes transparent asset only after internal source promotion and final M29.5 icon_replay authorization
```

Batch validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
```

## Documentation Updates Required Per Phase

Every implementation phase must update:

```text
docs/architecture/backend.md
docs/engineering/current-mainline-code-map.md
docs/engineering/m29-contract-regression-matrix.md
docs/engineering/testing-strategy.md if validation surface changes
docs/plans/active/054-m29-media-internal-decomposition-and-transparent-assets.md
```

When completed, move this file to:

```text
docs/plans/completed/054-m29-media-internal-decomposition-and-transparent-assets.md
```

and update:

```text
docs/plans/completed/index.md
docs/index.md
```

## Current Status

Phase 1 is complete. Phase 2 report-only implementation is complete. Phase 3 batch validation is complete. Phase 4 transparent asset report-only implementation is complete. Phase 5-7 implementation is complete, with final validation recorded in plan 055.

Completed in Phase 1:

```text
M29-to-Codia math contract gained Media Internal Pixel Decomposition formulas.
M29 current math contract records M29.6 and transparent asset extraction as report-only next steps.
This plan records Phase 1-7 and C0-C6.
```

Completed in Phase 2:

```text
backend/app/media_internal_decomposition/ added.
upload-preview now runs m29_media_internal_decomposition after ownership conservation and before hierarchy candidates.
report output path:
  storage/upload_previews/{taskId}/m29_media_internal_decomposition/media_internal_decomposition_report.json
report schema:
  M29MediaInternalDecompositionReport 0.1
report-only invariants enforced:
  reportOnly=true
  dslChanged=false
  assetChanged=false
  createdVisibleNodeCount=0
  materializationChanged=false
  blockingUpload=false
```

Implemented Phase 2 tests:

```text
backend/tests/test_media_internal_decomposition.py
backend/tests/test_upload_preview_pipeline.py
```

Validation run:

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py -q
uv run pytest tests/test_upload_preview_pipeline.py -q
```

Completed in Phase 3:

```text
/Users/luhui/Downloads/m29 batch validation ran across every PNG.
15/15 upload-preview tasks completed.
M29.6 report artifact existed for every task.
No ownership conflicts were produced.
Batch ledger recorded composite media, internal candidates, rejected fragments, matched groups, and visual comparison metrics.
```

Phase 3 validation ledger:

```text
backend/tmp/validation/upload_preview_batch_20260525_153841/upload_preview_batch_validation.json
```

Completed in Phase 4:

```text
backend/app/transparent_asset_report/ added.
upload-preview now runs m29_transparent_assets after M29.6 and before hierarchy candidates.
report output path:
  storage/upload_previews/{taskId}/m29_transparent_assets/transparent_asset_report.json
report schema:
  M29TransparentAssetReport 0.1
candidate sources are limited to:
  existing raster_icon/icon_replay source objects
  execution-supported M29.6 internal_icon_candidate items
report-only invariants enforced:
  reportOnly=true
  dslChanged=false
  assetChanged=false
  createdVisibleNodeCount=0
  materializationChanged=false
  materializerConsumesAssets=false
  blockingUpload=false
```

Implemented Phase 4 tests:

```text
backend/tests/test_transparent_asset_report.py
backend/tests/test_upload_preview_pipeline.py
```

Validation run:

```bash
cd backend
uv run pytest tests/test_transparent_asset_report.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py -q
```

Completed in Phase 5-7:

```text
backend/app/internal_source_promotion/ added.
upload-preview now runs m29_internal_source_promotion after transparent assets.
promotion output paths:
  storage/upload_previews/{taskId}/m29_internal_source_promotion/internal_source_promotion_report.json
  storage/upload_previews/{taskId}/m29_internal_source_promotion/source_ui_physical_graph.promoted.json
promotion is limited to:
  high confidence or structurally supported medium M29.6 internal_icon_candidate
  transparent asset allow
  existing parent media source object
pipeline reruns final M29.3/M29.4/M29.5/ownership from promoted M29.2 before hierarchy/materialization.
M29.5 keeps promoted internal icon overlay over its parent media only when sourceEvidence links the icon to that media and transparent asset.
M29.5 authorizes copied media cleanup for promoted internal icons only when source evidence and relation graph explain containment.
materializer consumes transparent asset and alpha-mask copied media cleanup only after final M29.5 authorizes icon_replay and cleanup.
```

Implemented Phase 5-7 tests:

```text
backend/tests/test_internal_source_promotion.py
backend/tests/test_m29_replay_plan.py
backend/tests/test_m29_plan_materializer.py
backend/tests/test_upload_preview_pipeline.py
```

Validation run:

```bash
cd backend
uv run pytest tests/test_internal_source_promotion.py tests/test_transparent_asset_report.py tests/test_m29_replay_plan.py::test_m295_keeps_promoted_internal_icon_over_parent_media tests/test_upload_preview_pipeline.py -q
uv run pytest tests/test_internal_source_promotion.py tests/test_transparent_asset_report.py tests/test_media_internal_decomposition.py tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
```

Phase 2-7 still do not:

```text
authorize copied media cleanup for internal icons
erase internal icons from copied parent media
create Auto Layout/Component/Variant/Vector
use literal text/file/theme/fixed-bbox rules
```
