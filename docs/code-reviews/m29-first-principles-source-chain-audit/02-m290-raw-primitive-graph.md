# 02 M29.0 Raw Primitive Graph

## Source Truth

M29.0 raw primitive graph consumes:

```text
source PNG pixels
OCR text boxes converted to M29TextBox
M29VisualPrimitiveOptions thresholds
```

It outputs primitive evidence, not Figma-ready UI components:

```text
text
shape
image
symbol
unknown
blocked
containment relations
debug overlays
node asset crops
```

Main entrypoint:

```text
backend/app/visual_primitive_graph.py:113
```

The orchestrator calls it through:

```text
backend/app/upload_preview/stages.py:59-74
```

## Output Artifacts

Primary output:

```text
backend/storage/upload_previews/{taskId}/m29/nodes.json
```

The document includes:

```text
version
sourceImage
imageSize
nodes
relations
blocked
debug
warnings
meta
```

Type definitions:

```text
backend/app/visual_primitive/types.py
```

## Decision Authority

M29.0 is allowed to decide raw primitive evidence:

```text
raw node type: text / shape / image / symbol / unknown
raw node subtype
raw bbox
raw metrics
raw confidence
raw reasons
blocked primitive reasons
raw containment relation
```

M29.0 is not allowed to decide:

```text
pixelOwner
visualKind
replayDecision
cleanupTargets
visible replay
promotion
Figma component/group/Auto Layout
```

Those decisions belong downstream, mainly M29.2 and M29.5.

## Runtime Order Inside M29.0

The current extraction order is:

```text
1. decode PNG pixels
2. build OCR text nodes
3. build text exclusion mask
4. build global foreground mask
5. connected components over initial foreground
6. detect shapes
7. detect low-contrast support regions
8. detect images and image-like unknowns
9. detect text-support backgrounds
10. remove images overlapping text-support shapes
11. build image protection mask
12. build remaining foreground mask
13. connected components over remaining foreground
14. detect symbols or blocked fragments
15. add blocked_inside_images
16. export node assets
17. build containment relations
18. write debug artifacts and nodes.json
```

Code evidence:

```text
backend/app/visual_primitive_graph.py:130-185
```

## Main Formulas And Gates

### Text mask

OCR text boxes are padded and masked before foreground extraction:

```text
build_text_exclusion_mask(width, height, text_boxes, padding)
```

Code evidence:

```text
backend/app/visual_primitive/components.py:10-11
```

This is correct as a primitive rule: text strokes should not become symbols. The information loss is that UI foreground close to text can be hidden if OCR boxes are too large or padded too aggressively. That is usually repaired downstream through raw text nodes, not by making symbols overlap text.

### Global foreground mask

Foreground is defined by distance from a global background estimate:

```text
background = estimate_global_background(pixels)
FG(p) = color_distance(rgb(p), background) > 42 and not near_white(rgb(p))
```

Code evidence:

```text
backend/app/visual_primitive/components.py:14-26
backend/app/visual_primitive/components.py:29-43
```

This is a major first-principles risk. It assumes a page-level background sampled from corners/top/bottom is meaningful. On complex mockups, dark screens, banners, hero graphics, cards, or media regions, local foreground/background contrast is not represented by this global model.

Consequence:

```text
1. Large complex areas become one connected image component.
2. Internal UI inside that area can be swallowed into image protection.
3. Later symbol detection sees fragments as inside_image_primitive.
```

This matches real symptoms such as media-contained button/icon/tab fragments not becoming selectable.

### Connected components

Connected components use 8-neighbor flood fill and drop areas smaller than `min_area` or larger than `image_area * max_area_ratio`:

```text
area < min_area -> discard
area > max_area -> discard
```

Code evidence:

```text
backend/app/visual_primitive/components.py:46-101
```

Options:

```text
min_component_area = 16
max_component_area_ratio = 0.25
```

Code evidence:

```text
backend/app/visual_primitive/types.py:147-150
```

Important nuance:

