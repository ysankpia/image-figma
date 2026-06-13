# Plan 193: Pencil export text and slice coordination

Status: active
Created: 2026-06-13

## Problem

The exported `project.zip/design.pen` can visually degrade when editable OCR text, confirmed slice images, and the raster remainder all touch the same UI control.

Observed sample:

```text
/Users/luhui/Downloads/project_mqc1wpkd_123c88b0-project
```

Concrete failures:

- text layers are emitted above confirmed slice image layers, so OCR text can visually cover nearby cut images or icons;
- text knockout paints a whole rectangle into the remainder using a surrounding-ring background sample;
- for colored buttons, the surrounding ring can sample the page background instead of the button surface, creating white blocks;
- the same wrong background estimate also makes button text color sampling choose button pixels instead of the white glyph color.
- colored control surfaces can be identified during text reconstruction but not emitted as shape/control layers in the `.pen`, so a rounded button can still look wrong even after remainder knockout is improved.
- page frames are emitted with `clip=false`, so Pencil `textGrowth:auto` layers can visually spill across neighboring frames on the global canvas.
- TypeScript M29 previously did not receive OCR blocks, so it could not emit OCR-backed `text_region`/text mask evidence or recover the old Go M29 text/surface lineage contract.
- short control labels can get wrong font size or x-position when the text reconstruction path treats OCR/foreground height as the whole control label geometry.
- tight normal text foreground, such as a page title, must not be misclassified as a control owner surface merely because the text pixels are dense.
- OCR can return a single line box that contains both a confirmed icon slice and the nearby label text. If that OCR box is used directly for Pencil text placement or font fitting, editable text overlaps the icon and the font size is inflated by the icon/control line box rather than the real glyph pixels.
- the current TypeScript path has received several partial repairs, but the remaining dense UI/text failures must not be solved by more isolated coefficient tuning before comparing against the older PSD-like/Codia pipeline that may already contain the correct placement and font-fitting contract.
- the old PSD-like oracle also contains a media-owned-text fallback, but that fallback is not the desired Slice Studio product contract for normal uncut UI areas. The desired contract is editable replacement: remove original glyph pixels from the remainder and place editable text back over the same text region while preserving the original background/control surface.

Historical reference check:

- `docs/plans/completed/179-slice-studio-m29-text-position-and-handoff-fixes.md` established the current rule: OCR owns text content, M29 owns physical bbox evidence.
- `docs/plans/completed/180-slice-studio-text-node-render-box-fix.md` explains why Slice Studio once switched from raw fixed-width-height boxes to `textGrowth:auto`. The current fix must not restore raw/tight fixed boxes, but the page 6 Pencil MCP check shows `auto` can produce huge layout boxes for dense editable text. The corrected contract is compact fixed render bounds, with expanded safe bounds kept as metadata/audit evidence instead of the visible Pencil text node box.
- `archive/legacy-code/services/pencil-python-backend/app/exporter/single_page.py` kept separate export modes and made visible OCR text an explicit handoff policy, but current Slice Studio has no full surface/vector layer owner. Therefore the immediate fix must tighten the current Pencil contract rather than hide M29/OCR output.
- `archive/legacy-code/services/psdlike-python` is now the oracle candidate for the next step. It must be run directly against the same failing page before further TS edits. If the old output is better, port the old behavior as a coherent contract instead of pulling isolated fragments.

## Scope

In scope:

