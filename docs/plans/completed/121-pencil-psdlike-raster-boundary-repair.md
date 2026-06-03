# 121 Pencil PSD-like Raster Boundary Repair

## Status

Completed.

## Goal

Repair local raster objects that PSD-like boundary extraction cropped too
tightly before they enter Pencil evidence.

The observed failure is page_0003 of the `兼职` export: source pixels contain
complete circular metric icons, but PSD-like emits only short lower raster
strips. Pencil faithfully draws those truncated raster crops.

## Root Cause

The information loss happens in PSD-like surface/raster ownership:

```text
source full icon pixels
-> PSD-like local_container_surface owns too much of the card
-> only the lower icon fragment survives as raster
-> Pencil evidence receives an incomplete crop and bbox
-> .pen output shows a clipped icon
```

This is not a Pencil renderer, Figma importer, OCR, or TextLayer safe-bounds
defect.

## Scope

- Add generic source-based raster boundary repair in
  `services/pencil-python-backend/app/psdlike_adapter.py`.
- Only attempt repair for bounded local raster objects.
- Use `source.png` as source truth.
- Build a foreground mask in a local search window, then recover the connected
  component touching the current raster bbox.
- Reject repair if the recovered bbox expands into OCR text, expands like a
  layout/container, or grows implausibly.
- Record repair metadata in `compileHints.rasterBoundaryRepair`.

## Non-Goals

- No Figma plugin changes.
- No page/file/text/coordinate/screen-size special cases.
- No mobile/web/button/card/nav heuristics.
- No replacement of PSD-like with raw M29 primitive dumps.

## Validation

```bash
cd services/pencil-python-backend
uv run python -m py_compile $(find app tests -name '*.py' | sort)
uv run pytest -q
```

Real sample validation:

```bash
cd services/pencil-python-backend
OCR_PROVIDER=baidu_ppocrv5 uv run python -m app.cli.export_project \
  --input /Users/luhui/Downloads/兼职 \
  --out /Volumes/WorkDrive/pencil-exports/jianzhi-psdlike-raster-repair-realocr-v1 \
  --project-name "兼职 PSD-like Raster Repair OCR v1" \
  --mode all \
  --columns auto \
  --boundary-source psdlike \
  --include-debug
```

Acceptance signals:

- page_0003 metric icon rasters expand from truncated strip bboxes to full local
  icon bboxes.
- `compileHints.rasterBoundaryRepair` records original and repaired bbox.
- Pencil CLI preview no longer clips the metric icons.
- Existing `.pen` asset path invariants still pass.

## Completion Evidence

- `cd services/pencil-python-backend && uv run python -m py_compile $(find app tests -name '*.py' | sort)`
- `cd services/pencil-python-backend && uv run pytest -q`
- Real page_0003 adapter replay:
  `/Volumes/WorkDrive/pencil-exports/page0003-raster-repair-adapter-check`
- Real project export:
  `/Volumes/WorkDrive/pencil-exports/jianzhi-psdlike-raster-repair-realocr-v1/project.zip`
- Repaired bboxes:
  - `psd_raster_0021`: `112,512,72,48 -> 108,482,79,83`
  - `psd_raster_0022`: `520,512,80,48 -> 524,482,78,80`
- Pencil CLI preview comparison:
  `/Volumes/WorkDrive/pencil-exports/jianzhi-psdlike-raster-repair-realocr-v1/preview/page_0003_source_vs_clean_editable_metrics_precise.png`
