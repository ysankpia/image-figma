# 08 M29.6 Media Internal Decomposition

## Source Truth

M29.6 consumes:

```text
source PNG pixels
OCR boxes
raw M29 nodes and blocked nodes
M29.2 source objects
M29.3 relation metadata
M29.5 replay plan metadata
```

Primary package:

```text
backend/app/media_internal_decomposition/
```

Runtime entrypoint:

```text
backend/app/media_internal_decomposition/pipeline.py:16
```

First-principles role:

```text
M29.6 is the second-pass evidence extractor for objects inside preserve_raster media.
It is report-only.
It does not promote candidates, create assets, create DSL nodes, or authorize cleanup.
```

## Input Artifacts

```text
original PNG
m29/nodes.json
ocr/ocr.json
m29_2/source_ui_physical_graph.json
m29_3/region_relation_graph_report.json
m29_5/replay_plan.json
```

Code evidence:

```text
backend/app/media_internal_decomposition/pipeline.py:29-47
```

## Output Artifacts

Primary output:

```text
m29_media_internal_decomposition/media_internal_decomposition_report.json
```

Major fields:

```text
compositeMediaItems
textMasks
internalCandidates
matchedInternalGroups
rejectedFragments
warnings
```

Validation enforces report-only:

```text
backend/app/media_internal_decomposition/validation.py:6-30
```

## Decision Authority

### This layer can decide

M29.6 can decide evidence-level facts:

```text
which preserve_raster images are composite media
which OCR boxes belong to media context
text protection masks
internal candidate bbox/role/score
candidateDecision accepted_report_candidate vs rejected_fragment
matched OCR anchor
anchorRelation
repetition score
groupSupportedExecution
action_row matchedInternalGroups
```

### This layer must not decide

M29.6 must not decide:

```text
visible replay
source ownership promotion
transparent asset allow/reject
cleanup targets
materialization
button/control object creation
selected-state materialization
```

This is encoded in `REPORT_ONLY_META`:

```text
reportOnly = true
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
materializationChanged = false
```

Code evidence:

```text
backend/app/media_internal_decomposition/types.py:11-19
```

## Main Formulas And Gates

### Composite media detection

M29.6 starts from M29.2 media source objects:

```text
pixelOwner == preserve_raster
replayDecision == image_replay
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:77-79
```

It treats media as composite if:

```text
has OCR text in media context
or has at least 2 raw nodes inside
or source risk contains_internal_text
or source PNG exists and media bbox is at least 24x24
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:81-85
```

The final fallback condition means M29.6 can scan many media regions even without OCR. That is important: the layer is no longer "only OCR above text".

### Text-in-media context

OCR text belongs to media if:

```text
containment_ratio(text, media) >= 0.95
```

or if the text has high horizontal overlap and fits an expanded media anchor bbox:

```text
horizontal_overlap >= 0.95
containment_ratio(text, expanded_media_anchor_bbox) >= 0.95
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:94-107
```

This fixes the "label slightly outside media" case without using literal labels or fixed coordinates.

### Text mask

M29.6 protects OCR text with a small padded mask:

```text
paddedBbox = OCR bbox padded by 3 px
reason = internal_ocr_text_protection
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:110-119
```

This is necessary to avoid treating text strokes as icons.

### Raw internal candidates

For raw symbols/shapes/unknowns inside media, M29.6 computes:

```text
sizeScore
compactnessScore
colorCoherenceScore
textAnchorScore
relationConsistencyScore
repetitionScore
heroGraphicPenalty
textMaskOverlap
```

Candidate score:

```text
score =
  size * 0.18
  + compact * 0.16
  + color * 0.12
  + textAnchor * 0.34
  - hero * 0.20
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:171-247
```

Reject reasons include:

```text
overlaps_internal_text_mask
large_media_fragment
separator_not_icon
hero_or_texture_fragment
weak_internal_candidate_score
```

This is a genuine evidence formula, not a single confidence gate.

### Anchor relations

M29.6 supports:

```text
above_text
below_text
left_of_text
right_of_text
near_text
```

Directional score uses cross-axis distance and ideal gap:

```text
score = exp(-cross_delta^2 / (2*sigma_cross^2))
      * exp(-(gap - ideal_gap)^2 / (2*sigma_gap^2))
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:274-345
```

This answers the user's concern:

```text
current code is not limited to "OCR 上方".
It scans above, below, left, right, and near text.
```

### Pixel anchor candidates

If the source PNG can be decoded, M29.6 scans anchor windows around OCR text and extracts connected foreground components:

```text
for each OCR block:
  for each anchor window:
    local foreground mask
    connected components
    score component as internal icon candidate
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:657-687
backend/app/media_internal_decomposition/candidates.py:841-880
backend/app/media_internal_decomposition/candidates.py:933-1003
```

Foreground pixel rule:

```text
color_distance(rgb, local_edge_background) >= 55
and saturation >= 15
and luma >= 18
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:883-890
```

### Generic non-OCR foreground scan

M29.6 also scans the media region with tiled windows even without OCR anchors:

```text
generic_scan_windows(media)
foreground_components_in_window
score_generic_foreground_candidate
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:690-719
backend/app/media_internal_decomposition/candidates.py:722-748
backend/app/media_internal_decomposition/candidates.py:761-828
```

This is the correct generalization beyond OCR-anchored icons. It is still conservative later: generic non-OCR foreground cannot become visible replay unless evidence contract proves strong anchoring/group support.

### Repetition and action-row support

M29.6 boosts accepted internal icon candidates that form repeated icon/text row geometry:

