# M29 Physical Evidence

M29 is the physical evidence layer. It sees pixels, OCR masks, primitive regions, local measurements, and relations. It does not own final Figma layer decisions.

## Role

M29 provides:

- source image dimensions and sha;
- OCR-aware text masks;
- connected components and primitive regions;
- bbox, mask, crop, color, edge, texture, and contrast measurements;
- physical relation graph;
- evidence tokens that Draft assembly can consume.

M29 does not provide:

- final Draft layers;
- final semantic controls;
- final z-order;
- final asset ownership;
- final Codia-like tree.

## Output Contract

Primary output:

```text
m29_physical_evidence.v1.json
```

Useful downstream facts:

```text
token id
token type
bbox
source primitive ids
text content if OCR-derived
measurements
compile hints
disposition
reasons
```

## Authority

M29 is usually the bbox authority for non-text visual evidence. OCR is usually the bbox authority for text. VLM is usually semantic authority, not physical bbox authority.

Draft assembly may refine M29 evidence, but it must keep source refs and a reason.

## Evidence, Not Product Structure

The following are evidence/hints:

```text
CanBeImage
CanBeIcon
CanBeLayerBackground
CanContainForeground
HasStableRectGeometry
TextureScore
EdgeDensity
CornerRadiusEstimate
ContainedByRasterID
```

They are not permission to emit a final layer by themselves. Draft assembly must decide ownership and pixel conflicts.

## Anti-Specialization

M29 logic must not depend on:

```text
file name
sample name
brand
visible text
fixed bbox
fixed coordinates
fixed screen size
task id
```

Thresholds should be derived from image scale or evidence measurements when possible. Hard-coded constants need local rationale and regression coverage.

## Relationship To Legacy Python M29

Python `/api/upload-preview` remains historical/reference on this branch. Go `internal/m29` is the Draft runtime evidence provider.

Do not patch Draft behavior in the Python materializer. If a Draft source ownership defect exists, fix Go M29, OCR integration, vision review, or Draft assembly.
