# M29.0.7 Text Ownership Gate

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M29.0.7 是 M29+ 的 script-only ownership/routing 阶段。它消费已有 M29.0.3 visual evidence 和 M29.0.2 OCR textBoxes，为每条既有 evidence 生成像素所有权和后续 object-forming 路由建议。

它解决的不是 OCR 或切图能力问题，而是入口归属问题：文字像素应由 text evidence 接管；真实视觉 evidence 才允许作为 object-forming visual side；不确定重叠保留为 mixed/audit 风险。

M29.0.7 不是 replacement engine，不是 detector，不是 clean M29.0.4 generator，不修图，不生成 DSL/Figma/TextNode，不回写 M29.0.2/M29.0.3/M29.0.4/M29.0.5。

## Contract

输入：

```text
M29.0.3 visual_evidence.json
M29.0.2 text_masked_media_audit.json textBoxes
source PNG for overlays and top-K audit examples only
```

输出 schema：

```text
M2907TextVisualOwnershipGateDocument v0.1
```

ownership：

```text
text_owned
visual_owned
shape_owned
mixed_or_uncertain
audit_only
```

routing flags：

```text
suppressedAsVisual
allowedForObjectFormingVisualSide
allowedForTextSide
allowedForAuditOnly
```

核心规则：

```text
M29.0.2 textBox -> text_owned, text side allowed, visual side disallowed.
M29.0.3 text_noise + high OCR overlap + acceptable confidence -> text_owned, suppressed as visual.
M29.0.3 text_noise without usable OCR -> audit_only or mixed_or_uncertain, visual side disallowed.
icon_candidate with high OCR overlap -> mixed_or_uncertain, not directly suppressed.
media_candidate/accepted_image with internal OCR text -> visual_owned with text_overlay_on_visual risk, not suppressed.
other visual candidates stay visual-owned unless overlap makes ownership uncertain.
```

Pixel use is audit-only. The stage may crop top-K examples and draw overlays from existing bboxes. It must not derive child bboxes from raw pixels, erase or synthesize pixels, export text-removed images, or create formal visual assets.

## M29.0.4 Consumption

M29.0.4 baseline is unchanged when no ownership JSON is supplied.

When `--m2907-ownership-json` is supplied, M29.0.4 still builds the object graph from the original M29.0.3/M29.0.2 facts, but attaches ownership routing by source id:

```text
m2903_visual_evidence:<sourceVisualEvidenceItemId>
m2902_text_box:<sourceTextBoxId>
```

Object-forming visual side requires `allowedForObjectFormingVisualSide=true`. Text-owned evidence may still participate as text side when `allowedForTextSide=true`. Weak text-noise with visual side disallowed no longer forms visual_text_pair visual side, compound_visual, or standalone uncertain_compound.

M29.0.7 does not emit a replacement M29.0.4 document.

## Run

Generate ownership routing:

```bash
cd backend
uv run python scripts/run_m29_0_7_text_visual_ownership_gate.py \
  --input "/path/to/source.png" \
  --m29-output storage/m29_batch_smoke_20260518_221638/image_01
```

Consume ownership routing in M29.0.4:

```bash
cd backend
uv run python scripts/run_m29_0_4_visual_object_candidate_audit.py \
  --input "/path/to/source.png" \
  --m29-output storage/m29_batch_smoke_20260518_221638/image_01 \
  --m2907-ownership-json storage/m29_batch_smoke_20260518_221638/image_01/m29_0_7/text_visual_ownership_gate.json
```

M29.0.7 outputs:

```text
m29_0_7/text_visual_ownership_gate.json
m29_0_7/text_visual_ownership_audit.json
m29_0_7/text_owned_evidence.json
m29_0_7/visual_forming_evidence.json
m29_0_7/audit_only_evidence.json
m29_0_7/text_overlay_on_visual.json
m29_0_7/text_visual_ownership_gate.md
m29_0_7/preview_text_visual_ownership_gate.png
m29_0_7/overlays/
m29_0_7/assets/
```

## Validation

Focused:

```bash
cd backend && uv run pytest tests/test_text_visual_ownership_gate.py tests/test_visual_object_candidate_audit.py -q
```

M29 focused:

```bash
cd backend && uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_symbol_fragment_grouping.py \
  tests/test_text_masked_media_audit.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_visual_object_candidate_audit.py \
  tests/test_text_aware_visual_object_refinement.py \
  tests/test_member_boundary_quality_audit.py \
  tests/test_text_visual_ownership_gate.py -q
```

Full:

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

## Acceptance

- `text_noise` with strong OCR ownership becomes text-owned and cannot form visual side.
- Low-confidence or missing OCR `text_noise` remains non-visual-side audit evidence.
- OCR overlap does not directly suppress icon/image/media candidates.
- Image-internal text is recorded as overlay risk without generating a text-removed image.
- M29.0.4 behavior is unchanged without `--m2907-ownership-json`.
- M29.0.4 with ownership JSON blocks weak text-noise from visual side while preserving text-side relation evidence.
- Routing views only reference existing source ids and existing bboxes.
- Overlay and preview PNGs are readable and source-sized where required.
