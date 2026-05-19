# M29.1.1 Pre-OCR Symbol Lineage Audit

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M29.1.1 是 script-only 审计层。它只读 M29、M29.1、M29.0.2、M29.0.3 和 M29.0.7 输出，追踪 OCR 前已有 symbol / eligible blocked / group lineage 的候选，后续是否被 M29.0.3 压成 plain `text_noise`，以及是否又被 M29.0.7 suppress。

它不修“底部区域”，不写页面/行业特化规则，不改变 M29/M29.1/M29.0.2/M29.0.3/M29.0.7 行为。它的目标是证明 lineage loss 链条，而不是减少 unresolved 或恢复正式 visual asset。

## Contract

输入：

```text
M29 nodes.json
M29.1 group_nodes.json
M29.0.2 text_masked_media_audit.json
M29.0.3 visual_evidence.json
M29.0.7 text_visual_ownership_gate.json
source PNG for overlays/examples only
```

输出：

```text
m29_1_1/pre_ocr_symbol_lineage_audit.json
m29_1_1/pre_ocr_symbol_lineage_audit.md
m29_1_1/overlay_pre_ocr_symbol_lineage.png
m29_1_1/assets/lineage_lost_examples/
m29_1_1/assets/text_like_glyph_examples/
m29_1_1/assets/mixed_conflict_examples/
```

findingKind 固定为通用证据词：

```text
visual_lineage_lost_after_text_mask
eligible_blocked_not_grouped
accepted_symbol_later_demoted
uncertain_group_later_demoted
anchorless_symbol_fragment
compact_icon_like_blocked
text_like_glyph_sequence
symbol_text_ownership_conflict
```

每个 finding 记录既有 M29 node/blocked、M29.1 candidate/group、M29.0.2 mediaEvidence、M29.0.3 VisualEvidenceItem、M29.0.7 ownershipDecision 的匹配链，以及 bbox、lineageStrength、lineageLossStage、laterVisualKind、laterOwnership、reasons、risks 和 audit example crop。

## Boundaries

- 不新增 bbox，只引用既有 source bbox。
- 不生成 formal visual asset，只生成审计 crop 和 overlay。
- 不重跑 detector，不读取 raw pixels 派生 child。
- 不修改 M29/M29.1/M29.0.2/M29.0.3/M29.0.7 JSON。
- 不进入 DSL、Renderer、Figma 或上传主链路。
- 不使用页面角色或行业场景合同。

## Run

```bash
cd backend
uv run python scripts/run_m29_1_1_pre_ocr_symbol_lineage_audit.py \
  --input "/path/to/source.png" \
  --m29-output storage/m29_visual_primitive_graph
```

默认解析：

```text
--m29-output/nodes.json
latest m29_1*/group_nodes.json
latest m29_0_2*/text_masked_media_audit.json
latest m29_0_3*/visual_evidence.json
latest m29_0_7*/text_visual_ownership_gate.json
```

如果输出目录已存在且未传 `--overwrite`，脚本自动写入时间戳后缀目录。

## Validation

```bash
cd backend && uv run pytest tests/test_pre_ocr_symbol_lineage_audit.py -q
```

M29 focused：

```bash
cd backend && uv run pytest \
  tests/test_pre_ocr_symbol_lineage_audit.py \
  tests/test_symbol_fragment_grouping.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py -q
```

## Acceptance

- 能发现 eligible blocked not grouped。
- 能追踪 M29/M29.1 lineage 后续被 M29.0.3 demote 为 `text_noise`。
- 能追踪后续 M29.0.7 suppression。
- 能记录 text-like glyph sequence，并不把它当 surviving visual lineage。
- 能记录 mixed symbol/text conflict。
- overlay PNG 可读且尺寸等于源图。
- finding bbox 来自既有 evidence，不新增生产几何。
- 不生成 formal visual asset。
