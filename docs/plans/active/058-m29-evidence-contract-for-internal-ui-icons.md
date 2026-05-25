# 058 M29 Evidence Contract For Internal UI Icons

- 状态：active
- 创建日期：2026-05-26
- 负责人：Codex

## Goal

为 composite media 内部 UI icon 建立一个窄版、可审计的 M29 evidence contract。目标不是再调一个局部 confidence 阈值，而是在 M29.6、transparent asset、M29.2 ownership、M29.5 cleanup 之间增加一个明确裁决层：

```text
evidence consistency gate
+ ownership / cleanup risk gate
+ later render-back validation gate
```

第一版只覆盖 internal UI icon / media-contained foreground asset：

```text
M29.6 internal icon candidate
+ transparent asset alpha gate
+ parent media containment
+ text-anchor / repeated structure evidence
+ negative evidence / cleanup risk
=> allow_visible_replay | report_only | reject
```

通过合同的 M29.6 candidate 才能被 `internal_source_promotion` 提升为 promoted M29.2 source object。合同本身保持 report-only，不创建 DSL、资产替换、visible nodes 或 cleanup 权限。

## First-Principles Contract

Real goal:

```text
底部 tab、快捷入口、轮播 action row 这类 internal UI icon 应该能成为独立 Figma image/icon layer；
同时父 copied media 中对应区域只有在 M29.5 授权后才能 cleanup，避免双影和破洞。
```

Source truth:

```text
source PNG pixels
raw M29 primitive / blocked / pixel foreground evidence
OCR bbox anchors
M29.2 source ownership
M29.3 relation graph
M29.5 replay and cleanup plan
transparent asset alpha analysis
post-materialization visual comparison
```

Information-loss point:

```text
local candidate reports already contain partial truth, but promotion currently consumes local confidence/alpha gates directly.
There is no explicit cross-evidence contract that says why a diagnostic/report candidate may become source ownership.
```

Owning layer:

```text
evidence contract report: cross-evidence proof and decision
internal source promotion: only bridge from allowed contract into promoted M29.2
M29.5 replay plan: only visible replay / cleanup authorization source
materializer: plan consumer only
```

Do not do:

```text
do not patch materializer, Renderer, or plugin to invent icons or cleanup
do not use literal tab labels, filenames, sample ids, fixed y coordinates, fixed bboxes, brand, theme, or app-specific rules
do not make M29.6 or transparent asset report directly authorize materialization
do not add Pillow/OpenCV/SAM/ONNX/runtime dependencies
do not change DSL/API/plugin protocol
```

## Evidence Formula

第一版公式：

```text
IconEvidenceScore(c, M, T, G) =
  a * FragmentForegroundScore(c)
+ b * SizeCompactnessScore(c)
+ c * TextAnchorScore(c, T)
+ d * SameMediaContainmentScore(c, M)
+ e * RepetitionScore(G)
+ f * RelationConsistencyScore(c, M)
+ g * TransparentAssetScore(c)
- h * TextOverlapPenalty(c, T)
- i * TextureHeroPenalty(c)
- j * CleanupRisk(c, M)
- k * RepairCostPenalty(c)
```

决策：

```text
if EvidenceScore >= tau_visible
and transparent asset is allow
and parent media source exists
and text overlap / hero risk / cleanup risk are low:
  allow_visible_replay

elif candidate has partial evidence but execution support or alpha safety is incomplete:
  report_only

else:
  reject
```

第一版 render-back gate 只记录为后续阶段，因为 `dsl_visual_comparison` 在 materialization 后才有数据。当前阶段不把 render-back 做成前置阻断。

## Scope

Allowed:

- `backend/app/m29_evidence_contract/`
- `backend/app/upload_preview/paths.py`
- `backend/app/upload_preview/stages.py`
- `backend/app/upload_preview/pipeline.py`
- `backend/app/internal_source_promotion/`
- focused backend tests
- docs / bug / regression matrix updates

Forbidden without explicit migration proposal:

- DSL schema changes
- public API response changes
- Renderer or Figma plugin changes
- Figma Auto Layout / Component / Instance / Variant / Vector materialization
- new runtime dependencies

Forbidden always:

- text literal, filename, path, task id, sample id, fixed coordinate, fixed bbox, fixed screen size, brand, theme, industry, or one-screenshot rules
- cleanup outside M29.5 `cleanupTargets`
- materializer owner inference

## Steps

1. Add `M29EvidenceContractReport` as a report-only artifact after transparent assets and before internal source promotion.
2. Score M29.6 internal icon candidates using decomposed positive evidence, negative evidence, risk, and transparent asset output.
3. Make `internal_source_promotion` require `allow_visible_replay` from the evidence contract instead of directly trusting local confidence plus alpha allow.
4. Record contract id, decision, and score in promoted source evidence.
5. Keep M29.2 label-anchored blocked icon recovery as source ownership evidence, but expose matching evidence contract items for audit rather than moving the decision downstream.
6. Update upload-preview stage timing and artifact tests.
7. Add focused tests for allow/report-only/reject decisions, promotion consumption, and pipeline artifact presence.

## Acceptance

- `m29_evidence_contract/evidence_contract_report.json` is produced in upload-preview production profile.
- Report declares `reportOnly=true`, `dslChanged=false`, `assetChanged=false`, `materializationChanged=false`, `createdVisibleNodeCount=0`.
- `internal_source_promotion` promotes M29.6 internal icons only when the matching evidence contract decision is `allow_visible_replay`.
- Transparent asset reject, high text overlap, hero/texture risk, missing parent media, or missing execution support cannot promote.
- Contract items include decomposed `positiveEvidence`, `negativeEvidence`, `risk`, and `decision`; not just one confidence number.
- No code uses filenames, paths, visible text literals, task ids, fixed coordinates, fixed bboxes, brands, themes, or one-screenshot structure rules.
- Materializer remains a consumer of M29.5 plan only.

## Validation

Targeted:

```bash
cd backend
uv run pytest tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_upload_preview_pipeline.py -q
```

Core affected regression:

```bash
cd backend
uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  tests/test_ownership_conservation.py \
  tests/test_source_ui_physical_graph.py \
  -q
```

Finish:

```bash
git diff --check
git status --short --branch
```

## Notes

Bug 012 is the motivating failure, but this plan must stay generic. Single-sample improvement is only diagnosis; acceptance is the contract, tests, and unchanged M29 boundary behavior.