- keep Slice Studio saved slices as export truth;
- improve local background sampling for text color and text knockout;
- keep editable OCR text where possible;
- make confirmed slice image layers visually win over overlapping editable text layers;
- make page frames clip overflowing children so editable text cannot pollute neighboring frames;
- add regression tests for colored button text color, colored button knockout, and frame clipping.
- pass OCR blocks into the TypeScript M29 physical evidence extractor as text-mask lineage;
- keep OCR-backed `text_region` as lineage only, not as physical bbox truth;
- add owner-aware control text sizing/placement for short labels while rejecting tight ordinary text as a false control owner.
- run the old PSD-like/Codia pipeline on `storage/projects/project_mqc1wpkd_123c88b0/originals/page_0006.png` with the same OCR evidence and inspect the generated preview/layer stack.
- compare the old oracle against the current TS export for text bbox, font size, owner surface, and overlap behavior.
- if the old oracle is materially better, migrate the corresponding text style fitting, owner-aware bbox, harmonization, and layer ownership logic to TypeScript as one coherent behavior.
- preserve the current product direction that OCR-visible text outside confirmed slice ownership should remain editable whenever possible.
- add a page-scoped Pencil export endpoint for fast validation of the failing page without changing the package schema.

Out of scope:

- default OCR provider changes;
- super-resolution or UpscalerJS preprocessing in the main export path;
- AI slice prompt changes;
- database changes;
- auth, ownership, billing, or plan 189 work;
- rebuilding UI controls as semantic shapes.
- making complex-region raster ownership the default text strategy for uncut UI areas.

## Expected Fix

Immediate execution rule:

```text
old pipeline oracle first
-> compare concrete output
-> only then port 1:1 or reject
```

Do not keep tuning thresholds in the current TypeScript path until the old pipeline has been run on the same page and judged with visible output.

Corrected product contract after oracle review:

```text
uncut UI text -> editable text replacement
confirmed slice text -> slice image remains final visible owner
OCR bbox -> default render/knockout region
M29/local foreground -> physical/color evidence, not a tight render box by default
solid owner surface -> optional text centering/fit context
outlined/background surfaces -> do not squeeze or shift text
```

The old media-owned-text behavior is useful evidence for why the previous output looked clean, but it must not become the mainline answer for ordinary uncut regions because the user needs editable text.

Use a local dominant-color estimate inside the text region before falling back to surrounding-ring sampling for ordinary text replacement.

Current policy update after P15/P16 gradient-button validation:

```text
filled non-background owner surface -> raster-owned control background
editable label on that surface -> fixed-bound text overlay
text knockout for that label -> skipped
Pencil vector control rectangle -> not emitted by default
```

This is intentionally conservative. It avoids turning gradients, shadows, rounded caps, and mixed button fills into inaccurate single-color vector rectangles. Owner-surface evidence is still useful for text alignment, sizing, and metadata, but it no longer means the source button background is removed from the remainder.

Set Pencil child order to:

```text
remainder
editable OCR text
confirmed slice images
```

This keeps saved slice images as the final visible owner when text and slices overlap. Raster button/control backgrounds remain in the remainder unless a future mask-grade surface owner is introduced.

The implementation now uses an explicit page render/ownership plan before
Pencil materialization:

```text
TextReconstruction + saved slices
-> PageRenderPlan
-> remainder text knockouts
-> Pencil nodes in declared z-order
```

The plan builder does not rerun OCR, M29, or project loading. It only converts
already-computed evidence into ownership instructions. `pencil-package` remains
an executor; it must not rediscover whether a region is a button/control.

Set Slice Studio page frames to:

```text
clip: true
```

This prevents a bad OCR/M29 text replay from leaking outside the source page frame in Pencil's global canvas.

Emit editable Pencil text with compact fixed render bounds:

```text
textGrowth: fixed-width-height
width/height: textRenderBBox
textAlignVertical: middle
lineHeight: omitted
```

Do not use raw OCR, tight M29 foreground, or expanded safe bounds as the final Pencil text node box. `placement` remains the source placement decision, `textRenderBBox` is the compact Pencil render box, `safeBBox` stays metadata/audit evidence, and `knockoutBBox` remains the glyph erase region.

Restore the old M29/OCR coordination rule:

```text
OCR block -> text content + text mask lineage
M29/local foreground -> physical text bbox evidence
confirmed slice bbox -> excluded from local text foreground measurement
owner surface -> short control label font cap and safe x/y placement
confirmed slice image -> final visible owner when overlapping text
```

