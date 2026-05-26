# 09 Transparent Asset Report

## Source Truth

Transparent asset report consumes:

```text
source PNG pixels
OCR boxes
M29.2 source objects
M29.6 internal candidates
```

Primary package:

```text
backend/app/transparent_asset_report/
```

Runtime entrypoint:

```text
backend/app/transparent_asset_report/pipeline.py:17
```

First-principles role:

```text
This layer tests whether an already-recognized icon-like source/candidate can be represented as a transparent RGBA asset.
It may write diagnostic PNG assets.
It does not authorize materialization or cleanup by itself.
```

## Input Artifacts

```text
original PNG
ocr/ocr.json
m29_2/source_ui_physical_graph.json
m29_media_internal_decomposition/media_internal_decomposition_report.json
```

Code evidence:

```text
backend/app/transparent_asset_report/pipeline.py:34-45
```

## Output Artifacts

Primary output:

```text
m29_transparent_assets/transparent_asset_report.json
```

Diagnostic assets:

```text
m29_transparent_assets/assets/transparent/*.png
```

Item fields:

```text
candidateId
source
sourceObjectId
mediaSourceObjectId
bbox
analysisBbox
decision
assetPath
backgroundRgb
bgVariance
foregroundAreaRatio
alphaCoverage
largestComponentRatio
edgeAlphaMean
edgeAlphaCoverageGt32
alphaProfile
reasons
risks
```

Code evidence:

```text
backend/app/transparent_asset_report/pipeline.py:74-113
```

## Decision Authority

### This layer can decide

Transparent asset report can decide:

```text
candidateAllowedForAlpha preflight
alphaProfile
allow/reject transparent debug asset
assetPath for allowed diagnostic asset
background stability
foreground/alpha/largest-component/edge-alpha metrics
```

### This layer must not decide

It must not decide:

```text
source ownership promotion
visible replay
cleanup target
materializer asset replacement by itself
DSL nodes
Figma output
```

Validation enforces:

```text
reportOnly = true
materializerConsumesAssets = false
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
```

Code evidence:

```text
backend/app/transparent_asset_report/types.py:8-17
backend/app/transparent_asset_report/validation.py:6-33
```

## Main Formulas And Gates

### Candidate sources

Transparent candidates come from:

```text
M29.2 raster_icon source objects
M29.6 internal_icon_candidate items
```

Code evidence:

```text
backend/app/transparent_asset_report/candidates.py:19-34
```

This is a key limitation:

```text
shape/control backgrounds do not pass through this pipeline as transparent assets.
```

### M29.2 icon preflight

M29.2 raster icons require:

```text
visualKind == raster_icon
pixelOwner == raster_icon
replayDecision == icon_replay
area <= 12000
not too thin
confidence != low
inside image bounds
textOverlap <= 0.20
```

Code evidence:

```text
backend/app/transparent_asset_report/candidates.py:37-74
```

### M29.6 internal icon preflight

M29.6 internal candidates require:

```text
role == internal_icon_candidate
candidateDecision == accepted_report_candidate
confidence == high OR groupSupportedExecution == true
area <= 12000
not too thin
textOverlap <= 0.20
heroPenalty <= 0.42
inside image bounds
```

Code evidence:

```text
backend/app/transparent_asset_report/candidates.py:77-126
```

This is the exact gate that rejected the Google icon artifact:

```text
internal_candidate_not_execution_supported
```

That means:

```text
M29.6 found the candidate,
but transparent report refused to even run alpha analysis because execution support was missing.
```

### Soft-edge alpha profile

For anchored soft-edge icons, transparent report allows a more tolerant edge-alpha path only if:

```text
has OCR anchor
anchorRelation in above/below/left/right text
confidence high or groupSupportedExecution
groupSupportedExecution true
textAnchorScore >= 0.70
textOverlap <= 0.14
heroPenalty <= 0.26
```

Code evidence:

```text
backend/app/transparent_asset_report/candidates.py:129-142
```

This is a strong positive evidence gate, not a global loosen.

### Analysis bbox

For M29.6 internal icons, alpha analysis expands bbox inside the parent media:

```text
padding = clamp(shortEdge * 0.45, 4, 12)
analysis bbox constrained to container/media
```

Code evidence:

```text
backend/app/transparent_asset_report/pipeline.py:80-88
backend/app/transparent_asset_report/alpha.py:143-154
```

This is why promotion later uses `analysisBbox` as the promoted source bbox. It prevents clipping glow/edges but can enlarge overlap relations.

### Background estimation

Default icon uses edge background sample:

```text
dominant_rgb(edgePixels)
edge variance <= 38
```

M29.6 internal icon with expanded context uses dominant cluster background:

```text
dominant 16x color bucket
coverage >= 0.36 and clusterVariance <= 18
or allEdgeVariance <= 38
```

Code evidence:

```text
backend/app/transparent_asset_report/alpha.py:170-201
```

Soft-edge fallback background can pass with:

```text
coverage >= 0.32
clusterVariance <= 8
```

