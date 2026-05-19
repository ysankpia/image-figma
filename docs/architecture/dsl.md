# DSL v0.1

DSL v0.1 是后端 M30 materialization 和 Figma Renderer 之间的稳定合同。

```text
M29 trusted evidence
-> M30 materialized DSL
-> Renderer
-> Figma nodes
```

OCR、M29 evidence、audit reports 和 storage artifacts 都不是 Renderer 输入。Renderer 只消费 DSL。

M31 Reconstruction UI Tree 也不是 Renderer 输入。它是 M29 后面的诊断组织层，用来验证 primitive ownership、reconstruction unit fallback 和后续 layer recovery 的可行性。M31 不改 DSL schema。

## Top-Level Shape

DSL 顶层必须包含：

```text
version
taskId
page
assets
root
meta
```

`version` 当前固定为 `"0.1"`。

## Element Types

v0.1 schema 支持：

```text
frame
group
text
shape
image
icon
line
```

当前 M30 upload path 只允许 materialize visible:

```text
frame
text
shape
image
line when already present in base DSL
```

M30 upload path must not emit visible `icon` nodes. Safe visual assets are represented as `image` nodes because the current renderer path does not need a separate icon materialization type.

Every element needs:

```text
id
type
layout
```

Common optional fields:

```text
role
name
style
content
source
imageFill
children
meta
```

## Layout

v0.1 uses absolute pixel layout:

```text
x
y
width
height
```

M30 must not infer Auto Layout, responsive constraints, Hug Content, Fill Container, or component structure from a PNG.

## Assets

Image nodes reference `assets` through `assetId`.

M30 preview publishes local image assets under:

```text
storage/assets/{taskId}/m30/
/files/assets/{taskId}/m30/...
```

Asset URLs returned to the plugin must be fetchable by the Figma renderer.

## Fallback

Fallback is part of the contract, not a failure.

Bootstrap M30 DSL uses:

```text
root frame
  original_reference hidden
  full_image_fallback visible
  m30_shape_candidate*
  m30_visual_asset*
  m30_text_cover*
  m30_text_member*
```

Augment-existing mode preserves the input DSL and appends M30 nodes above existing fallback. It does not modify the base DSL in place.

M30.2 conservative text cover keeps the fallback visible and adds ordinary `shape` nodes under materialized text only when background sampling is safe.

M30.2 does not:

```text
hide fallback
mask fallback regions
inpaint
delete original_reference
delete existing fallback nodes
```

## M30 Node Roles

Current visible roles:

```text
m30_text_member
m30_text_cover
m30_shape_candidate
m30_visual_asset
```

### Text

M30 text nodes come from M29.0.5 `textMembers`.

Required trace in `meta`:

```json
{
  "m30Materialized": true,
  "sourceKind": "m2905_text_member",
  "sourceTextMemberId": "...",
  "sourceTextBoxId": "...",
  "sourceEvidenceNodeId": "...",
  "sourceObjectId": "...",
  "sourceBBox": [0, 0, 0, 0],
  "ocrConfidence": 0.91,
  "materializationConfidence": "medium",
  "riskFlags": []
}
```

### Text Cover

Text cover nodes are ordinary `shape` nodes:

```json
{
  "type": "shape",
  "role": "m30_text_cover",
  "style": {
    "visible": true,
    "opacity": 1,
    "fill": "#ffffff"
  }
}
```

They reuse the source text bbox. They do not count as new detected bboxes.

### Shape

M30 shape nodes come from safe M29.0.5 `shapeCandidates`.

They should only be emitted when fill/style evidence is reliable. If a shape has no reliable fill/radius/stroke, M30 skips it and records the reason in the report.

### Image

M30 image nodes come from safe M29.0.5 `visualAssets`.

They must use:

```text
type = image
source.assetId = registered asset id
imageFill.mode = fit or the safest supported value
```

## Audit-Only Evidence

The following may appear in reports or DSL meta references, but must not become visible children:

```text
mixed_symbol_text_candidate
future_promotable_uncertain_symbol_candidate
candidate_for_future_uncertain_review
keep_mixed_symbol_text_conflict
text_owned_rejected_lineage audit examples
residual mixed review output
M29.1.3 classification output
M29.0.3.2 review output
```

This rule is the main safety gate between evidence/audit world and Renderer-visible DSL.

## M32 Boolean Subtract Masking

To support clean, high-fidelity editable UI reconstruction without text ghosting (double rendering), the system supports Figma-side Boolean Subtraction.

- **DSL Meta Extension**: For image/fallback elements (e.g., `fallback_region_*`), the backend collects the absolute bounding boxes of all successfully materialized/editable text or icon layers and registers them in the `meta` object under the `maskBBoxes` key.
- **Format**:
  ```json
  "meta": {
    "maskBBoxes": [
      [10, 10, 40, 12],
      ...
    ]
  }
  ```
- **Coordinate Space**: The bounding box coordinates are stored in absolute page coordinates. This allows the Figma Renderer to construct mask nodes directly without having to compute relative offsets or coordinate space transformations.

## Removed Legacy DSL Paths

M30.2.2 removed the old pre-M29 upload chain. DSL patch, visible text replacement, component annotation, slice candidate, icon fallback replay, perception, and SAM harness outputs are historical and no longer part of the active upload DSL path.

Historical behavior remains in ADRs, archived plans, and git history.
