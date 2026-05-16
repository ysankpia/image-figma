# Image-to-Figma Backend

Backend for the Image-to-Figma MVP. It accepts one PNG, stores local files, creates a completed task, builds deterministic region fallback DSL from real PNG dimensions, saves visual primitive candidates, and serves local asset URLs.

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
