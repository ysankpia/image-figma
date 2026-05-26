# 03 M29.2 Source Ownership

## Source Truth

M29.2 consumes three fact sources:

```text
source PNG pixels
OCR boxes
raw M29 primitive graph nodes + blocked primitives
```

Primary entrypoint:

```text
backend/app/source_ui_physical_graph/pipeline.py:20
```

The runtime wrapper calls it from:

```text
backend/app/upload_preview/stages.py
```

M29.2 is the first layer that turns raw visual evidence into source ownership objects:

```text
visualKind
pixelOwner
replayDecision
sourceEvidence
confidence
reasons
risks
```

Type contract:

```text
backend/app/source_ui_physical_graph/types.py:7-33
backend/app/source_ui_physical_graph/types.py:75-98
```

First-principles interpretation:

```text
raw M29 says "there is a primitive-like thing here";
M29.2 says "this thing owns pixels in this way and is or is not eligible for replay".
```

That means M29.2 is not just a report layer. It is a source ownership gate.

## Input Artifacts

```text
m29/nodes.json
ocr/ocr.json
storage/uploads/{taskId}/original.png
```

The pipeline loads OCR boxes from `text_boxes_from_ocr_document`, raw nodes from `m29_document["nodes"]`, and blocked records from `m29_document["blocked"]`. See:

```text
backend/app/source_ui_physical_graph/pipeline.py:35-37
```

## Output Artifacts

Primary output:

```text
m29_2/source_ui_physical_graph.json
```

Debug output:

```text
m29_2/source_ui_physical_graph_overlay.png
```

Payload fields:

```text
schemaName = M292SourceUiPhysicalGraph
sourceObjects
summary
options
warnings
debug
meta.truthSource = source_png_plus_ocr_plus_m29_primitives
```

Code evidence:

```text
backend/app/source_ui_physical_graph/pipeline.py:48-67
```

## Runtime Order Inside M29.2

Current order:

```text
1. detect_media_objects
2. classify_ocr_text_objects
3. cluster_icon_objects
4. classify_shape_objects
5. classify_unknown_objects
6. classify_blocked_objects
7. dedupe_objects
8. write report + overlay
```

Code evidence:

```text
backend/app/source_ui_physical_graph/pipeline.py:38-46
```

This order matters. Media is detected first, so later text/icon/shape/block recovery can know whether a candidate is inside a preserved raster region. That is architecturally correct, but it also means a large accepted media object becomes a strong suppressor for independent icon/shape replay.

## Decision Authority

### This layer can decide

M29.2 is allowed to decide:

```text
source object identity
visualKind
pixelOwner
replayDecision
whether OCR text is editable or preserved
whether raw symbol fragments become raster_icon
whether raw shape evidence becomes shape_geometry
whether unknown image-like regions are media or control backgrounds
whether blocked raw fragments are recoverable
diagnostic-only classification
dedupe between overlapping source objects
```

### This layer must not decide

M29.2 must not decide:

```text
M29.5 cleanupTargets
final materialization order
copied media erasure
transparent asset allow/reject
evidence-contract allow_visible_replay
promotion from M29.6 internal candidates
Figma groups, components, auto layout, variables, variants
Renderer or plugin behavior
```

If an object does not exist in M29.2, downstream should not invent it. The only current exception is the explicit bridge:

```text
M29.6 / transparent / evidence contract -> internal source promotion -> promoted M29.2 document
```

## Main Formulas And Gates

### M29.2 object contract

Every object is created by `make_object` with:

```text
sourceEvidence = {
  ocrBoxIds,
  m29NodeIds,
  blockedIds,
  localBackgroundConfidence,
  textOverlapRatio,
  mediaContainmentRatio,
  ...
}
```

Code evidence:

```text
backend/app/source_ui_physical_graph/types.py:101-136
```

This is the right primitive contract. The weakness is not the fields; the weakness is whether later gates require enough independent evidence from these fields instead of using one hard bit such as `assetPath`.

### Media detection

M29.2 preserves media when raw M29 says a node is `image`, or when an `unknown / image_like_low_confidence` is large/colorful/textured enough:

```text
node_type == image
or low_confidence_media
or area >= min_media_area and color_count >= media_color_threshold and texture >= media_texture_threshold
```

Code evidence:

```text
backend/app/source_ui_physical_graph/media.py:13-70
```

It intentionally skips unknowns that look like finite controls:

```text
classify_control_like_unknown(...) is not None -> not media
```

and skips low-confidence unknowns supported by overlapping control shapes:

