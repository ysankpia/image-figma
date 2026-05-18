# M29.0.1 Blocked Evidence Enhancement

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Goal

M29.0.1 只增强 M29 `blocked` evidence 的可解释性，为后续 M29.1 eligible blocked primitives 做准备。

它不改变 M29 accepted `text/shape/image/symbol/unknown` nodes，不改变检测接受逻辑，不新增 detector，不接 OCR/SAM2/SVG/Figma/DSL，也不进入上传主链路。

## Implementation

M29 document 仍保持 `version = "0.1"`，避免扩大迁移面；`meta.blockedEvidenceVersion = "0.2"` 标记 blocked evidence 合同升级。

`M29BlockedPrimitive` 保持 `bbox/source/reasons/metrics`，新增最小 `context`：

```text
area
maxEdge
textOverlapRatio
imageOverlapRatio
protectiveShapeOverlapRatio
insideImage
nearImage
nearProtectiveShape
nearestShapeId
```

`context` 只记录 M29.1 需要的局部事实，不记录 neighbor graph、group relation、semantic icon type 或 future grouping decision。

## Reason Taxonomy

M29.0.1 不再把复杂 reject 压成单一 `symbol_metrics_rejected`，而是输出有限 reason：

```text
symbol_color_too_high
symbol_texture_too_high
symbol_edge_too_high
symbol_area_too_small
symbol_area_too_large
line_like
text_overlap
inside_image_primitive
image_internal_texture
protective_shape_overlap
large_container_fragment
weak_symbol_metrics
```

后续 M29.1 可考虑进入 grouping 的 reason：

```text
weak_symbol_metrics
symbol_color_too_high
symbol_texture_too_high
symbol_edge_too_high
symbol_area_too_small
```

后续 M29.1 hard-block reason：

```text
inside_image_primitive
image_internal_texture
text_overlap
protective_shape_overlap
large_container_fragment
line_like
symbol_area_too_large
```

## Acceptance

M29.0.1 验收重点：

```text
blocked item 都有 bbox/metrics/reasons
blocked context 字段类型可校验
meta.blockedEvidenceVersion == "0.2"
meta.blockedReasonSummary 统计 reason 分布
accepted nodes 的 type/subtype/bbox 签名不因 evidence 字段变化而改变
真实图 smoke 中 blocked reasons 不再大面积塌缩为 symbol_metrics_rejected
```

验证命令：

```bash
cd backend && uv run pytest tests/test_visual_primitive_graph.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```
