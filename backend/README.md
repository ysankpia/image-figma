# Image-to-Figma Backend

M4 backend for the fake task flow. It accepts one PNG, stores local files, creates a completed fake task, returns DSL, and serves local asset URLs.

## Run

```bash
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Test

```bash
uv run pytest
```