```text
is_control_shape_supported_low_confidence_unknown(...) -> not media
```

Code evidence:

```text
backend/app/source_ui_physical_graph/media.py:32-35
backend/app/source_ui_physical_graph/media.py:73-90
```

First-principles result:

```text
If raw M29 already swallowed a whole login/button area into one accepted image,
M29.2 has no independent control background source to promote unless raw M29 also emitted a control-like unknown or shape.
```

That matches the class of failures where the label is editable but the surrounding button/background is not selectable.

### OCR text editability

M29.2 makes high-confidence OCR editable unless it is empty/low-confidence or classified as large display text inside media:

```text
low confidence or empty -> preserve_raster_text
large_display_text_inside_media -> preserve_raster_text
otherwise -> editable_ui_text / text_replay
```

Code evidence:

```text
backend/app/source_ui_physical_graph/text.py:12-91
```

The media display-text gate is now relative to containing media scale:

```text
absolute_display_height
and (
  relative_display_height
  or relative_display_width + height floor
  or image_relative_width + media-relative height floor
)
```

Code evidence:

```text
backend/app/source_ui_physical_graph/text.py:105-121
```

This is a better abstraction than the older absolute-width/height-only rule. It explains why `Continue with Google` style long control labels can now become editable while true poster/display text is preserved.

Remaining risk:

```text
Text editability is still mostly text-size + local-background based.
It does not yet prove a full control structure: background + icon + text + cleanup feasibility.
```

So this gate can make text editable without proving the button itself exists as a draggable object.

### Raw symbol icon clustering

M29.2 accepts raw symbols as `raster_icon / icon_replay` only if they:

```text
are raw M29 symbol nodes
fit icon_max_area
are not selected-tab indicators
are not >= 0.80 contained in media
do not overlap OCR text too much
```

Code evidence:

```text
backend/app/source_ui_physical_graph/icons.py:12-75
```

The media containment exclusion is a deliberate boundary:

```text
if symbol is inside preserved media:
  M29.2 does not replay it directly.
```

That prevents double ownership, but it is also a source-chain cliff. Media-contained icons must be recovered later by M29.6/evidence/promotion. If that bridge rejects the candidate, the icon stays unselectable.

### Selected tab indicator exclusion

M29.2 explicitly excludes thin label-aligned selected-tab indicators from standalone icon replay:

```text
height <= 18
width / height >= 3.2
center aligned with OCR label
vertical gap below label is bounded
width ratio near label width
```

Code evidence:

```text
backend/app/source_ui_physical_graph/icons.py:78-96
backend/app/source_ui_physical_graph/unknowns.py:31-36
```

This is not a text/brand/file special case. It is a geometry rule. But it means bottom-tab selected markers currently become diagnostic/non-icon unless another shape/control state path owns them.

Correct first-principles conclusion:

```text
Selected indicator should not be treated as an icon.
But it also should not disappear from structure forever.
It needs a separate selected-state marker / decoration evidence path if product wants it selectable or represented.
```

### Shape ownership

M29.2 converts safe raw shapes into `shape_geometry / shape_replay`:

```text
separator -> separator
card/container/background -> card_background
control subtypes -> control_background
other safe solid shape -> control_background
```

Code evidence:

```text
backend/app/source_ui_physical_graph/shapes.py:52-127
```

Shape safety rejects high text overlap, high color count, high texture, or high edge score:

```text
text_overlap >= 0.45 -> unsafe
color_count > shape_replay_color_threshold -> unsafe
texture > shape_replay_texture_threshold -> unsafe
edge >= shape_replay_edge_threshold -> unsafe
```

Code evidence:

```text
backend/app/source_ui_physical_graph/shapes.py:131-159
```

Small textured foreground shapes are redirected to `raster_icon`, not `shape_geometry`, when they fit icon-size and complexity gates:

```text
badge/small ellipse/icon button/small rounded rect
+ small bbox
+ low text overlap
+ complex foreground metrics
=> raster_icon / icon_replay
```

Code evidence:

```text
backend/app/source_ui_physical_graph/shapes.py:162-187
```

This is a good ownership correction for avatar-like, colored, or textured circular glyphs. The risk is threshold pressure: small dots, selected markers, badges, and icon backgrounds can sit near this boundary.

### Control-like unknown recovery

`image_like_low_confidence` can become `control_background / shape_replay` if it is a finite control:

```text
unknown image-like node
+ finite bbox
+ low enough color/texture/edge complexity
+ sufficient fill ratio
+ contains OCR text with bounded text-area ratio
=> control background
```

