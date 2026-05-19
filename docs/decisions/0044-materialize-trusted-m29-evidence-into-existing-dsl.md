# ADR: Materialize Trusted M29 Evidence Into Existing DSL

- 状态：accepted
- 日期：2026-05-19

## Context

M29 已经把 PNG 像素拆成可审计的 text / shape / image / symbol / mixed evidence，并通过 M29.0.7、M29.1.3、M29.0.3.2 把污染风险关在 audit-only 层。

有效 80 图 batch 为：

```text
backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_20260519_200727
```

无效 batch 不可作为 M30 事实来源：

```text
backend/storage/m29_0_3_2_residual_mixed_boundary_review_batch_20260519_193713
reason: BAIDU_PADDLE_OCR_TOKEN_MISSING
```

M29 closure tightening review 结果：

```text
confirmed_text_counter_evidence: 70
reviewed_tightening_candidates: 103
ratio: 0.679612
threshold: 0.70
```

这说明继续做 M29.0.3.3 的收益不足以抵消误收紧风险。正确下一步不是恢复图标，也不是继续扩大 M29 audit，而是把 M29.0.5 已经安全分离出的 textMembers、shapeCandidates 和 visualAssets 保守落到现有 DSL v0.1。

## Decision

新增 M30 Evidence-Grounded DSL Materialization。

M30 是 script-only 阶段，不接上传主链路。它输出新的 DSL variant：

```text
m30_materialized_dsl.json
m30_materialization_report.json
m30_materialization_preview.png
```

M30 支持两种输入模式：

```text
augment-existing-dsl:
  default path
  base DSL + M29.0.5 evidence -> materialized DSL variant

bootstrap-dsl-from-m29:
  no base DSL path
  source image + M29.0.5 evidence -> minimal DSL with full-image fallback
```

M30 只 materialize：

```text
M29.0.5 textMembers
M29.0.5 safe shapeCandidates
M29.0.5 safe visualAssets
```

M30 不 materialize：

```text
mixed_symbol_text_candidate
future_promotable_uncertain_symbol_candidate
candidate_for_future_uncertain_review
keep_mixed_symbol_text_conflict
M29.1.3 audit-only items
M29.0.3.2 residual review items
```

M30 不使用 DSL `icon` type。当前 Renderer 对 `icon` type 仍是 unsupported，safe visual assets 统一落成 DSL `image` nodes。

## Consequences

Benefits:

- 从 M29 evidence 层进入 DSL/Renderer 层，不再停留在 audit-only 研究。
- 复用现有 DSL v0.1 和 Renderer，不创建新的 DesignScene schema。
- fallback 保留，M30 节点只是可编辑 materialization overlay，局部失败不会破坏整页。
- audit-only mixed/future/residual 信息不会绕过 safety gates 进入 visible DSL children。

Costs:

- M30.1 不做 text cover，可能出现轻微双字；这是验证桥接层的可接受代价。
- Shape 第一版会偏保守，没有可靠 fill 的候选会被 skip。
- Image 第一版只复制 M29.0.5 已存在 asset，不重新裁剪，不补漏。

Hard boundaries:

- 不改 M29.0.3、M29.1.3、M29.0.7、M29.0.4、M29.0.5。
- 不修改任何 M29 JSON。
- 不重新 OCR，不重新 detector，不新增 bbox。
- 不从 raw pixels 新切 child bbox。
- 不做 M29.1.4、promotion、图标恢复。
- 不做 Auto Layout、Figma Component/Instance、SVG/vectorization。
- 不删除 fallback。
- 不接上传主链路。
