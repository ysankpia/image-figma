# Go M29.0 Locator

Standalone minimal Go locator for original-image pixel coordinates.

This tool is intentionally smaller than the archived Go backend. It only keeps the M29.0 coordinate path:

```text
input PNG
-> foreground mask
-> connected components
-> original-image pixel bboxes
-> crop PNGs for each bbox
-> m29_locations.v1.json
```

It does not call OCR, compile Draft-era tokens, build relation graphs, generate preview sheets, or render Pencil/Figma files.

## Run

From this directory:

```bash
go test ./...
```

Locate foreground regions:

```bash
go run ./cmd/m29locate \
  --input /absolute/path/to/input.png \
  --out /tmp/go-m29-locate
```

Expected output:

```text
/tmp/go-m29-locate/m29_locations.v1.json
/tmp/go-m29-locate/crops/loc_0001.png
/tmp/go-m29-locate/crops/loc_0002.png
...
```

## JSON Contract

The coordinate source is:

```text
m29_locations.v1.json
-> items[]
-> bbox
```

Each item contains the source-image pixel bbox plus the corresponding crop path:

```json
{
  "id": "loc_0001",
  "kind": "image_region",
  "bbox": {
    "x": 249,
    "y": 14,
    "width": 167,
    "height": 42
  },
  "cropPath": "crops/loc_0001.png"
}
```

Coordinates are in the original PNG coordinate system. The crops are cut from the same original image.

## Boundary

This module is not wired into Slice Studio. The current Slice Studio runtime still defaults to:

```text
server/m29-physical-evidence/
```

The archived source remains untouched at:

```text
archive/legacy-code/services/backend-go/
```
