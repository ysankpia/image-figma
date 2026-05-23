# M29.0.2 Text-Masked Visual Media Audit

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Goal

M29.0.2 是 M29 visual primitive graph 的诊断增强。它用 OCR/text boxes 生成 `text_mask` 和文字中和后的 analysis view，减少文字碎片对图片/图标候选判断的干扰，并输出媒体证据审计。

M29.0.2 不正式接入 M30 OCR，不把文字从最终图片资产里擦掉，不修改 M29/M29.1 输出，不进入上传主链路，不改 DSL/Figma，也不替换 M8 `/primitives` 合同。

核心规则：

```text
detection 可以使用 text-suppressed analysis view
asset export 必须仍从原始 source PNG 裁剪
```

## Implementation

新增：

```text
backend/app/text_masked_media_audit.py
backend/scripts/run_m29_0_2_text_masked_media_audit.py
backend/tests/test_text_masked_media_audit.py
```

输入可以是 M29 output、M29.1 output、`--text-boxes-json` 或 `--ocr-json`。只有显式传 `--ocr-provider baidu_ppocrv5` 时才调用远程 Paddle OCR；默认不依赖网络和 token。

## Pipeline

```text
load source PNG
-> load OCR/text boxes
-> build text_mask
-> create text-suppressed analysis PNG
-> load or run original M29 evidence
-> run M29 on text-suppressed analysis in audit-only output
-> compare before/after counts and bboxes
-> load M29.1 groups when present
-> classify media evidence by page regions
-> export evidence crops from original source PNG
-> write overlays, preview, JSON and Markdown report
-> validate output
```

输出到 M29 output 下的 `m29_0_2/`：

```text
text_masked_media_audit.json
text_masked_media_audit.md
preview_text_masked_media_audit.png
overlays/09_text_mask.png
overlays/10_text_suppressed_analysis.png
overlays/11_media_before_after.png
overlays/12_media_evidence_map.png
assets/accepted_images/*.png
assets/media_like_unknowns/*.png
assets/media_like_symbols/*.png
assets/media_like_blocked/*.png
assets/symbol_groups/*.png
```

## Run

```bash
cd backend
uv run python scripts/run_m29_0_2_text_masked_media_audit.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --m29-output storage/m29_visual_primitive_graph \
  --text-boxes-json storage/m29_text_boxes_smoke.json
```

显式 Paddle OCR smoke：

```bash
cd backend
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
uv run python scripts/run_m29_0_2_text_masked_media_audit.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --m29-output storage/m29_visual_primitive_graph \
  --ocr-provider baidu_ppocrv5
```

## Acceptance

合成测试必须覆盖：

```text
OCRDocument.blocks -> M29TextBox
text_mask 和 text-suppressed analysis PNG 可读
text-suppressed analysis 只改 text_mask 区域
evidence asset 从原图裁，不从擦字图裁
accepted image 和 M29.1 group 也必须导出 evidence crop，避免 JSON 有记录但 preview grid 不展示
纯文字碎片在 text_mask 后不再污染 symbol
文字旁边 icon 仍能保留为候选
mediaEvidence 区分 m29_image / m29_unknown / m29_symbol / m29_blocked / m291_group / after_text_mask_candidate
validation 拒绝坏 bbox、重复 id、缺失 asset、不可读 overlay
```

真实图 smoke 是人工诊断证据。重点看分类宫格、秒批区、供应商推荐、采购工具和底部 tab 的图片/图标分别落在 accepted image、unknown、symbol、blocked、M29.1 group 还是 text-suppressed candidate。

## Validation

```bash
cd backend && uv run pytest tests/test_text_masked_media_audit.py -q
cd backend && uv run pytest tests/test_visual_primitive_graph.py tests/test_symbol_fragment_grouping.py tests/test_text_masked_media_audit.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```

M29.0.2 storage output 是本地证据，不提交 `backend/storage/`。
