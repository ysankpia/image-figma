# M34.3 Text-Symbol Leakage Cleanup Before M30 Materialization

- 状态：active
- 日期：2026-05-20

## Goal

M34.3 cleans high-confidence OCR symbol leakage before M30 emits editable text. It fixes cases where a leading icon glyph is recognized as text, such as a magnifier-like glyph becoming leading `Q`.

Source chain:

```text
OCR/M29 evidence stays unchanged
+ editable M30 text member
+ decoded source pixels
-> cleaned text + cleaned bbox for materialized text node
```

## Plan

- Add a pixel-only leading projection gap helper in `png_tools.py`.
- In M30 text materialization, run cleanup only after text editability allows `editable_text`.
- First version auto-trims only uppercase leading `Q` with pixel projection evidence.
- Use `cleanedBBox` for text node layout, foreground sampling, and `M30MaterializedNode.bbox`.
- Keep the protected symbol pixels in fallback naturally by not including them in the cleaned bbox.
- Add report/meta diagnostics for original and cleaned text/bbox decisions.

## Non-Goals

- No OCR JSON rewrite.
- No M29 nodes rewrite.
- No M31 reconstruction tree changes or downstream backflow.
- No visible icon layer or symbol primitive creation.
- No fallback erasure function changes.
- No M38 hierarchy output.

## Acceptance

- High-confidence leading `Q` symbol leakage is trimmed from emitted editable text.
- Legitimate `Q` text without projection gap remains unchanged.
- Cleaned bbox drives text layout, foreground sampling, and fallback text erasure.
- M30 report explains text-symbol leakage decisions.

## Verification

```bash
cd backend
uv run pytest tests/test_png_tools.py tests/test_evidence_grounded_dsl_materialization.py tests/test_m30_upload_pipeline.py tests/test_config_env.py -q
```
