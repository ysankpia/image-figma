# 213 Python M29 Locator Parity

Status: completed

## Goal

Create a new Python implementation of the standalone Go M29.0 locator without modifying the Go locator.

Python output must match the current Go locator behavior for the same input image at the coordinate/crop contract:

```text
input PNG
-> foreground mask
-> connected components
-> original-image pixel bboxes
-> m29_locations.v1.json
-> crops/loc_*.png
```

## Source Truth

Use the current standalone Go locator as the behavior source:

```text
tools/go-m29-physical-evidence/
```

Do not use the archived Go backend as the implementation target for this pass.

## Scope

- Add `tools/py-m29-locator/`.
- Implement a Python CLI equivalent to `go run ./cmd/m29locate`.
- Match:
  - JSON schema fields and key casing.
  - background estimate thresholds.
  - foreground mask condition.
  - 4-neighbor connected component behavior.
  - component bbox coordinates.
  - component ordering.
  - classification output.
  - crop filenames and crop dimensions.

## Forbidden Scope

```text
Do not edit tools/go-m29-physical-evidence/.
Do not edit archive/legacy-code/services/backend-go/.
Do not add OCR/Baidu/token/Draft/vision/relation graph behavior.
Do not introduce image-name, path, sample, coordinate, or fixture-specific logic.
```

## Acceptance

- Python CLI writes `m29_locations.v1.json` and `crops/loc_*.png`.
- Python unit test covers a synthetic rectangle and exact bbox/crop output.
- Real sample parity against Go:
  - item count matches.
  - every item bbox matches.
  - every item kind matches.
  - measurements match except for accepted tiny Go/Python floating-point edge-density drift at threshold boundaries.
  - crop dimensions match for all items.
- `git diff -- tools/go-m29-physical-evidence archive/legacy-code/services/backend-go` remains empty except for no changes.

## Result

Added `tools/py-m29-locator/` as a standalone Python implementation. It accepts one PNG and writes:

```text
m29_locations.v1.json
crops/loc_*.png
```

It intentionally does not include OCR, Baidu, evidence tokens, Draft, vision, relation graph, overlays, or preview sheets.

Real-sample parity against `tools/go-m29-physical-evidence/` on `docs/reference/codia-samples/images/腾讯动漫_018_1440.png`:

- Go item count: 210.
- Python item count: 210.
- All item ids, bboxes, kinds, crop paths, crop dimensions, and crop pixels matched.
- Diagnostics matched.
- Eleven measurement entries differed only in `edgeDensity` or derived `textureScore`, and one hint entry differed only by a `confidence` float serialization tail. The user accepted this as below the coordinate/crop behavior threshold; no Python compatibility hack was added.

The standalone Go locator and archived Go backend were not modified.

## Validation

```bash
cd tools/py-m29-locator
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m py_m29_locator --input <sample.png> --out <tmp>/py

cd ../go-m29-physical-evidence
go run ./cmd/m29locate --input <sample.png> --out <tmp>/go

python3 <parity check>
git diff -- tools/go-m29-physical-evidence archive/legacy-code/services/backend-go
git diff --check
```
