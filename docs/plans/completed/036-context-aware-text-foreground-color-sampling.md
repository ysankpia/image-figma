# M36 Context-Aware Text Foreground Color Sampling

- 状态：completed
- 日期：2026-05-20

## Goal

M36 fixes text legibility in M30 materialized DSL. Editable text color must come from source PNG pixel evidence instead of a single hard-coded dark gray.

Source chain:

```text
source PNG decoded pixels
+ editable M30 text bbox
+ local dominant background sample
-> sampled foreground color
-> DSL text node style.color
```

## Plan

- Add `sample_text_foreground_rgb(...)` and `default_contrast_rgb(...)` in `png_tools.py`.
- Use existing dominant edge background sampling around each editable text bbox.
- Filter bbox interior pixels by RGB distance from background, bucket remaining pixels by RGB `// 16`, and use the contrast-weighted bucket average as foreground.
- M36.1 keeps the same source pixels and API, but prevents high-count texture buckets from beating smaller high-contrast text strokes.
- If the bbox is too small, out of usable bounds, or has no high-contrast foreground pixels, use black or white from background brightness.
- In M30 materialization, sample foreground only for text that is actually emitted as `m30_text_member`.
- Record `textForegroundColorSource` in text node meta and summary counters in the M30 report.

## Non-Goals

- No M31 tree consumption.
- No frame/group generation.
- No relative coordinates.
- No OCR, VLM, detector, font recognition, or handwritten text reconstruction.
- No change to M35 fallback erasure.
- No sampling or redrawing for `graphic_text_preserve_in_fallback`.

## Acceptance

- Editable text on dark, blue, or colored backgrounds no longer defaults to `#111827`.
- Preserved graphic text still stays inside fallback and is not materialized as text.
- M30 report exposes sampled/default/fallback text foreground counts.
- M30 DSL schema, Renderer, and plugin contracts remain unchanged.

## Verification

```bash
cd backend
uv run pytest tests/test_png_tools.py tests/test_evidence_grounded_dsl_materialization.py -q
```
