# Python M29.0 Locator

Python parity port of the standalone Go M29.0 locator.

Source behavior:

```text
../go-m29-physical-evidence/
```

This tool only does:

```text
input PNG
-> foreground mask
-> connected components
-> original-image pixel bboxes
-> crop PNGs for each bbox
-> m29_locations.v1.json
```

It does not include OCR, tokens, Draft, vision, relation graphs, overlays, or preview sheets.

Parity target:

```text
coordinates, item ordering, crop paths, crop dimensions, and crop pixels match the Go locator.
```

Tiny floating-point differences can occur in `edgeDensity`, derived `textureScore`, or derived hint `confidence` around threshold/serialization boundaries. They are not part of the coordinate/crop acceptance gate.

## Run

```bash
PYTHONPATH=src python3 -m py_m29_locator \
  --input /absolute/path/to/input.png \
  --out /tmp/py-m29-locate
```

Expected output:

```text
/tmp/py-m29-locate/m29_locations.v1.json
/tmp/py-m29-locate/crops/loc_0001.png
...
```

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
