# 07 Ownership Conservation

## Source Truth

Ownership conservation consumes:

```text
M29.2 source ownership
M29.3 relation graph
M29.5 replay plan
```

Primary package:

```text
backend/app/ownership_conservation/
```

Runtime entrypoint:

```text
backend/app/ownership_conservation/pipeline.py:17
```

First-principles role:

```text
This layer audits whether accepted visible replay and cleanup claims are mutually explainable.
It does not fix source ownership.
It does not change M29.5 plan.
It does not materialize or erase pixels.
```

## Input Artifacts

```text
m29_2/source_ui_physical_graph.json
m29_3/region_relation_graph_report.json
m29_5/replay_plan.json
```

Code evidence:

```text
backend/app/ownership_conservation/pipeline.py:26-40
```

## Output Artifacts

Primary output:

```text
m29_ownership_conservation/ownership_conservation_report.json
```

Fields:

```text
sourceObjectClaims
visibleReplayClaims
cleanupClaims
conflicts
summary
warnings
```

Code evidence:

```text
backend/app/ownership_conservation/pipeline.py:41-75
```

## Decision Authority

### This layer can decide

Ownership conservation can decide:

```text
visible replay claim count
cleanup claim count
visible ownership overlap conflicts
missing copied image cleanup warnings
invalid cleanup claim errors
non-visible action visible-role errors
whether overlaps are explainable by source relation/cleanup/provenance
```

### This layer must not decide

It must not decide:

```text
new source objects
finalReplayAction
cleanupTargets
asset alpha
promotion
DSL nodes
Figma output
```

Current code is report-only:

```text
meta.reportOnly = true
materializationChanged = false
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
```

Code evidence:

```text
backend/app/ownership_conservation/pipeline.py:63-71
```

## Main Formulas And Gates

### Claims

Source object claims mirror M29.2:

```text
sourceObjectId
bbox
visualKind
pixelOwner
replayDecision
confidence
```

Visible replay claims are M29.5 plan items whose action is visible:

```text
text_replay
image_replay
icon_replay
shape_replay
```

Cleanup claims are copied from M29.5 `cleanupTargets`:

```text
fallback
copied_image_asset
authorizedBy = m29_5_cleanupTargets
```

Code evidence:

```text
backend/app/ownership_conservation/claims.py:8-63
```

### Conflict detectors

The report runs:

```text
detect_non_visible_claims
detect_visible_overlap_conflicts
detect_missing_copied_cleanup
detect_invalid_cleanup_claims
```

Code evidence:

```text
backend/app/ownership_conservation/conflicts.py:12-27
```

### Visible overlap

Visible claims that overlap above threshold become warnings unless explainable:

```text
overlapRatio >= 0.20
or near_equal relation
then require overlap_is_explainable
```

Code evidence:

```text
backend/app/ownership_conservation/conflicts.py:50-74
```

Explainable overlap includes:

```text
shape under text/icon/image
promoted internal icon over parent image with transparent asset
label-anchored blocked icon with copied cleanup
text inside image with copied cleanup
promoted internal icon + text overlap when both clean same media and textOverlapRatio <= 0.14
```

Code evidence:

```text
backend/app/ownership_conservation/conflicts.py:225-271
```

### Cleanup validity

Copied image cleanup is valid only when:

```text
target source object exists
target is preserve_raster / image_replay
and one of:
  editable text containment
  promoted internal icon containment with transparentAssetPath
  label-anchored blocked icon containment
  shape background containment
```

Code evidence:

```text
backend/app/ownership_conservation/conflicts.py:111-158
backend/app/ownership_conservation/conflicts.py:161-222
```

This is the correct downstream audit of the M29.5 cleanup contract.

## Information Loss

### Loss 1: This layer reports, but cannot repair

If the report finds missing cleanup:

```text
materializer will still consume the M29.5 plan it was given.
```

This is useful for batch ledger and debugging, but it is not a runtime guard that blocks bad output.

### Loss 2: No pixel-level mask ownership

The report reasons by bbox and relation edges, not actual alpha masks:

```text
it can say overlap is explainable,
but not whether the alpha cleanup erased the exact pixels cleanly.
```

Pixel-level verification belongs to materializer output inspection and visual comparison.

### Loss 3: It relies on promotion evidence shape

For promoted internal icons, explainability requires:

```text
promotionSource = m29_6_internal_icon_candidate
mediaSourceObjectId
transparentAssetPath
textOverlapRatio <= threshold for icon/text overlap
```

If promotion omits those fields, ownership conservation cannot explain the overlap.

## Known Failure Symptoms Mapped To This Layer

### Double shadow / duplicated text/icon

If M29.5 misses copied image cleanup, this report should warn:

```text
missing_copied_image_asset_cleanup
```

If it does not warn, check whether relation edges are missing or the object never became a visible claim.

### Icon overlay over media reported as conflict

If icon is promoted but lacks `transparentAssetPath` or parent media evidence, the overlap is not explainable. The owner is promotion/evidence contract, not ownership conservation.

## Tests / Guards

Direct tests:

```text
backend/tests/test_ownership_conservation.py
```

Important guards from bug records:

```text
promoted internal icon low label overlap is explainable when both cleanup same media
promoted internal icon high label overlap is still reported
invalid cleanup claims become errors
```

Related code:

```text
backend/app/ownership_conservation/conflicts.py:258-271
```

## Findings

### P1: Ownership conservation is a report, not an enforcement gate

Evidence:

```text
backend/app/ownership_conservation/pipeline.py:63-71
```

Judgment:

```text
This is architecturally safe, but it means visual badness can still pass upload if upstream plan/materializer produced it. Batch validation must inspect the report.
```

Recommended next action:

```text
Keep it report-only, but make real-sample acceptance read conflictCount/errorCount.
```

### P2: Promoted internal icon overlap depends on the promotion contract

Evidence:

```text
backend/app/ownership_conservation/conflicts.py:229-271
```

Judgment:

```text
This is the right dependency. Promotion must carry mediaSourceObjectId, transparentAssetPath, and textOverlapRatio.
```

Recommended next action:

```text
Audit internal_source_promotion fields and M29.5 propagation.
```

### P2: Bbox-level conservation is not enough for cleanup quality

Evidence:

```text
ownership conservation uses bbox overlap/relation, not alpha masks.
```

Judgment:

```text
It can prove permission consistency, not visual cleanup quality.
```

Recommended next action:

```text
Use materializer report and DSL visual comparison for pixel-output verification.
```

## Recommended Next Action

Continue to M29.6 media internal decomposition:

```text
This is the current recovery layer for media-contained icons and likely the missing abstraction for media-contained controls.
```
