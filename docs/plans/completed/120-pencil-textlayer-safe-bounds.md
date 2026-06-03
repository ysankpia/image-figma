# 120 Pencil TextLayer Safe Bounds

## Status

Completed.

## Goal

Prevent editable OCR TextLayers in `services/pencil-python-backend` from being
visually clipped by Pencil's actual text renderer when OCR bounding boxes are
tight.

This is a Pencil `.pen` text layout contract fix. It is not an OCR, PSD-like
boundary, M29, or Figma plugin change.

## Root Cause

OCR and PSD-like evidence preserve text such as `今日提交数` and `今日完成数`.
The final `.pen` also contains matching TextLayer nodes, but those nodes use
`textGrowth: fixed-width-height` with the raw OCR bbox as the exact node bounds.
Pencil may render `system-ui`/CJK text wider or taller than the Python
measurement font used during export, so a tight OCR bbox can clip glyphs.

## Scope

- Add a generic safe-bounds expansion for visible OCR TextLayers.
- Keep the text visual center aligned with the source OCR bbox.
- Clamp expanded bounds to the page canvas.
- Preserve font fitting against the original OCR bbox so the text does not
  visibly grow.
- Record original and safe text bounds in node metadata.
- Add unit tests for CJK TextLayer safe bounds.

## Non-Goals

- Do not change OCR recognition.
- Do not change text knockout or bitmap crop ownership.
- Do not patch the Figma importer.
- Do not add sample-name, text-content, coordinate, or page-specific rules.

## Validation

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

Run a focused `page_0003` export and compare `今日提交数` / `今日完成数` in the
Pencil CLI preview.

## Completion Evidence

- `cd services/pencil-python-backend && uv run python -m py_compile $(find app tests -name '*.py' | sort)`
- `cd services/pencil-python-backend && uv run pytest -q`
- Re-exported `/Volumes/WorkDrive/pencil-exports/jianzhi-psdlike-boundary-realocr-v2/work/page_0003/psdlike_pencil_evidence`.
- Pencil CLI preview:
  `/Volumes/WorkDrive/pencil-exports/text-safe-bounds-page0003-single-20260603-222344/preview/clean-editable.png`
- Focused comparison:
  `/Volumes/WorkDrive/pencil-exports/text-safe-bounds-page0003-single-20260603-222344/preview/page_0003_metrics_fixed_compare.png`