Code evidence:

```text
backend/app/source_ui_physical_graph/controls.py:32-60
backend/app/source_ui_physical_graph/controls.py:63-120
```

This is the right abstraction for buttons/search fields. The hard limitation is upstream:

```text
If raw M29 never emits the control-like unknown because the area was swallowed by a larger accepted media region,
this recovery path never runs.
```

That is the likely owning layer for "button text editable, but button background is still part of image".

### Blocked foreground recovery

M29.2 can recover some blocked raw foreground into `raster_icon / icon_replay`:

```text
recoverable reason in {
  symbol_color_too_high,
  symbol_texture_too_high,
  symbol_edge_too_high,
  weak_symbol_metrics
}
+ no hard block
+ small foreground bbox
+ text overlap < 0.20
+ if media-contained, must have label anchor
```

Code evidence:

```text
backend/app/source_ui_physical_graph/blocked.py:13-126
backend/app/source_ui_physical_graph/blocked.py:129-160
```

Label anchor evidence checks same media context, no text intersection, bounded horizontal distance, and either above-label or same-cell vertical relation:

```text
backend/app/source_ui_physical_graph/blocked.py:200-225
```

Hard blocks include:

```text
inside_image_primitive
image_internal_texture
protective_shape_overlap
large_container_fragment
line_like
symbol_area_too_small
symbol_area_too_large
```

Code evidence:

```text
backend/app/source_ui_physical_graph/blocked.py:137-147
```

This boundary is conservative and mostly correct. But it is also the second source-chain cliff:

```text
raw M29 marks a fragment as inside_image_primitive/image_internal_texture
=> M29.2 cannot recover it
=> M29.6 must recover it from media-internal pixels
=> transparent/evidence/promotion must all pass
```

### Dedupe

Overlapping source objects are deduped by replay-decision priority:

```text
text_replay: 5
image_replay: 4
icon_replay: 3
shape_replay: 2
preserve_in_parent_raster: 1
skip: 0
```

Code evidence:

```text
backend/app/source_ui_physical_graph/dedupe.py:7-25
```

This is a simple deterministic rule. It is acceptable as a tie-breaker, but dangerous as semantic proof. If two candidates represent different layers of the same UI object, dedupe can erase useful structure.

## Information Loss

### Loss 1: Media containment suppresses direct icon replay

M29.2 drops direct raw-symbol icon replay when the symbol is inside media:

```text
bbox_overlap_ratio(symbol, media) >= 0.80 -> skip from cluster_icon_objects
```

Consequence:

```text
media-contained icons become dependent on M29.6/transparent/evidence/promotion.
```

This is the correct ownership boundary but a fragile execution chain.

### Loss 2: Accepted media can hide control backgrounds

If a full button row or login button is part of a large media image, M29.2 can still create editable text, but no independent background if raw M29 did not emit a finite control unknown/shape.

Consequence:

```text
text selectable
button/control not selectable
icon may not be selectable
cleanup may create or avoid double ownership depending on M29.5
```

The fix should not be in the materializer. The missing fact is upstream source ownership/evidence.

### Loss 3: Selected-state indicators are diagnostic-only

Selected tab indicators are intentionally not icons:

```text
selected_tab_indicator_not_icon
```

Consequence:

```text
They may be visually preserved in parent raster, but they are not represented as explicit selected-state decoration/control evidence.
```

This is not a bug if the acceptance target is "do not create false icons"; it is a gap if the target is "Codia-like selectable tab states".

### Loss 4: Hard-blocked media-internal fragments need M29.6

`inside_image_primitive` and `image_internal_texture` are hard blocks for M29.2 blocked recovery.

Consequence:

```text
M29.2 cannot rescue many internal media icons by itself.
M29.6 must provide a second-pass internal pixel decomposition path.
```

## Known Failure Symptoms Mapped To This Layer

### Text editable, icon not selectable

Likely chain:

```text
OCR text -> editable_ui_text / text_replay in M29.2
icon pixel -> inside media, blocked, or non-OCR internal candidate
M29.2 does not directly replay media-contained symbol
M29.6/transparent/evidence/promotion fails
=> final DSL has text but not icon
```

M29.2 is partly responsible for the boundary, but not necessarily the final failure.

### Text editable, button background not selectable

Likely chain:

```text
OCR text -> editable_ui_text
button background -> swallowed by media region
no finite control unknown/shape source object
=> M29.5 has no shape_replay plan item
```

