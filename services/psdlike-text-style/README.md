# PSD-like Text Style Service

Focused Slice Studio service for editable-text style measurement.

It is intentionally measurement-only:

```text
page PNG + text items + optional ownerSurface
-> fontSize, fontWeight, fontFamily, color, lineHeight, textAlign, measured
```

It does not decide OCR ownership, raster preservation, slice ownership,
knockout, Pencil layer order, or export schema.

Run locally:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 4120
```

Test:

```bash
uv run pytest -q
```
