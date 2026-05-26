# 10 Evidence Contract

## Source Truth

Evidence contract consumes:

```text
M29.2 source ownership
M29.6 media internal decomposition candidates
transparent asset report items
```

Primary package:

```text
backend/app/m29_evidence_contract/
```

Runtime entrypoint:

```text
backend/app/m29_evidence_contract/pipeline.py:14
```

First-principles role:

```text
This layer combines independent evidence and risk into allow_visible_replay / report_only / reject.
It remains report-only.
It does not create source objects, DSL nodes, assets, or cleanup permissions.
```

## Input Artifacts

```text
m29_2/source_ui_physical_graph.json
m29_media_internal_decomposition/media_internal_decomposition_report.json
m29_transparent_assets/transparent_asset_report.json
```

Code evidence:

```text
backend/app/m29_evidence_contract/pipeline.py:23-32
```

## Output Artifacts

Primary output:

```text
m29_evidence_contract/evidence_contract_report.json
```

Item fields:

```text
contractId
candidateId
candidateRole
sourceKind
mediaSourceObjectId
bbox
sourceTruth
positiveEvidence
negativeEvidence
risk
decision
reportOnly
```

Validation enforces:

```text
decision.mode in allow_visible_replay / report_only / reject
reportOnly = true
sourceOwnershipChanged = false
materializerConsumesContracts = false
```

Code evidence:

```text
backend/app/m29_evidence_contract/validation.py:6-47
backend/app/m29_evidence_contract/types.py:8-18
```

## Decision Authority

### This layer can decide

Evidence contract can decide:

```text
evidenceScore
positiveEvidence/negativeEvidence
risk level
decision mode
promotionAllowed boolean
promotion requirement statement
```

### This layer must not decide

It must not decide:

```text
source ownership mutation
visible replay
cleanup targets
materialization
actual asset replacement
```

Only internal source promotion may consume `allow_visible_replay` and mutate the M29.2 document.

## Main Formulas And Gates

### Positive evidence

For M29.6 internal icon candidates:

```text
sourceCandidateScore
sizeCompactness
textAnchor
sameMediaContainment
repetition
relationConsistency
transparentAsset
```

Code evidence:

```text
backend/app/m29_evidence_contract/scoring.py:33-41
```

### Negative evidence

```text
textOverlapPenalty
heroGraphicPenalty
cleanupRisk
repairCostPenalty
```

Code evidence:

```text
backend/app/m29_evidence_contract/scoring.py:49-54
```

### Evidence score

Formula:

```text
score =
  sourceCandidateScore * 0.20
  + sizeCompactness * 0.12
  + textAnchor * 0.16
  + sameMediaContainment * 0.12
  + repetition * 0.10
  + relationConsistency * 0.10
  + transparentAsset * 0.20
  - textOverlapPenalty * 0.20
  - heroGraphicPenalty * 0.16
  - cleanupRisk * 0.12
  - repairCostPenalty * 0.08
```

Code evidence:

```text
backend/app/m29_evidence_contract/scoring.py:175-190
```

This is the right conceptual move: not pure confidence, but evidence consistency plus risk.

### Decision mode

Allow visible replay requires:

```text
no hard reasons
evidenceScore >= 0.68
transparentAllowed
executionSupported
mediaContainment >= 0.95
textOverlap <= 0.20
heroPenalty <= 0.42
```

Report-only requires:

```text
evidenceScore >= 0.42
```

otherwise reject.

Code evidence:

```text
backend/app/m29_evidence_contract/scoring.py:192-207
```

### Hard rejection

Hard reject if:

```text
not internal_icon_candidate
candidate not accepted
generic foreground not visible replay
missing parent media
text overlap > 0.30
hero penalty > 0.62
```

Code evidence:

```text
backend/app/m29_evidence_contract/scoring.py:209-223
```

### Generic foreground guard

A generic pixel component with `rawSubtype = non_ocr_foreground` can pass only if:

```text
has OCR anchor
anchor relation is above/below/left/right
textAnchorScore >= 0.70
textOverlap <= 0.20
heroPenalty <= 0.26
groupSupportedExecution == true
```

Code evidence:

```text
backend/app/m29_evidence_contract/scoring.py:226-239
```

This is the correct protection against promoting arbitrary image texture.

## Information Loss

### Loss 1: TransparentAsset is still a hard term