Owning fix:

```text
raw M29 / M29.2 finite-control evidence,
or M29.6 internal control/background evidence + promotion,
not materializer hard patches.
```

### Bottom tab selected marker cannot be selected

Current chain:

```text
selected indicator symbol -> selected_tab_indicator_not_icon
=> diagnostic_only / skip
```

This is intentional anti-false-icon behavior. If product wants it represented, the next abstraction should be selected-state decoration/control marker, not icon replay.

## Tests / Guards

Direct tests:

```text
backend/tests/test_source_ui_physical_graph.py
```

Important guards:

```text
test_long_control_label_inside_large_media_remains_editable_text
test_large_display_text_inside_media_is_still_preserved_by_relative_scale
test_selected_tab_indicator_symbol_is_not_standalone_icon
test_symbol_inside_media_is_not_separately_replayed
test_blocked_media_contained_foreground_with_label_anchor_recovers_as_raster_icon
test_blocked_media_contained_foreground_without_label_anchor_stays_diagnostic
test_low_confidence_unknown_yields_to_overlapping_control_shape
```

Relevant bug records:

```text
docs/bugs/resolved/016-media-contained-long-control-label-preserved-as-raster.md
docs/bugs/resolved/015-bottom-tab-selected-icon-stays-non-ocr-foreground.md
```

## Findings

### P1: M29.2 is a correct but hard source-ownership boundary for media-contained icons

Evidence:

```text
backend/app/source_ui_physical_graph/icons.py:30-34
backend/tests/test_source_ui_physical_graph.py::test_symbol_inside_media_is_not_separately_replayed
```

Judgment:

```text
This is not a wrong rule by itself. Directly replaying every symbol inside preserved media would create double ownership.
The gap is that later bridge layers must be strong enough to recover proven internal UI elements.
```

Recommended next action:

```text
Audit M29.6 -> transparent -> evidence -> promotion as the executable recovery path.
Do not patch this in materializer.
```

### P1: Media-contained controls can have editable labels without selectable button backgrounds

Evidence:

```text
backend/app/source_ui_physical_graph/text.py:75-90
backend/app/source_ui_physical_graph/controls.py:32-60
backend/app/source_ui_physical_graph/media.py:32-35
```

Judgment:

```text
Text editability and control-background ownership are currently separate.
That is architecturally fine, but the system needs an internal control/background evidence path when raw M29 swallowed the background into media.
```

Recommended next action:

```text
Audit whether M29.6 can express internal control/background candidates, not just icon/text candidates.
```

### P2: Selected tab indicator has a negative rule but no positive owner path

Evidence:

```text
backend/app/source_ui_physical_graph/icons.py:78-96
backend/app/source_ui_physical_graph/unknowns.py:31-36
backend/tests/test_source_ui_physical_graph.py::test_selected_tab_indicator_symbol_is_not_standalone_icon
```

Judgment:

```text
The negative rule is valid: selected indicator is not an icon.
But Codia-like output likely needs a positive role for selected-state marker/decorative state.
```

Recommended next action:

```text
Add this to the roadmap as a separate evidence contract, not as icon replay.
```

### P2: Threshold-heavy ownership gates need a heuristic ledger

Evidence:

```text
backend/app/source_ui_physical_graph/types.py:37-69
backend/app/source_ui_physical_graph/shapes.py:131-187
backend/app/source_ui_physical_graph/controls.py:63-120
backend/app/source_ui_physical_graph/blocked.py:129-160
```

Judgment:

```text
These are mostly mathematical thresholds, not literal special cases.
But without a ledger of intended domain, non-domain, and regression samples, they become hidden specialization pressure.
```

Recommended next action:

```text
Record them in 15-specialization-and-heuristic-ledger.md with owner, risk, and coverage.
```

### P2: Dedupe priority is deterministic but not a proof of semantic ownership

Evidence:

```text
backend/app/source_ui_physical_graph/dedupe.py:7-25
```

Judgment:

```text
The current priority is simple and stable. But if a future promoted control, icon, and text overlap as legitimate sibling layers, IoU-only dedupe could discard evidence.
```

Recommended next action:

```text
When auditing promotion and final replay, check whether dedupe suppression is explainable by source role, not only bbox overlap.
```

## Recommended Next Action

Continue to M29.3 relation graph:

```text
Does it preserve enough geometry/source relation to let M29.5 and later evidence gates prove icon-text-control structure?
Or is it mostly report-only geometry that cannot fix missing source objects?
```
