# 11 Internal Source Promotion

## Source Truth

Internal source promotion consumes:

```text
base M29.2 source ownership document
M29.6 media internal candidates
transparent asset report
evidence contract report
```

Primary package:

```text
backend/app/internal_source_promotion/
```

Runtime entrypoint:

```text
backend/app/internal_source_promotion/pipeline.py:13
```

First-principles role:

```text
This is the only current bridge from report-only internal evidence back into source ownership.
It mutates the M29.2 document by appending promoted source objects.
It does not create DSL nodes directly.
After promotion, upload-preview reruns M29.3, M29.4, M29.5, and ownership conservation.
```

## Input Artifacts

```text
m29_2/source_ui_physical_graph.json
m29_media_internal_decomposition/media_internal_decomposition_report.json
m29_transparent_assets/transparent_asset_report.json
m29_evidence_contract/evidence_contract_report.json
```

Code evidence:

```text
backend/app/internal_source_promotion/pipeline.py:23-31
```

## Output Artifacts

Primary outputs:

```text
m29_internal_source_promotion/internal_source_promotion_report.json
m29_internal_source_promotion/source_ui_physical_graph.promoted.json
```

Report summary:

```text
baseSourceObjectCount
promotedSourceObjectCount
finalSourceObjectCount
rejectedCandidateCount
sourceOwnershipChanged
```

Code evidence:

```text
backend/app/internal_source_promotion/pipeline.py:33-71
```

## Decision Authority

### This layer can decide

Promotion can decide:

```text
which allow_visible_replay internal icon candidates become M29.2 source objects
promoted object bbox
promoted sourceEvidence
duplicate promoted bbox dedupe
promoted M29.2 summary update
```

### This layer must not decide

Promotion must not decide:

```text
visible replay order
cleanupTargets
materialization
Figma node creation
alpha analysis
evidence scoring
button/control background promotion unless a contract exists
```

It marks:

```text
promotionOnly = true
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
materializationChanged = false
```

Code evidence:

```text
backend/app/internal_source_promotion/types.py:8-15
backend/app/internal_source_promotion/pipeline.py:248-261
```

## Main Gates

Promotion requires all of:

```text
candidate exists
candidate.role == internal_icon_candidate
candidateDecision == accepted_report_candidate
parent media source object exists in base M29.2
candidate bbox valid
transparent item exists
transparent decision == allow
transparent assetPath != null
evidence contract exists
evidence contract decision.mode == allow_visible_replay
```

Code evidence:

```text
backend/app/internal_source_promotion/pipeline.py:157-180
```

This is the strongest safety gate in the bridge. It is also where real candidates become impossible to select if any upstream report rejects them.

## Promoted Object Contract

Promoted object shape:

```text
visualKind = raster_icon
pixelOwner = raster_icon
replayDecision = icon_replay
confidence = high or medium
```

Source evidence includes:

```text
m29NodeIds
mediaSourceObjectId
candidateBbox
mediaInternalCandidateId
transparentAssetPath
transparentAssetBbox
transparentAssetCandidateId
evidenceContractId
evidenceContractDecision
evidenceScore
promotionSource = m29_6_internal_icon_candidate
textOverlapRatio
mediaContainmentRatio
```

Code evidence:

```text
backend/app/internal_source_promotion/pipeline.py:183-224
```

Important bbox rule:

```text
promoted bbox = transparent analysisBbox if present, otherwise candidate bbox
candidateBbox is preserved separately
```

Code evidence:

```text
backend/app/internal_source_promotion/pipeline.py:187-188
backend/tests/test_internal_source_promotion.py::test_internal_source_promotion_uses_transparent_asset_analysis_bbox
```

This is correct for padded transparent assets, but it can increase overlap and must be handled by M29.5/ownership conservation.

## Deduplication

Promotion dedupes exact same promoted bbox by rank:

```text
rank = (evidenceScore, len(candidateId), mediaId)
keep highest
reject duplicate_promoted_internal_bbox
```

Code evidence:

```text
backend/app/internal_source_promotion/pipeline.py:118-154
```

