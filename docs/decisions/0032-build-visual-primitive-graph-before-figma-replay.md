# ADR 0032: Build Visual Primitive Graph Before Figma Replay

## Status

Accepted.

## Context

M20-M28 produced useful evidence around icon crops, business candidates, visual provider benchmarks, SAM2 mask filtering, and single-image object extraction. That work also exposed the wrong abstraction: a screenshot-to-Figma system cannot start from "crop all icons". PNG screenshots are flattened render outputs, so the next durable layer must separate pixels into design primitives before any Figma replay.

The repository already has `backend/app/visual_primitives.py` from M8. That contract is part of the upload pipeline and is consumed by OCR patching, text binding, and component structure stages. Replacing it would create a broad migration and risk the stable fallback DSL path.

## Decision

M29 introduces a separate script-only visual primitive graph harness:

```text
PNG -> text / shape / image / symbol / unknown primitive graph
```

It does not replace M8 `/primitives`, does not add API/DB tables, and does not enter the upload pipeline. It writes local evidence under `backend/storage/m29_visual_primitive_graph*`.

M29 keeps deterministic pixel processing as the main path:

- bbox and mask utilities use explicit `[x, y, width, height]` and row-major binary mask semantics;
- text boxes are exclusion inputs, not OCR provider work;
- obvious shape detection runs before conservative image protection;
- image protection is accepted only at high confidence;
- symbol detection runs only on remaining foreground;
- overlays and preview sheet are required evidence.

## Consequences

- The project now has a clean bridge from low-level PNG pixels to future Figma reconstruction without disturbing M8-M28 upload stages.
- M29 can fail, over-filter, or under-detect during experimentation without changing DSL/Figma output.
- M30 can focus on symbol mask/vectorization, M31 on layout/component graph reconstruction, and M32 on DSL/Figma replay.
- Future migration from M8 `VisualPrimitiveDocument` to a richer primitive graph must be a separate decision after M29 evidence is reviewed.
