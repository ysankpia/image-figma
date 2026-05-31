# Plugin Rendering

The plugin and renderer consume Draft Runtime DSL. They do not make backend ownership decisions.

## Runtime Flow

```text
Plugin UI
-> Plugin main
-> POST /api/draft-preview
-> poll /api/draft-preview/{taskId}
-> GET /api/draft-preview/{taskId}/dsl
-> renderer renders Draft Runtime DSL
-> Figma nodes
```

Raster assets are fetched from:

```text
/api/draft-preview/{taskId}/assets/{assetId}.png
```

## Renderer Responsibility

Renderer should:

- create Figma frames/groups/text/shapes/images from DSL;
- keep text above lower z-order raster/shape siblings;
- report image load failures;
- render available layers even when one element fails;
- preserve backend IDs in plugin data where practical.

Renderer should not:

- run OCR;
- call VLM;
- crop source PNG;
- infer ownership;
- hide duplicate backing bugs;
- suppress backend layers by sample-specific rules.

## Plugin Responsibility

Plugin should:

- upload PNG;
- show task progress/failure;
- fetch DSL and assets;
- call renderer;
- display warnings surfaced by renderer/backend.

Plugin should not:

- inspect Codia golden;
- patch layer order based on image names;
- choose between backend evidence candidates;
- call Figma API from UI iframe.

## Warning Policy

Warnings are useful evidence and should not be silently swallowed.

Important warning classes:

```text
IMAGE_LOAD_FAILED
DRAFT_ASSET_NOT_FOUND
DRAFT_TEXT_COVERED
DRAFT_UNAUTHORIZED_OVERLAP
DRAFT_REFERENCE_IMAGE_VISIBLE
```

The right fix for ownership warnings is normally in Draft assembly or asset export, not in the renderer.
