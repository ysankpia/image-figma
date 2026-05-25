# Image Math Boundary

`backend/app/image_math/` is a low-level execution package for pixel math. It exists to make expensive image operations fast, testable, and isolated. It is not a source-truth, replay, cleanup, materialization, or design-decision layer.

## Position In The System

```text
source PNG pixels
-> image_math execution helpers
-> raw metrics / masks / arrays / component metrics / RGBA bytes
-> M29 source truth layers decide meaning
```

The decision layers remain:

```text
raw M29 primitive graph: primitive physical evidence
M29.2 source ownership: visualKind / pixelOwner / replayDecision
M29.3 relation graph: source object relations
M29.5 replay plan: visible replay order, dedupe, cleanup authorization
M29 evidence contract: cross-evidence allow/report/reject for internal assets
M29 internal source promotion: only bridge back into M29.2 source objects
plan_materializer: consumer of final M29.5 plan only
```

## Allowed Imports

Only files under `backend/app/image_math/` may directly import:

```text
numpy
PIL
skimage
```

Only `backend/app/json_tools.py` may directly import:

```text
orjson
```

`rich` is dev/script-only and must not be imported under `backend/app/`.

## Package Responsibilities

```text
arrays.py
  PIL <-> NumPy conversion, RGB/RGBA normalization, uint8 validation, bbox clamp, array crop.

background.py
  edge/ring sampling, median RGB, RGB variance, background maps, foreground difference maps.

masks.py
  binary mask creation, boolean mask operations, area, bbox, overlap, IoU, containment, text mask expansion.

morphology.py
  remove small objects, binary open/close, dilate/erode, fill holes, optional mask smoothing.

components.py
  connected component labeling, region metrics, bbox, area, centroid, fill ratio, tiny component filtering.

alpha.py
  mask to alpha, soft alpha, apply alpha to crop, RGBA bytes, alpha coverage, foreground bbox.

debug.py
  diagnostic overlays, bbox overlays, mask overlays, preview images.

metrics.py
  luma, color distance, variance, edge strength, texture score, pixel difference metrics.
```

## Forbidden Responsibilities

`image_math` must not:

- decide `pixelOwner`;
- decide `visualKind`;
- decide `replayDecision`;
- authorize cleanup;
- create or mutate DSL nodes;
- change materializer output;
- infer component identity;
- infer Auto Layout permission;
- import M29 domain modules;
- import upload preview pipeline modules;
- import plan materializer modules;
- import Renderer or Figma plugin code;
- contain text literal, filename, path, brand, theme, sample-id, fixed coordinate, fixed bbox, or one-screenshot rules.

## Consumers

Domain modules may consume image_math only as execution helpers:

```text
visual_primitive
media_internal_decomposition
transparent_asset_report
png_tools
dsl_visual_comparison
ownership_conservation
```

Consumers must translate raw metrics through their own domain contracts. For example:

```text
image_math.components -> component metrics only
media_internal_decomposition -> internal candidate scoring and report-only decisions
transparent_asset_report -> alpha risk report only
M29.2 -> source ownership
M29.5 -> cleanup and replay authorization
```

## Migration Strategy

1. Introduce image_math with unit tests and import-boundary tests.
2. Keep production behavior unchanged.
3. Add parity tests before migrating any existing report-only implementation.
4. Migrate one hotspot at a time.
5. Run targeted tests, full backend tests, and artifact inspection for real-output changes.
6. Do not accept a migration if output changes are unexplained or if they improve one sample by specializing to that sample.

## Acceptance Questions

Before merging any image_math consumer change, answer:

```text
Does this change alter DSL output?
Does this change alter M29.5 replay plan output?
Does this change alter cleanup authorization?
Does this change alter materializer output?
Does this change add direct numpy/PIL/skimage imports outside image_math?
Does this change add text, path, filename, coordinate, bbox, theme, brand, or sample-specific logic?
Is there a parity or regression test covering the migrated behavior?
```