Do not use OCR-backed `text_region` as a physical bbox. It records where OCR thinks text exists and lets TS M29 carry the same lineage as the old Go M29 path. Actual Pencil text placement should use the best physical glyph region when physical evidence is available, especially when OCR grouped a confirmed icon slice with the text. The source slice bbox is not an arbitrary gap rule; it is the asset-owned physical area that must be removed before measuring text foreground. Anti-aliased edge pixels around the saved slice are masked only for physical foreground measurement.

Font sizing must be based on the physical glyph bbox when available. OCR line height is line/control evidence, not font size truth, and it must not inflate small button/list labels.

Owner-aware control text must reject false positives where the candidate surface is only the tight text foreground itself. A filled candidate needs either real geometry outside the text bbox or strong outline evidence before it can cap font size or shift text placement.

## Validation

```bash
pnpm exec vitest run tests/pencil-exporter.test.ts
pnpm exec vitest run tests/m29-physical-evidence.test.ts tests/pencil-exporter.test.ts
pnpm run check
pnpm run build
git diff --check
```

Real-flow validation:

```bash
POST /api/projects/project_mqc1wpkd_123c88b0/export-project
inspect manifest/design.pen/remainder pixels
```

Latest full-export validation:

```text
Full package: /private/tmp/slice-full-export-fixed-1781354661/design.pen
Pencil frames: 28
Pencil layout: No layout problems
Visual screenshots: all 28 frames opened via Pencil MCP get_screenshot
```

Result:

- The fix is no longer limited to `page_0006`; the full export opens as a 28-frame Pencil document without whole-page collapse, cross-frame text spill, or large visible icon/text overpainting.
- The export is not a perfect closeout if the acceptance bar is zero text/slice geometry intersection. A manifest coordinate audit still finds intersections on 19 pages.
- Most remaining intersections are visible UI combinations where a text line and a confirmed icon slice naturally share one control row: search/filter icons, category icons, rating stars, VIP badges, and bottom navigation icons.
- Because slice image nodes are emitted above editable text nodes, these remaining intersections usually do not visually corrupt the page. They can still make Pencil layer hitboxes less clean than the source geometry ideally wants.
- Remaining visible defects are mostly OCR/content quality, not the page 6 geometry failure: examples include contact-field OCR on pages 13/14, status banner text on page 15, and some rating/status strings.

Generalized overlap rule validation:

```text
New full package: /private/tmp/slice-full-export-overlap-1781359903/design.pen
Backend restarted before export: yes
Project: project_mqc1wpkd_123c88b0
Pages: 28
Assets: 532
Pencil layout: No layout problems
```

Implementation adjustment:

- The page 6 blocker-aware foreground behavior is now a general overlap rule, not only an OCR-bbox fallback. If either the OCR bbox or the current physical/M29 bbox intersects a confirmed slice bbox, Slice Studio attempts local foreground measurement with the confirmed slice area masked out.
- The rule is geometry-based. It does not assume icons are on the left; regression tests cover left, right, top, and bottom icon positions.
- Over-broad `m29_foreground` candidates that include an icon can now be corrected by the same blocker-aware local foreground pass.
- The horizontal foreground filter was narrowed to reject true thin divider lines only, so a real text row inside a vertically broad OCR bbox is not discarded just because an icon sits above or below it.

Measured result:

```text
Before generalized rule:
pagesWithAnyOverlap=19
total text/slice intersections=73
large intersections=69

After generalized rule:
pagesWithAnyOverlap=7
total text/slice intersections=11
large intersections=9
```

Remaining intersections:

- `page_0004`: one tiny selected-check overlap.
- `page_0008`: bottom navigation active order icon/label.
- `page_0011`: rating star plus rating text.
- `page_0020`: rating stars plus rating text.
- `page_0021`: certification icon plus label.
- `page_0023`: rating star glyph/slice overlap.
- `page_0024`: illustration text crossing illustration slice.