```text
initial_components uses max(options.max_component_area_ratio, 0.80)
remaining_components uses options.max_component_area_ratio
```

Code evidence:

```text
backend/app/visual_primitive_graph.py:133-138
backend/app/visual_primitive_graph.py:148-153
```

This is intentional enough to catch large media early, but it also creates a size-regime behavior: large connected areas are allowed before image detection but not after image protection. That is a mathematical threshold, not literal sample specialization, but it is a likely hidden abstraction boundary to review later.

### Shape detection

`detect_shapes` classifies line, ellipse/circle, and rect-like components using geometry fit and low texture/color complexity:

```text
line_like -> separator
ellipse/circle geometry -> badge_background / small_ellipse
rect + is_rect_like -> rect subtype
```

Code evidence:

```text
backend/app/visual_primitive/detectors.py:36-85
backend/app/visual_primitive/geometry.py:11-25
backend/app/visual_primitive/geometry.py:28-79
```

This is valid primitive evidence. It should not be treated as final source ownership; M29.2 must still decide replay safety and visual kind.

Specialization risk:

```text
badge_background if area < 3200
ellipse only if area < 10000
circle ratio 0.85..1.18
```

These are not text/brand/file special cases, but they are size-regime heuristics. They need regression coverage for small markers and bottom tab selected indicators, because too-small or too-large shapes may shift categories.

### Image detection

`detect_images` scores image candidates with area, text overlap, protective shape overlap, color count, texture, fill ratio and edge score:

```text
if area < min_image_area or text_overlap > 0.08 or shape_overlap > 0.35:
  score = 0
else:
  score = 0.45
  + color_count bonus
  + texture bonus
  + fill_ratio bonus
  + edge_score bonus
```

Code evidence:

```text
backend/app/visual_primitive/detectors.py:87-133
backend/app/visual_primitive/detectors.py:235-246
```

If score passes `image_accept_threshold`, the component becomes `image` with reason `conservative_image_accept`. If it is large/colorful but below threshold, it becomes `unknown` / `image_like_low_confidence`.

This is the first major owner-risk point:

```text
raw image nodes trigger image protection mask.
internal components inside accepted image are later blocked as inside_image_primitive.
```

### Image protection and blocked internal fragments

Accepted images create image protection masks:

```text
image_mask = build_image_protection_mask(...)
foreground = build_remaining_foreground_mask(... image_mask ...)
```

Code evidence:

```text
backend/app/visual_primitive_graph.py:146-154
backend/app/visual_primitive/components.py:104-123
```

Symbols overlapping image mask are blocked:

```text
if imageOverlapRatio > 0:
  inside_image_primitive
```

Code evidence:

```text
backend/app/visual_primitive/detectors.py:171-210
```

The pipeline also adds blocked entries for components contained by images:

```text
blocked_inside_images([*initial_components, *remaining_components], images)
```

Code evidence:

```text
backend/app/visual_primitive_graph.py:154-155
backend/app/visual_primitive/detectors.py:225-233
```

This is defensible for preserving complex media, but it is exactly where media-contained UI foreground can become diagnostic-only unless later M29.6 recovers it. It is not a downstream materializer problem.

### Symbol detection

Remaining components become symbols if they are small enough, not text-overlapping, not image-overlapping, not protective-shape-overlapping, and have simple enough color/texture:

```text
color_count <= symbol_color_threshold
or texture_score <= symbol_texture_threshold
```

Code evidence:

```text
backend/app/visual_primitive/detectors.py:135-169
backend/app/visual_primitive/detectors.py:194-220
backend/app/visual_primitive/detectors.py:248-257
```

Options:

```text
symbol_min_area = 16
symbol_max_area = 12000
symbol_texture_threshold = 0.20
symbol_color_threshold = 24
```

This can fail in two opposite ways:

```text
1. multicolor icon has color_count too high and becomes blocked.
2. tiny selected marker or tab dot is below area or line-like and becomes blocked.
```

Again, this is not literal specialization, but it is a hidden size/color regime that can make "small things not recognized".

