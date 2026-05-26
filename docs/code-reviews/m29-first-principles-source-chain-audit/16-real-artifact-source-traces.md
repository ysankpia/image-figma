# 16 Real Artifact Source Traces

## Artifact

Trace source:

```text
backend/storage/upload_previews/task_33428579a6f7
```

This artifact is useful because it shows the key user-visible symptom:

```text
text can be selected/edited
some adjacent icon/button evidence exists in reports
final DSL does not expose those objects as selectable visible nodes
```

This report uses existing local artifacts only. No upload rerun was performed.

## Artifact Summary

Final materialization summary:

```text
replayedTextCount = 9
replayedImageCount = 4
replayedSymbolCount = 4
replayedShapeCount = 1
visibleNodeCount = 18
controlledStructureGroupCount = 0
copiedImageAssetTextErasedCount = 5
copiedImageAssetInternalErasedCount = 0
skippedReasons = { diagnostic_only: 93, suppress_duplicate: 1 }
```

Final M29.2 summary inside materialization report:

```text
sourceObjectCount = 112
editableTextCount = 9
rasterIconCount = 4
mediaRegionCount = 5
shapeGeometryCount = 1
diagnosticOnlyCount = 93
promotedInternalSourceObjectCount = 0
```

Final M29.5 summary:

```text
plannedVisibleNodeCount = 18
plannedTextReplayCount = 9
plannedImageReplayCount = 4
plannedIconReplayCount = 4
plannedShapeReplayCount = 1
diagnostic_only = 93
```

Artifact evidence:

```text
backend/storage/upload_previews/task_33428579a6f7/materialized_design/materialization_report.json
```

## Trace A: Detected Internal Candidates That Never Become Icons

M29.6 found two internal icon candidates around the same OCR anchor:

```json
{
  "candidateId": "m292_object_0010:internal_candidate_0030",
  "bbox": [176, 1059, 48, 42],
  "rawSubtype": "left_of_text",
  "role": "internal_icon_candidate",
  "candidateDecision": "accepted_report_candidate",
  "confidence": "medium",
  "score": 0.64,
  "textAnchorScore": 0.883,
  "heroGraphicPenalty": 0.0,
  "textMaskOverlap": 0.0,
  "reasons": ["ocr_anchor_foreground_component", "local_pixel_foreground"]
}
```

```json
{
  "candidateId": "m292_object_0010:internal_candidate_0031",
  "bbox": [176, 1031, 37, 22],
  "rawSubtype": "left_of_text",
  "role": "internal_icon_candidate",
  "candidateDecision": "accepted_report_candidate",
  "confidence": "medium",
  "score": 0.59,
  "textAnchorScore": 0.735,
  "heroGraphicPenalty": 0.0,
  "textMaskOverlap": 0.0,
  "reasons": ["ocr_anchor_foreground_component", "local_pixel_foreground"]
}
```

Fact:

```text
The source evidence exists before transparent asset extraction.
This is not a raw M29 total miss.
```

## Trace B: Transparent Asset Gate Rejects Before Alpha Analysis

Transparent asset report contains corresponding items:

```json
{
  "source": "m29_6_internal_icon_candidate",
  "sourceObjectId": "m292_object_0010:internal_candidate_0030",
  "bbox": [176, 1059, 48, 42],
  "decision": "reject",
  "assetPath": null,
  "inputConfidence": "medium",
  "inputScore": 0.64,
  "reasons": [
    "m29_6_internal_icon_candidate",
    "internal_candidate_not_execution_supported"
  ],
  "risks": [
    "internal_candidate_not_execution_supported",
    "transparent_asset_rejected"
  ]
}
```

Second candidate has the same rejection:

```text
internal_candidate_not_execution_supported
assetPath = null
```

Transparent report summary:

```text
candidateCount = 150
allowedCount = 6
rejectedCount = 144
sourceCounts.m29_6_internal_icon_candidate = 146
rejectionReasonCounts.internal_candidate_not_execution_supported = 89
```

Fact:

```text
The immediate gate is transparent asset preflight, not final materialization.
```

## Trace C: Evidence Contract Has No Allow Visible Replay

Evidence contract summary:

```text
internalCandidateCount = 164
transparentItemCount = 150
contractItemCount = 146
allowVisibleReplayCount = 0
reportOnlyCount = 16
rejectCount = 130
```

Fact:

```text
No internal icon candidate reaches allow_visible_replay in this artifact.
```

Inference:

```text
Because transparent asset rejection removes assetPath/transparentAllowed evidence,
promotion cannot produce new M29.2 source objects.
```

## Trace D: Promotion Rejects With Missing Transparent Asset Path

Promotion summary:

```text
baseSourceObjectCount = 112
promotedSourceObjectCount = 0
finalSourceObjectCount = 112
rejectedCandidateCount = 146
sourceOwnershipChanged = false
```

For the same candidates:

```json
{
  "candidateId": "m292_object_0010:internal_candidate_0030",
  "reason": "missing_transparent_asset_path",
  "bbox": [176, 1059, 48, 42]
}
```

```json
{
  "candidateId": "m292_object_0010:internal_candidate_0031",
  "reason": "missing_transparent_asset_path",
  "bbox": [176, 1031, 37, 22]
}
```

Fact:

```text
The M29.2 promoted document contains zero promoted internal source objects.
```

## Trace E: Final Materializer Has Nothing To Replay

Materialization report has no replayed node with:

```text
m292_object_0010:internal_candidate_0030
m292_object_0010:internal_candidate_0031
```

Final visible nodes remain:

```text
9 text
4 image
4 symbol
1 shape
```

Fact:

```text
The final output cannot select these internal icons because the promoted source objects do not exist.
```

## Trace Conclusion

Root chain:

```text
M29.6 detects medium OCR-anchored internal icon candidates
-> transparent asset preflight rejects them as internal_candidate_not_execution_supported
-> no transparent assetPath
-> evidence contract has no allow_visible_replay
-> internal source promotion rejects missing_transparent_asset_path
-> final M29.2 has no promoted object
-> final M29.5 has no icon_replay item
-> materializer cannot create selectable icon
```

This is a P1 source-chain bridge defect.

It is not a Renderer or Figma plugin defect.

## Adjacent Artifact Lessons

### Bottom tab / selected marker

The artifact has 93 diagnostic-only items. Current M29.2 deliberately treats selected tab indicators as not icons. That is reasonable, but there is no positive `selected_marker` replay contract.

Inference:

```text
bottom tab state markers need a role path, not an icon hack.
```

### Button/control background

Materialization shows only one shape replay. If a visible control background remains inside a media raster, controlled structure grouping cannot create a button because the background member does not exist.

Inference:

```text
media-contained button/control backgrounds need an internal control-background evidence and promotion path.
```

### Cleanup

`copiedImageAssetInternalErasedCount = 0` because no internal asset was promoted and replayed. This is correct: cleanup must not erase pixels without replacement.

## Recommended Next Action

Fix the bridge, not the output layer:

```text
1. Add a general execution-support path for medium but strongly anchored internal candidates.
2. Keep alpha/cleanup risk checks independent and explicit.
3. Add source-chain trace fields so transparent/evidence/promotion rejection is visible in one report.
4. Add separate role contracts for selected markers, table markers, and internal control backgrounds.
```
