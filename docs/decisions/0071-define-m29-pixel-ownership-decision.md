# ADR: Define M29 Pixel Ownership Decision

- 状态：accepted
- 日期：2026-05-23

## Context

ADR 0070 defines how M29 compares two regions:

```text
relation(A, B) -> {
  primarySetRelation,
  secondaryGeometryRelations
}
```

That relation function is not enough. Once two regions overlap, contain each other, or nearly equal each other, M29 must decide which owner controls the final visible pixels.

The core question is:

```text
When two regions A and B conflict, who owns the source foreground evidence pixels?
```

Without this decision, M29 Direct Replay can produce duplicate visible pixels: editable text over copied image text, icon fragments over OCR text, or replay nodes over fallback.

## Decision

M29.2.1 introduces a pixel ownership decision layer.

The minimal owner set is:

```text
editable_text
raster_media
raster_icon
shape_geometry
fallback_only
diagnostic_only
```

Meanings:

```text
editable_text     -> ordinary UI text replayed as Figma text
raster_media      -> image/banner/poster/product image preserved as raster
raster_icon       -> compact icon replayed as one raster image
shape_geometry    -> stable color block, line, background, button/card geometry
fallback_only     -> visible only through fallback
diagnostic_only   -> evidence only, not replayed
```

The hard invariant is:

```text
one source foreground evidence pixel / replay foreground pixel can have only one replay owner
```

This does not forbid Figma layer overlap. A background shape can overlap its child text bbox because they own different source evidence: background pixels vs text foreground pixels. The invariant only forbids duplicate replay of the same source foreground evidence, such as the same text strokes appearing in editable text, copied raster media, and fallback.

This means the ownership layer must also decide:

```text
replayDecision
suppressedRegionIds
winnerReason
cleanupTargets
```

## No Global Owner Ranking

Do not implement ownership as a single static ranking:

```text
editable_text > raster_media > raster_icon > shape_geometry
```

That is wrong because ordinary UI text should become editable, but artistic text inside media should stay raster.

Ownership must be decided by scenario and relation evidence.

## Scenario A: Near-Equal Evidence

If two regions are near-equal:

```text
A ≈ B
```

They usually represent the same source object from different evidence providers.

Rules:

```text
trusted OCR text + M29 text/symbol/shape evidence
-> owner = editable_text
-> weaker region is suppressed as duplicate evidence

not trusted text
-> choose stronger evidence owner
-> weaker region remains sourceEvidence only
```

Exception:

```text
near-equal text region contained by strong raster_media
and evidence indicates image/artistic/internal media text
-> owner = raster_media
```

## Scenario B: Text Contained By Media

If:

```text
T = text candidate
R = media candidate
T contained_by R
```

Then M29 must choose between editable text and preserving the text in raster.

Ordinary UI text:

```text
owner(T) = editable_text
replayDecision = text_replay
cleanupTargets = copied_media_asset, fallback
```

Media/internal/artistic text:

```text
owner(T) = raster_media
replayDecision = preserve_in_parent_raster
cleanupTargets = []
```

Generic evidence for ordinary UI text:

```text
high OCR confidence
small text bbox relative to containing media
stable local background
not centered as the dominant media content
aligned or repeated with peer UI text
not strongly fused with high-texture image content
cleanup can be performed without an obvious artifact
```

Generic evidence for raster media text:

```text
inside large high-texture media
visually fused with image/poster/banner content
large or display-like text
unstable local background
no peer UI text relation outside the media
solid-fill cleanup would leave an obvious patch
```

These are media ownership rules, not product-image or banner-specific rules.

Editable text ownership requires cleanup feasibility. If text is inside high-texture or gradient media and the available cleanup strategy can only produce a visible solid patch, the text must be preserved in parent raster for the first implementation:

```text
owner(T) = raster_media
replayDecision = preserve_in_parent_raster
cleanupTargets = []
```

## Scenario C: Icon Fragments

If several small symbol/shape fragments are:

```text
near
aligned
similar color/stroke
inside a compact union bbox
```

Then:

```text
owner = raster_icon
replayDecision = icon_replay
original fragments = suppressed sourceEvidence
```

If fragments near-equal or highly overlap trusted OCR text:

```text
trusted ordinary OCR text -> owner = editable_text
not trusted text -> owner = raster_icon or diagnostic_only
```

This prevents icons from fragmenting into multiple shape layers and prevents text strokes from replaying as symbols.

## Scenario D: Shape With Text Or Media

Shapes must be split into two cases.

Background/container geometry:

```text
large or stable low-texture region
may contain text/image/icon children
owner = shape_geometry
can coexist behind child owners
```

Text-stroke or media-texture fragments:

```text
small stroke-like region
high overlap with OCR text or media texture
owner = editable_text / raster_media / diagnostic_only
shape replay is suppressed
```

Shape geometry can coexist with child objects only when it owns background pixels, not child foreground pixels.

## Fallback Rule

Fallback never wins ownership conflicts. It is the visual safety layer.

Rules:

```text
if a region is replayed as text/image/icon/shape:
  fallback cleanup can erase or cover that region

if a region is preserve_in_parent_raster / diagnostic_only / fallback_only:
  fallback must not erase it
```

Cleanup follows ownership. Cleanup does not create ownership.

## Required Decision Order

The first implementation should use this order:

```text
1. merge near_equal evidence
2. decide text contained by media
3. group and decide icon fragments
4. decide shape background vs stroke/texture fragments
5. apply fallback cleanup only for replay-safe objects
```

## Output Contract

Every source region after ownership decision must be able to report:

```json
{
  "id": "region_001",
  "bbox": [0, 0, 0, 0],
  "owner": "editable_text",
  "replayDecision": "text_replay",
  "relationsUsed": ["near_equal:region_008", "contained_by:region_012"],
  "winnerReason": "trusted_ocr_ui_text",
  "suppressedRegionIds": ["region_008"],
  "cleanupTargets": ["copied_media_asset", "fallback"]
}
```

For preserved media/internal text:

```json
{
  "id": "region_021",
  "bbox": [0, 0, 0, 0],
  "owner": "raster_media",
  "replayDecision": "preserve_in_parent_raster",
  "relationsUsed": ["contained_by:region_010"],
  "winnerReason": "text_inside_high_texture_media",
  "suppressedRegionIds": [],
  "cleanupTargets": []
}
```

## Definition Of Done

The ownership layer is defined when:

```text
every region has exactly one owner
every replayDecision follows from owner
every suppressed region has a reason
every cleanup target follows from ownership transfer
uncertain regions become diagnostic_only, not visible DSL nodes
source PNG and raw M29 assets are never modified
```

## Boundaries

- Do not hardcode product images, search boxes, bottom bars, carousels, or current sample coordinates.
- Do not let editable text globally beat raster media.
- Do not let fallback participate as a competing owner.
- Do not replay diagnostic-only evidence.
- Do not clean copied assets or fallback unless a replay-safe owner has taken over that region.
