# Integrations

Current product integrations support Slice Studio. Historical Figma plugin, Renderer, and Draft integrations remain documented here only for explicit deferred-runtime work.

## Slice Studio

Slice Studio integrates with:

- local browser UI through Next.js;
- local Elysia API;
- local SQLite and project file storage;
- Sharp for image decode/crop/compression;
- optional Baidu OCR for editable text content;
- TypeScript M29 physical evidence for tighter OCR text bboxes;
- OpenAI-compatible Responses API for AI slice boxes when configured.

These integrations produce or refine normal Slice Studio slices and export artifacts. They must not bypass saved SliceRecord truth.

## Figma

The historical plugin writes Draft Runtime DSL into Figma through `archive/legacy-code/packages/image-to-figma-renderer`.

Figma integration boundaries:

- Plugin Main calls Figma Plugin API.
- Renderer receives DSL and adapter methods.
- Backend never calls Figma API.
- Plugin UI iframe never calls Figma API directly.

## OCR

OCR is an evidence source. In current Slice Studio it provides text content and raw bbox for Pencil text overlays. In historical Draft it provides text evidence for TextLayer creation.

OCR evidence is used by:

- Slice Studio editable text overlays.
- Slice Studio M29 text bbox matching.
- Historical Draft TextLayer creation.
- Historical vision review context.

OCR does not own final grouping, z-order, or raster suppression decisions.

## Vision Models

Current Slice Studio AI slice boxes use `SLICE_STUDIO_AI_SLICE_*` configuration and return transient bbox suggestions.

Historical Draft vision models are provider-neutral. OpenAI-compatible Responses, Chat Completions, and local HTTP adapters are valid as long as they produce the configured candidate/review contracts.

Provider configuration:

```text
VISION_PROVIDER
VISION_WIRE_API
VISION_BASE_URL
VISION_MODEL
VISION_API_KEY
VISION_DETECTOR_CONCURRENCY
VISION_TIMEOUT_SECONDS
VISION_STREAM
VISION_REVIEW_ENABLED
```

Vision models provide candidates and review decisions. They do not generate final Figma trees and do not replace saved Slice Studio slices.

## Local Assets

Current Slice Studio writes local originals and export packages under root `storage/`.

The historical Go backend writes local crop assets for `RasterLayer` nodes.

Renderer fetches them from:

```text
/api/draft-preview/{taskId}/assets/{assetId}.png
```

Completed tasks must not expose unresolved visible raster assets.

## Codia Reference

Official Codia JSON samples are reference/eval inputs only:

```text
docs/reference/codia-samples/
archive/legacy-code/services/backend-go/internal/eval/codia
```

Generation packages must not read Codia samples or import eval packages.
