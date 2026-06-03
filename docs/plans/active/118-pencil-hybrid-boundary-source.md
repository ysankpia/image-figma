# 118 Pencil Hybrid Boundary Source

## Summary

Add an opt-in `boundarySource=hybrid` mode to the Pencil Python backend.
The goal is to keep PSD-like's clean coarse boundaries while using M29 only as
a constrained fallback for local objects that PSD-like failed to cover.

Contract:

```text
1..N images
-> PSD-like layer_stack.v1.json as primary boundary source
-> M29 physical evidence as fallback candidate source
-> hybrid layer_stack.v1.json
-> existing PSD-like adapter
-> existing clean-editable / visual-fidelity / visual-ocr exporter
-> project ZIP
```

## First-Principles Judgment

The root defect is not in the Pencil or Figma importer. The `.pen` importer
renders what the backend gives it. PSD-like reduces crop explosion, but it can
miss small local UI objects. M29 has higher recall, but using all M29 primitives
reintroduces fragmented assets.

The fix belongs at the boundary source normalization layer: keep PSD-like as the
visible layer authority, and admit only M29 primitives whose pixels are not
already owned by PSD-like layers.

## Scope

- Add `boundarySource=hybrid` to CLI and HTTP validation.
- Run PSD-like first, then run local `m29extract` with OCR disabled as fallback
  evidence.
- Build a hybrid layer stack by copying PSD-like output and appending synthetic
  raster layers cropped from `source.png`.
- Only add M29 candidates with low PSD-like visual coverage and bounded local
  object size.
- Preserve OCR text ownership by placing fallback rasters below text layers and
  letting the existing Pencil exporter perform text knockout in OCR modes.
- Preserve the existing `m29` and `psdlike` behavior.

## Non-Goals

- No mobile/web/tabbar/header/button special cases.
- No file-name, page-name, visible-text, fixed-coordinate, or fixed-size rules.
- No Figma plugin changes.
- No direct import of PSD-like service internals.
- No resource-kit revival.
- No full M29 primitive dump into PSD-like output.

## Validation

Run:

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

Run representative real sample export:

```bash
cd services/pencil-python-backend
OCR_PROVIDER=baidu_ppocrv5 uv run python -m app.cli.export_project \
  --input /Users/luhui/Downloads/兼职 \
  --out /Volumes/WorkDrive/pencil-exports/jianzhi-hybrid-boundary-realocr-v1 \
  --project-name "兼职 Hybrid Boundary OCR v1" \
  --mode all \
  --columns auto \
  --boundary-source hybrid \
  --include-debug
```

Acceptance signals:

- Project manifest records `boundarySource=hybrid`.
- `debug/pages/page_XXXX/psdlike_debug/hybrid_boundary_report.v1.json` exists.
- Hybrid fallback count is bounded and does not explode to raw M29 primitive
  counts.
- OCR text remains editable in `clean-editable` and `visual-ocr`.
- `.pen` files do not reference source/raw/mask/debug assets.
- Multi-page visible asset basenames remain globally unique.