M29.5 later handles near-equal promoted internal icons by evidence score, using relation graph.

## Information Loss

### Loss 1: Only internal icons are promoted

Promotion filters:

```text
candidate.role == internal_icon_candidate
sourceKind == m29_6_internal_icon_candidate
```

Code evidence:

```text
backend/app/internal_source_promotion/pipeline.py:82-101
```

There is no current promotion object for:

```text
internal control background
button group
selected marker
table marker
internal shape/decorator
```

This is the main missing path for Codia-like draggable buttons and state markers.

### Loss 2: Rejected reason can hide upstream evidence strength

Promotion rejection reason is often:

```text
missing_transparent_asset_path
evidence_contract_not_allowing_visible_replay
```

Those are correct final reasons, but they require looking back at transparent/evidence reports to understand whether the candidate was weak, unsupported, or only failed alpha preflight.

### Loss 3: Promoted confidence is coarse

Promoted confidence becomes:

```text
high if candidate confidence high else medium
```

The detailed evidenceScore is preserved in sourceEvidence, but confidence itself is coarse.

## Known Failure Symptoms Mapped To This Layer

### M29.6 candidate exists but no final icon

Check promotion report:

```text
rejectedCandidates[].reason
```

If:

```text
missing_transparent_asset_path
```

then the owner is transparent preflight/alpha, not M29.5 or Figma.

If:

```text
evidence_contract_not_allowing_visible_replay
```

then inspect evidence contract positive/negative evidence and hard reasons.

### Final M29.5 does not include icon

If promotion count is zero:

```text
final M29.3/M29.4/M29.5 cannot include that internal icon.
```

If promotion count is positive but M29.5 suppresses it:

```text
owner moves to M29.5 duplicate/overlap/budget logic.
```

## Tests / Guards

Direct tests:

```text
backend/tests/test_internal_source_promotion.py
```

Important guards:

```text
test_internal_source_promotion_promotes_high_confidence_allowed_internal_icon
test_internal_source_promotion_rejects_medium_without_group_support_internal_icon
test_internal_source_promotion_promotes_group_supported_medium_internal_icon
test_internal_source_promotion_uses_transparent_asset_analysis_bbox
test_internal_source_promotion_requires_evidence_contract_even_when_alpha_allows
test_internal_source_promotion_dedupes_same_promoted_bbox_by_evidence_score
```

## Findings

### P1: Promotion boundary is architecturally correct

Evidence:

```text
backend/app/internal_source_promotion/pipeline.py:157-180
```

Judgment:

```text
It correctly requires candidate + transparent asset + evidence contract before mutating source ownership.
```

Recommended next action:

```text
Do not bypass this bridge in materializer.
```

### P1: Promotion currently only supports internal icons

Evidence:

```text
backend/app/internal_source_promotion/pipeline.py:82-101
```

Judgment:

```text
This is the biggest reason text can become editable while the full button/control is not draggable.
```

Recommended next action:

```text
Design a parallel promotion contract for internal control/background/selected marker candidates before changing materializer.
```

### P2: Promotion report needs upstream-reason trace for faster diagnosis

Evidence:

```text
rejectedCandidates only stores candidateId, reason, bbox.
```

Judgment:

```text
For real-sample debugging, `missing_transparent_asset_path` is too shallow unless the user opens transparent/evidence reports.
```

Recommended next action:

```text
Add richer rejected candidate diagnostic fields later: transparentCandidateId, transparentDecision, transparentRisks, evidenceMode, evidenceScore.
```

### P2: Analysis bbox promotion is necessary but increases overlap pressure

Evidence:

```text
backend/app/internal_source_promotion/pipeline.py:187-188
```

Judgment:

```text
Correct for padded alpha assets, but it requires M29.5 and ownership conservation to treat small text/media overlaps as explainable.
```

Recommended next action:

```text
Keep existing M29.5/ownership promoted icon overlap guards and include them in heuristic ledger.
```

## Recommended Next Action

Continue to final replay and materializer:

```text
Verify that after promotion, final M29.5 is the only materializer input and that materializer only consumes plan permissions.
```