These remaining cases are not the same main fault as page 6 icon+label layout drift. They are co-owned symbol/text regions or illustration-owned regions and should be handled with a separate rule only after visual acceptance is reviewed.

Rounded control knockout fix:

Observed follow-up issue:

- On P10/P11 service-list buttons such as `查看详情`, the visible Pencil output could show a rectangular green block that destroyed the button's right rounded corner.
- A smaller follow-up remained after splitting `safeBBox` and `knockoutBBox`: if the knockout bbox still touched a capsule button highlight or rounded edge, rectangular repaint could leave a hard flat protrusion above the editable text.

Concrete root cause:

- The OCR box for `查看详情` was not the main fault; it was reasonably close to the text.
- M29 did not provide a physical foreground box for that label, so the reconstruction path used OCR/local fallback.
- The exporter passed `layer.safeBBox` into `createRemainderPng` as the text knockout area.
- `safeBBox` is intentionally expanded for Pencil text layout so text does not clip, but using that same box for background repaint can touch button corners and repaint rounded outside pixels as a rectangular green fill.
- Even with a tighter `knockoutBBox`, repainting every pixel inside the box is still the wrong primitive for rounded or gradient controls. The desired operation is glyph erasure, not rectangular surface replacement.

Corrected contract:

```text
placement      -> source text placement decision
textRenderBBox -> compact Pencil text node size
safeBBox       -> metadata/audit bounds only
knockoutBBox   -> text foreground search region only
```

Implementation:

- `TextLayer` now carries `knockoutBBox`.
- `textKnockoutBounds()` chooses the tighter OCR/physical source box and adds only a small glyph-erase padding.
- `createRemainderPng()` now receives `layer.knockoutBBox` instead of `layer.safeBBox`.
- `createRemainderPng()` now estimates the local dominant background color, then repaints only pixels inside the knockout region that are foreground outliers from that background. It does not flatten the whole rectangle.
- The manifest records `knockoutBBox` for auditability.

OCR-anchored control surface fix:

Concrete root cause:

- The old PSD-like/Codia path did not merely repaint the remainder. It used OCR text as an anchor, sampled the nearby control support pixels, inferred a finite control surface, and emitted a shape/control layer before putting editable text over it.
- The current TypeScript path already detected a `textOwnerSurface`, but it sampled the surface fill from the broader search edge. On P10 `查看详情`, that produced `#fefefe` from the surrounding search/card area instead of the green button fill.
- Without an emitted shape/control surface, Pencil still depended on the raster remainder for the rounded button body. Any imperfect glyph knockout or layout expansion could show as a square patch or protrusion.
- The remaining P10 `搜索` failure had a deeper nested-control variant: the green outline of the outer search field was pixel-connected to the inner green search button, so a naive connected-component pass selected the wrong large owner or rejected the candidate after sampling white support pixels. The correct owner is the dense filled core around the text, not every thin connected stroke of the same color.

Corrected contract:

```text
OCR text bbox -> content and anchor
M29/local foreground -> glyph geometry and color evidence
support pixels around text inside owner surface -> control fill
thin connected outline strokes -> trimmed unless they have dense surface support
candidate with no real padding outside text -> not a control owner
filled non-background owner surface -> Pencil rectangle with preserved cornerRadius
editable text -> centered on that surface
saved slice image -> final visible owner if it overlaps
```

Implementation:

- `sampleControlSurfaceFill()` now samples left/right/top/bottom support pixels around the text inside the candidate surface, then falls back only if needed.
- `detectSeededFilledControlSurface()` now estimates the control fill from OCR text seed pixels, finds the connected surface, then trims it to the dense filled core using row/column support. This prevents an outer search field outline from swallowing the inner search button.
- `hasControlSurfacePadding()` rejects tight title/text foreground boxes and other no-padding components before they can become `filled_control_surface`.
- Accurate `local_foreground` text placement is no longer re-centered by a layout owner surface; the owner may still be recorded for audit/color context.
- Text color sampling can use a filled owner surface as the background, so white glyphs on colored buttons are not mis-sampled as the button fill.
- `inferControlCornerRadius()` estimates capsule/rounded-corner radius from the actual control corners.
- `pencil-exporter.ts` emits non-background `filled_control_surface` owner surfaces as rectangle nodes between the remainder and editable text.
- Editable text with a layout owner surface is center-aligned in the fixed safe text box.
- `validatePencilPackage()` now rejects a `.pen` where visible filled owner text lacks a matching control-surface rectangle below it.
- The manifest records `textOwnerSurface` and `textLayoutOwnerSurface` for post-export audit.

