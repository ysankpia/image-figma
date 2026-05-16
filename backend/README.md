# Image-to-Figma Backend

Backend for the Image-to-Figma MVP. It accepts one PNG, stores local files, creates a completed task, builds deterministic region fallback DSL from real PNG dimensions, saves visual primitive candidates, saves OCR, DSL patch, text replacement candidates, uses UI-aware sampling to reduce text replacement false rejections, quality-gates visible replacements, builds text-to-container binding reports, builds component structure reports, annotates DSL elements with component structure metadata, builds layer separation candidate reports, builds local asset slice candidate reports, and serves local asset URLs.

## Run

```bash
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Test

```bash
uv run pytest
```

## M8 Primitives

Default extraction uses the deterministic fake provider:

```bash
VISUAL_PRIMITIVE_PROVIDER=fake
```

Optional OpenAI smoke must be explicitly enabled:

```bash
VISUAL_PRIMITIVE_PROVIDER=openai OPENAI_API_KEY=... uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## OCR And Patch

Default OCR and patch harness:

```bash
OCR_PROVIDER=fake
DSL_PATCH_MODE=debug
```

Optional Baidu PP-OCRv5 async OCR smoke:

```bash
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Debug endpoints:

```bash
curl http://localhost:8000/api/tasks/{taskId}/ocr
curl http://localhost:8000/api/tasks/{taskId}/dsl-patch
curl http://localhost:8000/api/tasks/{taskId}/text-replacements
curl http://localhost:8000/api/tasks/{taskId}/text-bindings
curl http://localhost:8000/api/tasks/{taskId}/component-structures
curl http://localhost:8000/api/tasks/{taskId}/component-annotations
curl http://localhost:8000/api/tasks/{taskId}/layer-separation-candidates
curl http://localhost:8000/api/tasks/{taskId}/asset-slice-candidates
```

Visible text replacement is debug-only by default:

```bash
TEXT_REPLACEMENT_MODE=debug
```

Use `TEXT_REPLACEMENT_MODE=apply` only for local smoke. It keeps fallback regions and blocks only high-risk accepted replacements; medium-risk replacements are applied with caution metadata. M14 UI-aware sampling is enabled by default with `TEXT_REPLACEMENT_UI_AWARE_SAMPLING=true` and records the sampling strategy used for badge, legend, outline button, card/tip, and bottom nav text. `GET /api/tasks/{taskId}/text-replacements` explains accepted, rejected, applied, blocked, and strategy decisions.

M15 text binding is enabled by default:

```bash
TEXT_BINDING_ENABLED=true
TEXT_BINDING_MIN_CONFIDENCE=0.70
```

It writes `backend/storage/text_bindings/{taskId}.json` and exposes `GET /api/tasks/{taskId}/text-bindings`. Binding reports connect OCR/replacement text to visual primitives or inferred UI containers for M16. They do not change Figma-visible output or write inferred containers back into visual primitives. The current inferred roles include page header, hero profile, activity card, summary stat card, primary/outline button, shortcut/preview/tip card, legend group, and bottom nav item; button binding requires action-style evidence and should not absorb summary/stat text.

M16 component structure is enabled by default:

```bash
COMPONENT_STRUCTURE_ENABLED=true
COMPONENT_STRUCTURE_MIN_CONFIDENCE=0.70
```

It writes `backend/storage/component_structures/{taskId}.json` and exposes `GET /api/tasks/{taskId}/component-structures`. Structure reports aggregate M15 containers and bindings into component candidates and layout groups for M17+. They do not change Figma-visible output, do not create Figma Component/Instance nodes, do not delete fallback regions, and do not write inferred components back into visual primitives.

M17 component annotation is enabled by default:

```bash
COMPONENT_ANNOTATION_ENABLED=true
COMPONENT_ANNOTATION_LAYER_NAMING=true
COMPONENT_ANNOTATION_MIN_CONFIDENCE=0.70
```

It writes `backend/storage/component_annotations/{taskId}.json` and exposes `GET /api/tasks/{taskId}/component-annotations`. Annotation reports connect M16 components/groups back to existing DSL elements and update DSL `name`/`meta` only. They do not slice images, create Figma groups/components, delete fallback regions, change visible layout/style/content, or reconstruct icons, circles, triangles, stars, or complex shapes.

M18 layer separation candidates are enabled by default:

```bash
LAYER_SEPARATION_ENABLED=true
LAYER_SEPARATION_MIN_CONFIDENCE=0.70
LAYER_SEPARATION_SIMPLE_FILL_TOLERANCE=24
LAYER_SEPARATION_MAX_COMPONENT_AREA_RATIO=0.35
```

It writes `backend/storage/layer_separation_candidates/{taskId}.json` and exposes `GET /api/tasks/{taskId}/layer-separation-candidates`. M18 consumes M14 replacement evidence plus M15/M16/M17 structure facts to decide whether each component should later use shape + editable text, image slice with simple fill candidate, future repair, embedded text, or no text. M18 only updates top-level DSL meta. It does not slice images, generate filled PNGs, delete fallback regions, change existing DSL elements, create Figma groups/components, do AI inpainting, introduce Pillow/OpenCV, or reconstruct icons and complex shapes.

M19 local asset slice candidates are enabled by default:

```bash
ASSET_SLICE_ENABLED=true
ASSET_SLICE_MAX_CANDIDATES=24
ASSET_SLICE_MIN_CONFIDENCE=0.70
ASSET_SLICE_MAX_AREA_RATIO=0.25
ASSET_SLICE_GENERATE_FILLED=true
```

It writes `backend/storage/asset_slice_candidates/{taskId}.json`, emits PNGs under `backend/storage/assets/{taskId}/slices/`, and exposes `GET /api/tasks/{taskId}/asset-slice-candidates`. M19 consumes M18 layer separation candidates and only slices low-risk component roles that are suitable for future image-slice replacement. It can generate original slice PNGs plus solid-color filled slice PNGs for simple fill candidates. M19 only updates top-level DSL meta and never adds those experimental slices to DSL `assets`, so Figma-visible output stays identical to M18. It does not delete fallback regions, create Figma groups/components, do AI inpainting, introduce Pillow/OpenCV, or reconstruct icons and complex shapes.