```text
repetition = (icon row alignment + icon gap stability) / 2
score += repetition * 0.12
if repetition >= 0.55:
  groupSupportedExecution = confidence in {high, medium}
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:378-395
```

It also builds matched groups:

```text
role = action_row
layoutModel = row
items = candidate + OCR text pairs
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:548-609
```

### Fragment merge

For split icon fragments with the same OCR anchor and same directional relation, M29.6 can create a union candidate:

```text
same OCR anchor
same anchor relation
mergeable geometry
union bbox icon-like
not near-equal to existing accepted bbox
=> merged_anchor_icon_fragments
```

Code evidence:

```text
backend/app/media_internal_decomposition/candidates.py:398-535
```

This directly addresses the earlier "划转 icon 被切成两段" failure.

## Information Loss

### Loss 1: M29.6 currently promotes only icon-like candidates downstream

M29.6 reports roles such as:

```text
internal_icon_candidate
internal_shape_candidate
internal_decorative_candidate
internal_separator_candidate
```

But transparent/evidence/promotion only support internal icon candidate flow.

Consequence:

```text
button/control background inside media can be reported weakly, but currently lacks an equal execution/promotion path.
```

This is the biggest architectural gap for "text editable but button not draggable".

### Loss 2: Candidate bbox is still bbox + alpha later, not vector/shape semantics

Even if M29.6 finds a blue/purple icon, it becomes a candidate bbox. Shape-preserving alpha happens in transparent asset report. M29.6 itself does not output mask/alpha.

### Loss 3: Local background model is window-edge median, not full smooth background

The current pixel foreground uses median edge RGB per window, not a full per-pixel local background model. That is simpler and works for many UI icons, but complex gradients/glow can still fragment or reject.

### Loss 4: Generic scan is conservative and capped

Generic scan caps:

```text
GENERIC_SCAN_MAX_WINDOWS = 96
GENERIC_FOREGROUND_MAX_CANDIDATES = 80
```

This prevents explosion but can miss dense table markers or many small circles.

## Known Failure Symptoms Mapped To This Layer

### Three of four action icons detected, one missing

If the missing icon appears as two same-anchor fragments:

```text
merge_anchor_icon_fragments should create a union candidate.
```

If no candidate appears, inspect:

```text
text mask overlap
foreground contrast
component min area/short edge/aspect gates
hero penalty
same OCR anchor relation
```

### Google/Snapchat icon still not selectable

Real artifact `task_33428579a6f7` shows:

```text
M29.6 found candidates:
  m292_object_0010:internal_candidate_0030
  m292_object_0010:internal_candidate_0031

But they were medium confidence without groupSupportedExecution.
Transparent preflight rejected:
  internal_candidate_not_execution_supported
```

So M29.6 detection happened. The bridge failed at execution support / transparent preflight, not at Figma.

### Bottom tab marker not selectable

If marker is long/thin:

```text
long_thin -> separator_not_icon
```

That is probably correct for icon replay. But there is no selected-state marker promotion role yet.

## Tests / Guards

Direct tests:

```text
backend/tests/test_media_internal_decomposition.py
```

Important guards:

```text
test_composite_media_with_internal_ocr_and_symbol_reports_candidate
test_text_mask_rejects_raw_component_overlapping_internal_ocr
test_repeated_icon_label_row_builds_matched_group_without_text_literal_rule
test_ocr_anchor_foreground_uses_multiple_relations_not_only_above_text
test_non_ocr_foreground_component_inside_media_reports_candidate
test_non_ocr_foreground_still_respects_internal_text_mask
test_fragmented_icon_parts_with_same_text_anchor_get_union_candidate
test_near_media_bottom_label_can_anchor_internal_icon_candidate
test_separator_inside_media_is_rejected_not_icon
```

## Findings

### P1: M29.6 has the right general shape for media-internal icon recovery

Evidence:

```text
backend/app/media_internal_decomposition/candidates.py:133-168
backend/app/media_internal_decomposition/candidates.py:657-719
```

Judgment:

```text
It is not a one-sample carousel special case. It combines OCR protection, local foreground, connected components, text anchors, repetition, generic scan, and fragment merge.
```

Recommended next action:

```text
Keep this as evidence layer. Do not let it directly materialize.
```

### P1: Missing Codia-like button/control structure is not solved by the current M29.6 bridge

Evidence:

```text
downstream transparent/evidence/promotion only consumes internal_icon_candidate.
```

Judgment:

```text
The current bridge can promote internal icons, not internal control backgrounds or selected markers. This is a real product gap.
```

Recommended next action:

```text
Roadmap should add internal control/background candidate contract before materializer changes.
```

### P2: Generic non-OCR foreground scan is present but intentionally hard to promote

Evidence:

```text
backend/app/media_internal_decomposition/candidates.py:690-828
backend/app/m29_evidence_contract/scoring.py:226-239
```

Judgment:

```text
This is correct. Otherwise maps, decorative lines, routes, and texture fragments would become selectable icons.
```

Recommended next action:

```text
Promotion should stay evidence-gated; improve group/control evidence rather than globally loosening non-OCR foreground.
```

### P2: Local foreground formula is useful but still weaker than a full local background model

Evidence:

```text
backend/app/media_internal_decomposition/candidates.py:865-890
```

Judgment:

```text
Median edge background per search window is pragmatic. It may still fail on gradient/glow/icon-edge cases.
```

Recommended next action:

```text
If repeated failures remain, consider per-pixel smoothed local background in M29.6, not materializer fixes.
```

## Recommended Next Action

Continue to transparent asset report:

```text
This is where report candidates either get a real alpha PNG path or become blocked from promotion.
```
