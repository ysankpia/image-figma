# M29 Physical Evidence

M29 is the physical evidence layer. In current Slice Studio, the default implementation is the TypeScript extractor under `apps/slice-studio/server/m29-physical-evidence/`, used only to improve OCR text bbox placement. Go M29 remains reference/fallback tooling.

M29 sees pixels, primitive regions, local measurements, and optional OCR line context. It does not own final visible asset decisions.

## Role

M29 provides:

- source image dimensions and sha;
- OCR-aware text masks;
- connected components and primitive regions;
- bbox, mask, crop, color, edge, texture, and contrast measurements;
- physical relation graph;
- physical bbox evidence that Slice Studio text reconstruction can consume;
- historical evidence tokens that Draft assembly can consume.

M29 does not provide:

- final Slice Studio slices;
- final Draft layers;
- final semantic controls;
- final z-order;
- final asset ownership;
- final Codia-like tree.

## Output Contract

Current Slice Studio output:

```text
M29PhysicalEvidence
schemaVersion: ts.v1
```

Historical Go Draft output:

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

In Slice Studio, saved SliceRecord boxes are the visible asset authority. OCR is the text-content authority. TypeScript M29 physical evidence can refine OCR text bbox placement, but it cannot create or delete saved slices.

In historical Draft, M29 was usually the bbox authority for non-text visual evidence. VLM was semantic authority, not physical bbox authority.

Any downstream use must keep source refs and a reason.

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

They are not permission to emit a final layer or slice by themselves. Current Slice Studio requires saved slices for visible assets; historical Draft assembly must decide ownership and pixel conflicts.

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

## Relationship To Legacy M29

Python `/api/upload-preview` remains historical/reference on this branch. Go `internal/m29` and `cmd/m29extract` are retained as research/reference and explicit fallback.

Do not patch Slice Studio output in old Python materializers or Go Draft assembly. If current text placement is wrong, fix `apps/slice-studio/server/m29-physical-evidence/`, `m29-text-locator.ts`, OCR integration, or text reconstruction.
