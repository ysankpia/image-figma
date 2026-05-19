# M29.1.2 Symbol Lineage Survival Contract

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M29.1.2 给 M29.1 输出增加 pre-OCR symbol lineage 元数据，让后续 M29.0.3 在 high OCR overlap 时能区分：

```text
plain text noise
lineage-backed symbol/text conflict
rejected text-like glyph sequence
```

这一步不是 detector，不是 grouping 放宽，不是正式 visual asset 升级，也不是修图。它只把 M29/M29.1 已有的 symbol / eligible blocked / group 证据，用 `sourceLineage` 合同带到后续阶段。

## Contract

M29.1 `candidates[]` 和 `groups[]` 可输出：

```json
{
  "sourceLineage": {
    "preOcrSymbolCandidate": true,
    "lineageStrength": "weak",
    "lineageSource": "m29_symbol | eligible_blocked | m291_group",
    "m29NodeIds": [],
    "m29BlockedIds": [],
    "m291CandidateIds": [],
    "m291GroupId": "group_001",
    "ownershipHint": "visual_or_mixed",
    "risks": [],
    "reasons": []
  }
}
```

规则：

```text
accepted group -> medium/strong lineage
uncertain group -> weak/medium lineage
eligible blocked candidate -> weak lineage
text_like_glyph_sequence / image_like_merged_result -> rejectedLineageReason, no surviving sourceLineage
```

`sourceLineage` 是 advisory evidence。它只说明该区域在 OCR 前有 visual lineage，不说明它可直接成为 formal visual asset。

## M29.0.3 Consumption

M29.0.3 新增可选参数：

```bash
--m291-lineage-json /path/to/group_nodes.json
```

未传时，M29.0.3 baseline 行为保持不变。

传入时，classification 规则变为：

```text
high OCR/text overlap + no preOcrSymbolLineage
=> visualKind=text_noise, decision=noise

high OCR/text overlap + surviving preOcrSymbolLineage
=> visualKind=mixed_symbol_text_candidate, decision=uncertain

high OCR/text overlap + rejected text-like lineage
=> visualKind=text_noise, decision=noise
```

`mixed_symbol_text_candidate` 排序在 `other_candidate` 之后、`text_noise` 之前。它有 crop 仅用于 M29.0.3 审计资产桶，不是 formal visual asset。

## M29.0.7 Consumption

M29.0.7 对 `mixed_symbol_text_candidate` 输出：

```text
ownership=mixed_or_uncertain
decision=uncertain
ownershipReasonKind=symbol_text_ownership_conflict
suppressedAsVisual=false
allowedForObjectFormingVisualSide=false
allowedForTextSide=false
allowedForAuditOnly=true
```

plain `text_noise` 的 OCR ownership 规则不变。真实 icon/media/image 的 overlap 规则也不变。

## Boundaries

- 不改 M29 `nodes.json`。
- 不重新扫描 raw pixels。
- 不接新 OCR 或 detector。
- 不把 uncertain lineage 升级成 accepted visual asset。
- 不让 text-like glyph sequence 存活为 visual lineage。
- 不写页面角色或行业特化合同。
- 不进入 DSL、Renderer、Figma 或上传主链路。

## Validation

```bash
cd backend && uv run pytest \
  tests/test_symbol_fragment_grouping.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_text_visual_ownership_gate.py -q
```

验收重点：

- accepted/uncertain/eligible blocked 输出正确 lineage。
- rejected text-like sequence 不输出 surviving lineage。
- 无 lineage 的 high overlap 仍是 `text_noise`。
- 有 surviving lineage 的 high overlap 成为 `mixed_symbol_text_candidate`。
- `mixed_symbol_text_candidate` 在 M29.0.7 中 audit-only，不进入 object-forming visual side。
- formal visual asset 生成路径不改变。
