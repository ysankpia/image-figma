# M29.0.3 Visual Evidence Normalization

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Goal

M29.0.3 是 M29.0.2 之后的证据归一化 harness。它不降低 M29 image 阈值，也不回写 M29/M29.1，而是把 M29/M29.1/M29.0.2 已经看见的视觉对象统一成 `VisualEvidenceItem`，再分成 accepted image、media candidate、icon candidate、text noise 和 other candidate。

核心规则：

```text
source 只表示来源
visualKind/decision 才表示当前判断
```

M29.0.3 不替换 M8 `/primitives`，不进入上传主链路，不改 DSL/Figma，也不正式接 M30 OCR。它只消费 M29.0.2 已经产生的 text mask/media evidence。

## Implementation

新增：

```text
backend/app/visual_evidence_normalization.py
backend/scripts/run_m29_0_3_visual_evidence_normalization.py
backend/tests/test_visual_evidence_normalization.py
```

输入：

```text
source PNG
M29.0.2 text_masked_media_audit.json
```

输出到 M29 output 下的 `m29_0_3/`：

```text
visual_evidence.json
visual_evidence.md
preview_visual_evidence.png
assets/accepted_images/*.png
assets/media_candidates/*.png
assets/icon_candidates/*.png
assets/text_noise/*.png
assets/other_candidates/*.png
overlays/13_visual_evidence_buckets.png
overlays/14_media_candidates.png
overlays/15_text_noise.png
```

## Classification

每个 M29.0.2 `mediaEvidence` item 必须恰好生成一个 `VisualEvidenceItem`，且必须从原始 source PNG 裁出 asset。

分类顺序：

```text
textOverlapRatio >= 0.35 或 likely_text_noise -> text_noise/noise
m29_image + keep_accepted_image -> accepted_image/accepted
低文字重叠 + image-like metrics + 足够面积 -> media_candidate/candidate
低文字重叠 + icon 尺寸 -> icon_candidate/candidate
其他保留为 other_candidate/candidate
```

Preview 排序固定为：

```text
accepted_image
media_candidate
icon_candidate
other_candidate
text_noise
```

`text_noise` 不删除，只排后，保持可审计。

## Legacy Positioning

M20-M28 是历史探索阶段，不再作为 M29+ 的事实来源。M29+ 的新事实来源是：

```text
M29 visual primitive graph
M29.0.2 text-masked media audit
M29.0.3 visual evidence normalization
```

旧 SAM2/icon placement/fallback 产物可以作为历史参考，但不能约束 M29+ 的 evidence 合同。

## Validation

```bash
cd backend && uv run pytest tests/test_visual_evidence_normalization.py -q
cd backend && uv run pytest tests/test_visual_primitive_graph.py tests/test_symbol_fragment_grouping.py tests/test_text_masked_media_audit.py tests/test_visual_evidence_normalization.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```

真实图 smoke：

```bash
cd backend
uv run python scripts/run_m29_0_3_visual_evidence_normalization.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --m29-output storage/m29_visual_primitive_graph_audit_20260518_160831
```

验收重点是轮播图在 accepted images，分类宫格和供应商商品图进入 media candidates，底部 tab/工具图标进入 icon candidates，文字碎片进入 text noise 且仍可审计。
