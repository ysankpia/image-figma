# Image-to-Figma Renderer

Renderer turns backend-approved Draft Runtime DSL into Figma nodes. It does not decide layer ownership.

## Public Interface

Draft renderer entrypoint should be:

```ts
renderDesign(dsl, options)
```

`options` must provide `FigmaAdapter`. Renderer does not directly depend on global `figma`; real Figma API access is encapsulated by the adapter.

Return result:

```text
success
rootNodeId
renderedElementCount
warnings
errors
```

## Responsibilities

Renderer should:

- validate DSL shape lightly;
- build an asset index;
- create root frame;
- render frame/group/text/shape/image/line;
- apply absolute layout, fill, stroke, radius, opacity, and visibility;
- load image assets;
- preserve DSL z-order;
- report warnings.

## Non-Responsibilities

Renderer must not:

- run OCR;
- call vision models;
- crop source PNG;
- infer ownership;
- decide emit/consume/suppress;
- read Codia golden;
- restore visible full-image backing;
- hide backend duplicate-pixel bugs;
- implement sample-specific layer suppression;
- infer Auto Layout or components.

## Layer Policy

- Root frame uses page dimensions.
- Layer names prefer DSL `name`, then `type` and `id`.
- Text should render above lower-z siblings as supplied by DSL.
- `ReferenceImage` is hidden/locked or omitted from visible output.
- A visible image node with missing asset should produce a warning.
- Single element failure should not abort the entire page.

## Warning Policy

Important warnings:

```text
IMAGE_LOAD_FAILED
DRAFT_ASSET_NOT_FOUND
DRAFT_TEXT_COVERED
DRAFT_UNAUTHORIZED_OVERLAP
DRAFT_REFERENCE_IMAGE_VISIBLE
```

Warnings are evidence. If a warning indicates backend ownership or asset failure, fix Draft assembly/export/asset, not renderer cosmetics.

## Removed Legacy Renderer Notes

Old Codia Runtime renderer entrypoints have been removed from the public Renderer surface. New behavior must route through Draft Runtime DSL and the Draft renderer.