Evidence score gives transparentAsset a positive weight, but decision mode still requires:

```text
transparentAllowed == true
```

So strong source/text-anchor evidence cannot promote without assetPath.

This is a deliberate safety gate, but it explains real failures.

### Loss 2: Only internal icons get promotion contracts

The contract builder iterates:

```text
candidate.role == internal_icon_candidate
```

and label-anchored blocked icons are audit-only.

Code evidence:

```text
backend/app/m29_evidence_contract/pipeline.py:75-89
backend/app/m29_evidence_contract/pipeline.py:89-104
```

There is no evidence contract for:

```text
internal_control_background
internal_button
selected_marker
table_marker
shape/decorator state
```

### Loss 3: Label-anchored blocked icons do not use this for promotion

M29.2 label-anchored blocked icons are already source owned. Evidence contract emits audit-only items:

```text
mode = report_only
requiredForPromotion = false
promotionAllowed = false
```

Code evidence:

```text
backend/app/m29_evidence_contract/scoring.py:113-172
```

## Known Failure Symptoms Mapped To This Layer

### Candidate has strong anchor but stays report-only

Real artifact `task_33428579a6f7`:

```text
sourceCandidateScore = 0.64
textAnchor = 0.883
sameMediaContainment = 1.0
transparentAsset = 0.0
risks = transparent_asset_not_allowing_visible_replay + internal_candidate_not_execution_supported
mode = report_only
```

This is not an evidence-contract math bug by itself. It is a transparent/execution-support gate problem.

### Non-OCR route/line/texture would otherwise be promoted

The `generic_foreground_not_visible_replay` guard prevents false positives. Do not remove it globally.

### Button background missing

Evidence contract currently cannot allow a button/control background because it has no candidate sourceKind for it.

## Tests / Guards

Direct tests:

```text
backend/tests/test_m29_evidence_contract.py
```

Important guards:

```text
test_high_evidence_internal_icon_allows_visible_replay
test_transparent_reject_keeps_candidate_report_only
test_high_text_overlap_rejects_internal_icon_contract
test_medium_group_supported_internal_icon_can_allow_with_consistent_evidence
test_generic_non_ocr_foreground_is_not_promoted_even_with_alpha
test_anchored_group_supported_non_ocr_foreground_can_pass_evidence_contract
test_anchored_non_ocr_foreground_without_group_support_stays_rejected
test_label_anchored_blocked_icon_is_audit_only_not_promotion_contract
```

## Findings

### P1: Evidence contract is conceptually correct and better than confidence-only

Evidence:

```text
backend/app/m29_evidence_contract/scoring.py:33-71
backend/app/m29_evidence_contract/scoring.py:175-207
```

Judgment:

```text
The formula combines source score, geometry, anchor, containment, repetition, transparent alpha, cleanup risk, and repair cost. This is the right direction.
```

Recommended next action:

```text
Keep the contract. Extend it to more roles instead of bypassing it.
```

### P1: Evidence contract currently cannot solve button/control backgrounds

Evidence:

```text
backend/app/m29_evidence_contract/pipeline.py:75-89
```

Judgment:

```text
Only internal_icon_candidate is eligible. This is why Codia-like button extraction remains incomplete even after text/icon improvements.
```

Recommended next action:

```text
Roadmap should add internal control/background evidence contract and promotion path, not materializer hacks.
```

### P2: AssetPath requirement is safe but creates a single-point blocker

Evidence:

```text
backend/app/m29_evidence_contract/scoring.py:30
backend/app/m29_evidence_contract/scoring.py:192-203
```

Judgment:

```text
Visible replay of a raster icon needs a valid transparent asset. But when alpha preflight rejects before analysis, strong source evidence is stranded.
```

Recommended next action:

```text
Improve transparent preflight categories and consider a general single-button/single-icon execution-support proof.
```

### P2: Generic foreground guard is necessary

Evidence:

```text
backend/app/m29_evidence_contract/scoring.py:226-239
```

Judgment:

```text
This prevents overfitting and false positives. Do not loosen globally for one sample.
```

Recommended next action:

```text
Add stronger positive contracts for known UI structures instead.
```

## Recommended Next Action

Continue to internal source promotion:

```text
Verify the only bridge that mutates M29.2 and therefore enables final M29.3/M29.4/M29.5 replay.
```
