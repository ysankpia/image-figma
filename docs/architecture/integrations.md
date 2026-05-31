# Integrations

Current integrations support the Editable Draft pipeline.

## Figma

The plugin writes Draft Runtime DSL into Figma through `packages/image-to-figma-renderer`.

Figma integration boundaries:

- Plugin Main calls Figma Plugin API.
- Renderer receives DSL and adapter methods.
- Backend never calls Figma API.
- Plugin UI iframe never calls Figma API directly.

## OCR

OCR is an evidence source for Draft. It provides text, bbox, and confidence.

OCR evidence is used by:

- M29 text mask exclusion.
- Draft TextLayer creation.
- Vision review context.

OCR does not own final grouping, z-order, or raster suppression decisions.

## Vision Models

Vision models are provider-neutral. OpenAI-compatible Responses, Chat Completions, and local HTTP adapters are valid as long as they produce the configured candidate/review contracts.

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

Vision models provide candidates and review decisions. They do not generate final Figma trees.

## Local Assets

The Go backend writes local crop assets for `RasterLayer` nodes.

Renderer fetches them from:

```text
/api/draft-preview/{taskId}/assets/{assetId}.png
```

Completed tasks must not expose unresolved visible raster assets.

## Codia Reference

Official Codia JSON samples are reference/eval inputs only:

```text
docs/reference/codia-samples/
internal/eval/codia
```

Generation packages must not read Codia samples or import eval packages.