Validation:

```text
Focused tests: tests/pencil-exporter.test.ts now covers rounded-button safeBBox-vs-knockoutBBox behavior and glyph-only knockout on a rounded gradient button.
P10 page export: /private/tmp/slice-page10-knockout-fixed/design.pen
Full export: /private/tmp/slice-full-export-knockout-fixed-1781362382/design.pen
Glyph-only P10 page export: /private/tmp/slice-page10-glyph-knockout/design.pen
Glyph-only full export: /private/tmp/slice-full-export-glyph-knockout/design.pen
Pencil layout: No layout problems
Control-surface full export: /private/tmp/slice-full-export-control-surface-1781367105/design.pen
```

Latest control-surface validation:

```text
P10 `查看详情` owner surface:
  bbox: x=740 y=1127 width=136 height=49
  fill: #10b32f
  cornerRadius: 24
  exported node: page_0010__control_surface_0002

Full export:
  package: /private/tmp/slice-full-export-control-surface-1781367105/design.pen
  pages: 28
  assets: 532
  Pencil snapshot_layout(problemsOnly=true): No layout problems
  Visual screenshots checked: page_0006__frame, page_0010__frame, page_0011__frame
```

Plan-driven surface-knockout validation:

```text
Files:
  server/render-plan.ts
  server/render-plan-builder.ts

Contract:
  visible control surface bbox remains the Pencil rectangle bbox
  surface knockout keeps a separate source-owner cleanup instruction
  visible rounded shape is cleared from remainder
  owner band clears only source-owned pixels for the control surface
  text layers that generated a filled control surface do not also repaint text knockout pixels
  confirmed slices remain final visible owners above editable text

Real samples:
  /private/tmp/slice-plan-p10/design.pen
  /private/tmp/slice-plan-p11/design.pen

Pixel audit:
  P10 coloredSurfaceCount=5,totalSurviving=0
  P11 coloredSurfaceCount=5,totalSurviving=0

Pencil layout:
  page_0010__frame: No layout problems
  page_0011__frame: No layout problems
```

No-vector control-surface validation:

```text
Policy:
  filled owner surfaces remain raster-owned by default
  no Pencil `slice_studio_control_surface` rectangles are emitted
  no surfaceKnockouts are emitted from PageRenderPlan
  non-background filled owner labels skip textKnockout to avoid raster repaint artifacts
  ordinary/background text still uses textKnockout

Targeted page exports:
  project: project_mqc1wpkd_123c88b0
  pages: page_0010, page_0011, page_0015, page_0016
  result: all page exports passed
  Pencil snapshot_layout(problemsOnly=true): No layout problems

Full export:
  package: /private/tmp/slice-novector-full/design.pen
  frames: 28
  assets: 532
  editable text nodes: 1330
  control surface nodes: 0
  Pencil snapshot_layout(problemsOnly=true): No layout problems

Visual checks:
  P10/P11: no visible square button-edge protrusion in full-package screenshots
  P15: bottom `联系客服` remains a continuous raster gradient, not a split solid vector fill
  P16: no layout overflow in targeted/full-package screenshots

Validation:
  pnpm exec vitest run tests/pencil-exporter.test.ts
  pnpm run typecheck
  pnpm run check
  pnpm run build
  git diff --check
```

Root-cause correction after zoomed P10/P11 review:

