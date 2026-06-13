# Plan 194: PSD-like text-style evidence gate

Status: completed
Created: 2026-06-14
Completed: 2026-06-14

## Objective

Determine whether the archived PSD-like font/style measurement path is a
correct direction for Slice Studio's current Pencil editable-text problem.

This plan is deliberately an evidence gate, not the production integration.
The production microservice and TypeScript wiring belong to plan 195.

## Problem Checked

Current Slice Studio Pencil export can place editable OCR text correctly but
still make it visually wrong: some button/control labels are too large or too
bold. The concrete P10 `搜索` failure has current exported values:

```text
text: 搜索
current TS fontSize: 40
current TS fontWeight: 600
current textRenderBBox: x=785 y=170 width=92 height=42
owner surface: x=773 y=161 width=116 height=59
```

This points at style measurement, not OCR text content, slice ownership, or
Pencil layer ordering.

## Evidence Harness

The archived PSD-like Python code was used only as a reference/proof harness:

```text
archive/legacy-code/services/psdlike-python
```

A temporary measurement-only endpoint was added there:

```text
POST /api/text-style-batch
```

It accepts one page PNG plus OCR text items and returns measured style values:

```text
fontSize, fontWeight, fontFamily, color, lineHeight, textAlign, measured
```

This endpoint does not decide raster-vs-editable, does not create Pencil
layers, and does not change Slice Studio's export contract.

## Validation

Synthetic endpoint test:

```bash
cd archive/legacy-code/services/psdlike-python
uv run pytest tests/test_text_style_api.py -q
```

Result:

```text
2 passed in 0.34s
```

Real current-project sample:

```text
source image:
storage/projects/project_mqc1wpkd_123c88b0/originals/page_0010.png

input text:
搜索

input bbox:
x=770 y=159 width=121 height=62

input ownerSurface:
x=773 y=161 width=116 height=59 fill=#0eb12f
```

PSD-like result:

```json
{
  "text": "搜索",
  "fontSize": 31,
  "fontWeight": 500,
  "fontFamily": "PingFang SC",
  "color": "#fcfdfc",
  "lineHeight": 31,
  "textAlign": "center",
  "measured": { "width": 62, "height": 34 },
  "source": "psdlike"
}
```

Current export manifest result for the same visible label:

```json
{
  "id": "page_0010__text_0005",
  "text": "搜索",
  "fontSize": 40,
  "fontWeight": "600",
  "fontFamily": "PingFang SC",
  "color": "#fcfffd",
  "textRenderBBox": { "x": 785, "y": 170, "width": 92, "height": 42 }
}
```

## Conclusion

The PSD-like measurement path is the correct next direction for this class of
defect.

Reason:

- It changes exactly the failing variable: font size/weight/color measurement.
- It leaves OCR text content and Slice Studio ownership decisions in the
  current TypeScript pipeline.
- On the real P10 `搜索` case, it moves the value from the visibly wrong
  `40/600` to `31/500`, which matches the observed need to reduce both size and
  weight.
- The archived endpoint proves the measurement code is callable and fast
  enough for a per-page batch call (`elapsedSeconds` around `0.026` for the
  single real item).

This does not prove every text case is solved. The next implementation must
pass real TypeScript owner surfaces into the service instead of hand-entered
coordinates. Manually entered bbox samples for other labels were not accepted
as evidence because they produced unreliable color sampling.

## Follow-up

Open plan 195 to promote the minimum required PSD-like measurement code into a
current mainline service and integrate it with Slice Studio export.

The production service must not import from or run out of
`archive/legacy-code`. Archive remains reference only.
