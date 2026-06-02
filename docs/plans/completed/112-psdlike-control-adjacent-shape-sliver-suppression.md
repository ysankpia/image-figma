# 112 PSD-like Control-Adjacent Shape Sliver Suppression

## Status

Completed.

## Summary

Fix the visible artifact where a low-texture background-like `ShapeLayer` sliver is materialized next to a confirmed control and then covers the control edge. The concrete observed symptom is the `case_0036_764d3a58e5` income card button appearing clipped on the right side, but the repair must be generic.

This stage only changes `services/psdlike-python` shape ownership/suppression logic and tests. It does not change renderer, plugin, Go backend, DSL schema, OCR, model evidence, or Web profile thresholds.

## First Principles

PSD-like layer ownership requires one visible foreground object to own one visible pixel region. A low-texture region with no text ownership, no independent control role, and background-like fill is not an independent foreground object just because connected-component extraction produced a candidate box.

The failing chain is:

```text
confirmed control surface is correct
-> adjacent low_texture_solid_region background sliver survives
-> shape z-order renders the sliver above the control
-> the control edge looks clipped
```

The correct ownership decision is:

```text
confirmed control remains visible
background-like adjacent sliver is suppressed as parent/background residue
```

## Scope

Allowed:

- `services/psdlike-python/app/core/controls.py`
- `services/psdlike-python/tests/test_core_pipeline.py`
- this plan document

Forbidden:

- sample id, file path, literal visible text, fixed bbox, fixed coordinates, fixed screen size, brand, theme, or case-specific rules;
- renderer/plugin masking of backend ownership defects;
- changes to public DSL/API contracts;
- Web profile threshold changes.

## Implementation

Add a generic suppression reason:

```text
control_adjacent_background_sliver
```

The rule applies only when all of these are true:

- candidate is `low_texture_solid_region`;
- candidate is not a confirmed control;
- candidate is near or lightly overlapping a confirmed control edge;
- candidate geometry is a narrow sliver/residual relative to the control;
- candidate has no text ownership signal;
- candidate fill is much closer to background/light parent surface than to the control fill;
- candidate is not a real sibling control/chip/tab.

The rule belongs in `suppress_control_owned_shapes()` through `classify_control_owned_shape()`, after confirmed control candidates are merged and before raster suppression.

## Tests

Add synthetic regression coverage:

- suppress a background-like low-texture sliver adjacent to a confirmed control;
- keep adjacent real sibling controls and existing control-owned fragment behavior.

Run:

```bash
cd services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

## Targeted Validation

Run only the recent targeted set:

```bash
cd services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_112_control_sliver_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_112_control_sliver_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0037_7aa443d6c7 \
  --case-id case_0058_b048f93bd2
```

Acceptance:

- `case_0036_764d3a58e5`: the blue `提现` control remains complete; the right-side white sliver no longer clips the button; previous chart/control false-positive cleanup does not regress.
- `case_0037_7aa443d6c7`: action/control text and surfaces do not visibly regress.
- `case_0058_b048f93bd2`: electronic card area does not return to overlapping colored control blocks.
- all three generated DSLs are valid, with no missing assets, visible full-page raster, or tiny raster fragments.

## Validation Evidence

Static checks:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

Result: `47 passed, 1 warning`.

Targeted validation:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_112_control_sliver_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_112_control_sliver_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0037_7aa443d6c7 \
  --case-id case_0058_b048f93bd2
```

Result: `failed cases: 0`, DSL valid for all three cases.

Artifact checks:

- `case_0036_764d3a58e5`: income button region now contains only the two background bands and the confirmed blue `ocr_anchored_control_surface`; the prior `x400 y1352 w24 h56` white sliver is no longer visible. The output diagnostics include `control_adjacent_background_sliver: 1`.
- `case_0037_7aa443d6c7`: generated successfully with no full-page visible raster, no tiny raster fragments, and no missing assets.
- `case_0058_b048f93bd2`: generated successfully with no return to overlapping colored control blocks, no full-page visible raster, no tiny raster fragments, and no missing assets.

Inspected crops:

- `/tmp/case0036_112_income_button_crop.png`
- `/tmp/case0036_112_overlay_income_button_crop.png`