```text
Observed symptom:
  Green button caps showed small rectangular green protrusions above the vector
  control surface in Pencil.

Rejected diagnosis:
  This was not caused by rembg/background-removal absence, OCR content failure,
  or an original source button bbox larger than the exported control surface.

Pixel evidence:
  original P10 x=748,y=597: [254,254,254,255]
  broken remainder x=748,y=597: [18,184,51,255]
  fixed remainder x=748,y=597: [254,254,254,255]
  fixed remainder true button interior x=760,y=600: [10,173,38,0]

Actual root cause:
  Text knockout ran before surface ownership cleanup and expanded the control
  label knockout by a small pad. Because the label background estimate was the
  green button fill, white pixels just outside the original button were treated
  as foreground text and repainted green. Surface cleanup could not remove those
  pixels because they were not source-owned green pixels; Slice Studio had
  created them during materialization.

Fix:
  buildPageRenderPlan() omits textKnockouts for text layers that already emit a
  non-background filled control surface. The vector control surface plus editable
  text own that region; there is no second text-background repaint pass for the
  same label.

Validation:
  pnpm exec vitest run tests/pencil-exporter.test.ts
  pnpm run typecheck
  pnpm run check
  pnpm run build
  git diff --check
  current-code page exports: page_0010 and page_0011
  full export: project_mqc1wpkd_123c88b0, 28 frames, 532 assets
  Pencil screenshots: page_0010__frame and page_0011__frame
```

Nested-control final validation after backend restart:

```text
Page export:
  endpoint: POST /api/projects/project_mqc1wpkd_123c88b0/pages/page_0010/export-project
  package: /private/tmp/slice-page10-current-fix/package/design.pen
  result: assetCount=30, pageCount=1
  Pencil snapshot_layout(problemsOnly=true): No layout problems

P10 `搜索` text layer:
  placement: x=785 y=161 width=92 height=59
  originalBBox: x=770 y=159 width=121 height=62
  knockoutBBox: x=789 y=162 width=82 height=53
  fontSize: 40
  color: #fcfffd
  owner surface: x=773 y=161 width=116 height=59
  owner fill: #0eb12f
  owner cornerRadius: 27

Full export:
  endpoint: POST /api/projects/project_mqc1wpkd_123c88b0/export-project
  package: /private/tmp/slice-full-current-fix/package/design.pen
  pages: 28
  assets: 532
  Pencil snapshot_layout(problemsOnly=true): No layout problems
  Visual screenshots checked: page_0010__frame, page_0006__frame
```

Validation commands:

```bash
pnpm exec vitest run tests/pencil-exporter.test.ts
pnpm exec vitest run tests/m29-physical-evidence.test.ts
pnpm run check
pnpm run build
git diff --check
```

Result:

- The root cause is fixed at owner selection: P10 `搜索` now uses the inner green filled button as the owner surface instead of the outer search field/outline.
- The fix is not page-specific and does not assume icon/text direction. It is based on OCR-seeded fill, dense surface support, and padding gates.
- OCR content mistakes remain outside this defect. This plan fixes geometry, owner surface, text color, and visible square/protrusion behavior.

Latest P10 pixel audit after backend restart:

```text
Button text layer: page_0010__text_0040 / 查看详情
Knockout bbox: x=753 y=1131 width=110 height=37
Changed pixels in whole knockout bbox: 1323 / 4070
Changed pixels in top edge band: 18 / 1100
Remainder crop: /private/tmp/slice-button-edge-analysis-glyph/02-remainder-3x.png
```

Oracle validation:

```bash
cd archive/legacy-code/services/psdlike-python
uv run python tools/run_one.py --image <repo>/storage/projects/project_mqc1wpkd_123c88b0/originals/page_0006.png --ocr <generated-old-ocr-json> --out /tmp/psdlike-page6-oracle
inspect /tmp/psdlike-page6-oracle/layer_stack.v1.json
inspect /tmp/psdlike-page6-oracle/*preview*.png
```