Code evidence:

```text
backend/app/transparent_asset_report/alpha.py:204-208
```

### Alpha mask

Alpha is generated from RGB distance to background:

```text
if distance <= 24: alpha = 0
elif distance >= 72: alpha = 255
else: alpha = 255 * (distance - 24) / 48
```

Code evidence:

```text
backend/app/transparent_asset_report/alpha.py:255-272
```

This is the current "shape crop" implementation: PNG remains rectangular, but non-foreground pixels are transparent.

### Alpha rejection gates

Reject if:

```text
unstable background
foreground ratio < 0.04
foreground ratio > 0.88
edge alpha risky
largest component ratio < 0.35
asset crop fails
```

Code evidence:

```text
backend/app/transparent_asset_report/alpha.py:31-109
```

Default edge alpha risk:

```text
if edgeAlphaCoverageGt32 > 0.12 or edgeAlphaMean > 28:
  reject
```

Soft-edge profile allows:

```text
edgeAlphaCoverageGt32 <= 0.30
edgeAlphaMean <= 48
largestComponentRatio >= 0.90
```

Code evidence:

```text
backend/app/transparent_asset_report/alpha.py:211-220
```

## Information Loss

### Loss 1: AssetPath becomes a hard bridge requirement

Downstream promotion requires:

```text
transparent decision == allow
assetPath != null
```

If transparent rejects, evidence can still be `report_only`, but promotion will reject with:

```text
missing_transparent_asset_path
```

This is correct for safe visible replay, but it makes transparent preflight a very important gate.

### Loss 2: Medium but plausible internal candidates are not analyzed unless group-supported

Preflight rejects:

```text
confidence != high and not groupSupportedExecution
```

This avoids false positives, but it also blocks cases where a single button/icon has strong anchor evidence but no repeated group.

Real artifact:

```text
task_33428579a6f7 Google icon candidates:
  inputConfidence = medium
  inputScore = 0.64 / 0.59
  textAnchor = strong in evidence report
  transparent reject = internal_candidate_not_execution_supported
```

### Loss 3: Transparent assets are icon-only

No equivalent transparent/control-background extraction path exists for:

```text
button background
tab selected marker
table marker
small decorative state
```

## Known Failure Symptoms Mapped To This Layer

### Candidate exists but icon not selectable

Check:

```text
transparent item decision
assetPath
preflightRisks
edge_alpha_risk
unstable_background
internal_candidate_not_execution_supported
```

If `assetPath` is null, promotion will not happen.

### Icon has glow and gets rejected

Soft-edge profile only applies to strongly anchored and group-supported candidates. Unanchored soft edge remains rejected.

### Button background not selectable

Transparent asset report is not the owner unless the background is represented as a raster_icon/internal_icon candidate. Current pipeline has no transparent button-background promotion path.

## Tests / Guards

Direct tests:

```text
backend/tests/test_transparent_asset_report.py
```

Important guards:

```text
test_raster_icon_on_stable_background_allows_rgba_debug_asset
test_ocr_overlap_rejects_transparent_asset
test_unstable_background_rejects_asset
test_edge_alpha_risk_rejects_background_block_asset
test_medium_confidence_internal_icon_without_group_support_is_report_rejected
test_group_supported_medium_internal_icon_uses_alpha_gate
test_anchored_group_supported_internal_icon_allows_soft_edge_glow
test_unanchored_internal_icon_with_soft_edge_still_rejects_edge_alpha_risk
test_internal_icon_uses_context_bbox_for_stable_action_strip_background
```

## Findings

### P1: Transparent preflight is the immediate blocker for some detected icons

Evidence:

```text
backend/app/transparent_asset_report/candidates.py:94-96
task_33428579a6f7 transparent report
```

Judgment:

```text
This is why "M29.6 found it but Figma cannot select it" happens. The candidate never gets an assetPath, so promotion rejects it.
```

Recommended next action:

```text
Do not globally lower this gate. Add a more general single-control/icon evidence path if strong independent evidence exists without repetition.
```

### P2: `assetPath` is a valid hard requirement, but it can hide why evidence was strong

Evidence:

```text
promotion reject reason = missing_transparent_asset_path
evidence report still has positive textAnchor/sourceCandidateScore
```

Judgment:

```text
Promotion should require an asset, but debug reports should make preflight-vs-alpha rejection obvious.
```

Recommended next action:

```text
In roadmap, improve failure ledgers around transparent preflight categories.
```

### P2: Alpha math is rule-based and explainable, but still not a full background-removal model

Evidence:

```text
backend/app/transparent_asset_report/alpha.py:255-272
```

Judgment:

```text
This is appropriate for UI icons. It will not match AI segmentation on complex products/people/glass, and should not be treated as generic background removal.
```

Recommended next action:

```text
Keep scope as transparent UI asset extraction unless explicitly adding a segmentation provider later.
```

## Recommended Next Action

Continue to evidence contract:

```text
Check whether it truly combines independent evidence or still collapses into assetPath + confidence.
```
