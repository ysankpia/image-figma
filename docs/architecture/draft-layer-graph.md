# Editable Layer Graph

`editable_layer_graph.v1.json` is the core backend contract. It expresses editable Figma layers after OCR, M29 physical evidence, vision candidates, and review decisions have been reconciled.

It is not a Codia tree, not a semantic UI control tree, and not a Figma internal canvas JSON clone.

## Goals

- Preserve editable text when source evidence supports text.
- Preserve local raster objects such as icons, avatars, covers, thumbnails, illustrations, and artistic text when they should remain image layers.
- Preserve editable surfaces such as card backgrounds, button bases, separators, and simple filled shapes.
- Group related layers so regions can be moved together.
- Avoid duplicate visible pixels.
- Keep every decision auditable.

## Layer Kinds

First-version layer kinds:

```text
Page
ReferenceImage
TextLayer
RasterLayer
ShapeLayer
GroupLayer
```

Do not add `Button`, `ListView`, `BottomNavigation`, `ActionBar`, `EditText`, `Component`, `Instance`, or `AutoLayout` as first-version layer kinds. Use `semanticTags` for those hints.

## Minimal Shape

```json
{
  "version": "editable_layer_graph.v1",
  "image": {
    "path": "/path/source.png",
    "width": 665,
    "height": 1440,
    "sha256": "..."
  },
  "layers": [
    {
      "id": "layer_0001",
      "kind": "TextLayer",
      "bbox": {"x": 40, "y": 120, "width": 180, "height": 32},
      "z": 12000,
      "text": {"characters": "确认协议并支付"},
      "semanticTags": ["button_label"],
      "sourceRefs": [
        {"kind": "ocr", "id": "ocr_0012"}
      ],
      "decision": {
        "state": "emit",
        "bboxAuthority": "ocr",
        "reason": "ocr_text_promoted"
      }
    }
  ],
  "groups": [
    {
      "id": "group_0001",
      "kind": "RegionGroup",
      "semanticTags": ["bottom_navigation"],
      "bbox": {"x": 0, "y": 1280, "width": 665, "height": 160},
      "childLayerIds": ["layer_0101", "layer_0102"]
    }
  ],
  "summary": {
    "layerCount": 1,
    "groupCount": 1
  }
}
```

## BBox Authority

Allowed `bboxAuthority` values:

```text
source_image
m29
ocr
vision
review
children_union
derived
```

Default authority order:

```text
M29/OCR physical bbox > VLM semantic label
```

VLM can classify or recommend. It should not override physically supported bbox without a review decision and an audit reason.

## Decision States

Allowed decision states:

```text
emit
consume
suppress
refine
hint
reference_only
```

Every emitted layer needs `sourceRefs` and `decision.reason`. Suppressed and consumed candidates must be preserved in reports when they affect output.

## Z-Order

Within a local region:

```text
ShapeLayer
RasterLayer
TextLayer
GroupLayer metadata only
```

Text must render above same-region raster/shape layers. Reference images must not participate in visible z-order.

## Pixel Ownership Invariants

The graph should satisfy:

- No visible full-page screenshot backing.
- No visible body-scale backing under editable children.
- No visible text layer substantially covered by a raster layer.
- No unresolved raster asset.
- No large unauthorized overlap between sibling visible layers.
- Shape layers should not contain foreground text pixels.

When these invariants cannot be satisfied, the assembler should prefer a conservative visible owner and write the failure into `draft_validation_report.md` instead of hiding it in the renderer.

## Group Semantics

Groups are movement/organization hints. They do not own pixels and do not replace layers.

Useful first-version group tags:

```text
top_region
content_section
card
list_row
bottom_navigation
floating_region
button_like
```

Group tags are allowed to be imperfect. Visible layer ownership must remain conservative and auditable.
