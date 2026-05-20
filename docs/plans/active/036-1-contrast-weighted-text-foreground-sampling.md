# M36.1 Contrast-Weighted Text Foreground Sampling

- 状态：active
- 日期：2026-05-20

## Goal

M36.1 fixes the foreground bucket selection bug in M36 text color sampling.

The source truth remains decoded source PNG pixels. The corrected target function is:

```text
editable text bbox pixels
+ local background RGB
-> contrast/polarity-weighted foreground bucket
-> DSL text node style.color
```

## Plan

- Keep the existing M36 public API and M30 materialization behavior.
- Keep bbox clamp, 1px inward shrink, RGB distance `> 64` foreground candidate filtering, and RGB `// 16` buckets.
- Replace count-dominant bucket selection with contrast-weighted scoring.
- Score buckets by RGB contrast, luminance polarity, luminance delta, and a capped square-root count factor.
- Keep count as a weak anti-noise signal, not as the dominant foreground decision.

Scoring:

```text
score =
  min(sqrt(count), 6.0)
  * (rgb_manhattan_distance_from_background / 765.0)
  * luminance_polarity_factor
  * (abs(foreground_luma - background_luma) / 255.0)
```

## Non-Goals

- No OCR, M29, M31, M34 editability, M37 hierarchy, DSL schema, Renderer, or plugin changes.
- No business words, fixed coordinates, page-type rules, or M31 unit semantics.
- No sampling or redrawing for `graphic_text_preserve_in_fallback`.

## Acceptance

- Small white strokes on dark textured badge backgrounds can beat larger dark texture buckets.
- Dark text on light backgrounds still samples as dark text.
- Chromatic text still samples as chromatic text.
- No-foreground and unusable bbox cases still fall back to contrast color.
- M30 foreground diagnostics remain compatible.

## Verification

```bash
cd backend
uv run pytest tests/test_png_tools.py tests/test_evidence_grounded_dsl_materialization.py -q
```