### Low-contrast support detection

Low-contrast support exists to recover finite support backgrounds near text and foreground evidence. It requires:

```text
text bbox
same-line non-text foreground evidence
bounded support size
stable low texture/color fill
complete outer ring
minimum boundary delta
horizontal aspect
```

Code evidence:

```text
backend/app/visual_primitive/support.py:16-74
backend/app/visual_primitive/support_scoring.py:22-136
```

This is a good first-principles move: it avoids semantic rules like "search bar" and instead proves finite support by local geometry and boundary evidence.

But it has a structural limitation:

```text
It needs OCR text plus line evidence.
It will not recover a media-contained button background if the background was swallowed into an accepted image and no finite outer ring can be sampled.
```

### Text-support background detection

Text-only pill/background recovery searches expanded boxes around OCR text and requires:

```text
text containment >= 0.90
support area ratio in configured range
aspect >= min aspect
low texture/color
complete boundary deltas
no accepted image overlap
```

Code evidence:

```text
backend/app/visual_primitive/support.py:76-130
backend/app/visual_primitive/support_scoring.py:138-214
```

This helps finite control backgrounds that have stable local fill, even without a side icon. It is also guarded against plain page text and textured media by tests.

## Tests / Guards

Current regression matrix explicitly covers finite support and text support:

```text
docs/engineering/m29-contract-regression-matrix.md:26-34
docs/engineering/m29-contract-regression-matrix.md:58-59
```

Relevant tests include:

```text
backend/tests/test_visual_primitive_graph.py::test_low_contrast_support_region_is_detected_from_text_evidence
backend/tests/test_visual_primitive_graph.py::test_low_contrast_support_region_is_detected_on_dark_theme
backend/tests/test_visual_primitive_graph.py::test_low_contrast_support_region_does_not_swallow_textured_media
backend/tests/test_visual_primitive_graph.py::test_text_support_background_region_is_detected_from_text_only_pill
backend/tests/test_visual_primitive_graph.py::test_text_support_background_region_is_not_for_plain_page_text
backend/tests/test_visual_primitive_graph.py::test_text_support_background_region_rejects_accepted_media_overlap
backend/tests/test_source_ui_physical_graph.py::test_text_support_background_shape_replays_as_control_background
```

## Information Loss

### Loss 1: global background model loses local contrast

The first foreground mask is based on a single global background estimate. This loses local background context in complex media/card/banner regions.

Impact:

```text
internal media UI foreground may merge into a large image component
or disappear if too close to local background but far from global background assumptions
```

Owner layer:

```text
raw_m29 / image_math / M29.6 internal decomposition
```

Not owner:

```text
materializer
Renderer
plugin
```

### Loss 2: image protection intentionally suppresses internal components

Accepted image regions protect their interior from symbol detection. This preserves visual stability, but shifts internal UI extraction responsibility to M29.6.

Impact:

```text
button/icon/tab/marker inside media will not become a raw symbol source object unless M29.6 recovers it later.
```

### Loss 3: size/color thresholds act as implicit regimes

The code has thresholds for:

```text
min/max component area
shape area
symbol area
symbol color/texture
image color/texture
ellipse/circle area and ratio
support width/height/area/aspect
```

These are normal math parameters, but they can become hidden specialization if the system repeatedly changes them to pass one batch. The right fix is not "remove thresholds"; it is to document intended domain, add tests, and use multi-evidence gates downstream.

## Known Failure Symptoms Mapped To This Layer

### Text editable, icon not selectable

Likely path:

```text
raw M29:
  icon fragment is inside accepted image -> blocked_inside_images / inside_image_primitive

M29.6:
  may recover as internal_icon_candidate

transparent/evidence/promotion:
  may still block visible replay
```

M29.0 is often the first place the icon stops being a normal `symbol`.

### Button label editable, whole button not draggable

Likely path:

```text
text node exists from OCR
finite button background is swallowed into image component
text_support_background cannot recover because candidate overlaps accepted image
M29.2 has no control_background source object
M29.5 has nothing to replay as draggable background
```

