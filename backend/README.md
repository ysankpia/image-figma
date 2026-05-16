# Image-to-Figma Backend

Backend for the Image-to-Figma MVP. It accepts one PNG, stores local files, creates a completed task, builds deterministic region fallback DSL from real PNG dimensions, saves visual primitive candidates, saves OCR, DSL patch, text replacement candidates, uses UI-aware sampling to reduce text replacement false rejections, quality-gates visible replacements, builds text-to-container binding reports, builds component structure reports, and serves local asset URLs.

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