M29.0 contributes if accepted image detection is too coarse or if no local finite support candidate is emitted.

### Bottom tab selected marker / table dot missing

Likely path:

```text
small marker below symbol_min_area
or line_like blocked
or inside_image_primitive
or color_count/texture fails symbol gate
```

Raw M29 can lose these as normal symbols. M29.6 may need repeated small-object / marker evidence to recover them.

## Findings

### P1: Accepted image protection is a correct fallback but a major internal UI information-loss point

Owner layer:

```text
raw_m29 + m29_6_internal_decomposition
```

Evidence:

```text
backend/app/visual_primitive_graph.py:142-155
backend/app/visual_primitive/detectors.py:194-210
backend/app/visual_primitive/detectors.py:225-233
```

Problem:

```text
Once a large composite region is accepted as image, internal UI fragments stop being ordinary symbol candidates.
This is visually conservative, but it forces M29.6/transparent/evidence/promotion to recover internal elements later.
If M29.6 only reports candidates and promotion gate blocks them, final Figma loses selectability.
```

Do not fix by:

```text
lowering image_accept_threshold for one sample
allowing materializer to invent icons inside image
letting Renderer/plugin split bitmap content
```

Recommended next action:

```text
Audit M29.6 and evidence/promotion before changing raw image gate.
If raw M29 changes are needed, prefer reportable "composite_media_with_internal_ui_evidence" facts over weakening preserve_raster globally.
```

### P2: Global foreground mask is too coarse for local UI object decomposition

Owner layer:

```text
raw_m29 / image_math
```

Evidence:

```text
backend/app/visual_primitive/components.py:14-43
```

Problem:

```text
Foreground is relative to global edge/corner background, not local background.
This is not enough for media-internal decomposition, dark UI cards, gradient banners, or local control backgrounds.
```

Recommended next action:

```text
Do not immediately replace it in raw M29.
First audit whether M29.6's local foreground extraction already owns the local-background problem.
If not, define a shared image_math local foreground primitive that remains evidence-only.
```

### P2: Size/color regimes need explicit anti-specialization ledger

Owner layer:

```text
raw_m29 / docs_or_tests
```

Evidence:

```text
backend/app/visual_primitive/types.py:147-158
backend/app/visual_primitive/detectors.py:51-62
backend/app/visual_primitive/detectors.py:151-168
backend/app/visual_primitive/support_scoring.py:72-126
```

Problem:

```text
Thresholds are not automatically wrong. But "small / medium / large" gates can behave like hidden specialization if not tied to evidence contracts and regression cases.
The user concern that early M29 has size-based specialization is valid as an audit target.
```

Recommended next action:

```text
Create 15-specialization-and-heuristic-ledger.md later in this audit.
For every threshold, record intended domain, non-domain, current tests, and observed failure class.
```

### P2: Text-support background correctly avoids accepted media, but that means media-contained buttons need another path

Owner layer:

```text
raw_m29 + m29_6_internal_decomposition
```

Evidence:

```text
backend/app/visual_primitive/support.py:96-98
backend/app/visual_primitive/support_scoring.py:185-214
backend/tests/test_visual_primitive_graph.py::test_text_support_background_region_rejects_accepted_media_overlap
```

Problem:

```text
Rejecting accepted media overlap is correct for preventing textured media from becoming fake controls.
But for a real button inside composite media, raw M29 will not produce control_background.
That demands a later media-contained control/background evidence path.
```

Recommended next action:

```text
Audit M29.6 for internal control-background candidates, not just icon/text candidates.
```

## Recommended Next Action

Proceed to M29.2 source ownership audit.

Why:

```text
Raw M29 emits evidence but not replay authority.
The next layer decides whether raw shapes/images/symbols/text become editable text, shape_geometry, raster_icon, preserve_raster, or diagnostic_only.
Most visible "why is it not draggable/selectable" questions become explicit at M29.2.
```
