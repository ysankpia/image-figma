# M29 Design Token Report

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

新增 report-only 的单页 M29 design token candidate stage。它基于 materialized DSL 和 M29.5 replay plan，抽取当前页面的颜色、文字样式、圆角、间距候选 token，为后续设计系统能力提供证据。

## Layer Diagnosis

source input：

```text
M29 plan-driven DSL
M29 materialization report
M29.5 replay plan
```

decision point：

```text
color token candidate / text style candidate / radius token candidate / spacing token candidate / coverage / confidence
```

output surface：

```text
storage/upload_previews/{taskId}/m29_design_tokens/design_token_report.json
```

validation surface：

```text
pytest focused tests
upload-preview stage timing
15-image batch validation under /Users/luhui/Downloads/m29
```

## Scope

包含：

- 新增 `backend/app/design_token_report/` package。
- 新增 upload-preview stage `m29_design_tokens`，位于 `m29_materialization` 之后、`m29_asset_publish` 之前。
- 输出 schema `M29DesignTokenReport` version `0.1`。
- 输出 `colorTokens`、`textStyleTokens`、`radiusTokens`、`spacingTokens`、`warnings`、report-only invariants。
- batch validation 检查 design token report artifact。

不包含：

- 不写 DSL。
- 不绑定 Figma variables。
- 不做多页 token merge。
- 不做语义命名承诺。
- 不改变 materializer。
- 不按文件名、颜色、主题、文案、行业或固定 bbox 特化。

## Candidate Rules V1

颜色来源：

- DSL root/page background。
- DSL element style `fill` / `color`。
- 只统计 hex color，跳过 image/gradient。

文字样式来源：

- DSL text element `fontFamily`、`fontSize`、`fontWeight`、`lineHeight`、`color`。

圆角来源：

- DSL element style `radius` number 或 per-corner object。

间距来源：

- 同一父级 children 的相邻 x/y gaps。
- 只记录正 gap，不从截图语义推断 spacing。

输出是单页候选 token，不是设计系统变量。

## Validation

```bash
cd backend
uv run pytest tests/test_design_token_report.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
git diff --check
```

验收：

- Focused report tests 覆盖 empty/report-only、color token、text style token、radius token、spacing token、non-hex color skip。
- Upload pipeline stage timings 包含 `m29_design_tokens`。
- Production artifact profile 下 report 文件存在。
- 15 张真实样本全部 completed，required artifacts 全部存在。
- DSL/API/materialization response shape 不变。

## Result

已完成：

- 新增 `backend/app/design_token_report/`。
- 新增 upload-preview stage `m29_design_tokens`，位于 `m29_materialization` 之后、`m29_asset_publish` 之前。
- 新增 report artifact：

```text
storage/upload_previews/{taskId}/m29_design_tokens/design_token_report.json
```

保持 report-only：

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
materializationChanged=false
figmaVariablesBound=false
designSystemChanged=false
singlePageOnly=true
```

已验证：

```bash
cd backend
uv run pytest tests/test_design_token_report.py -q
# 6 passed

uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
# 47 passed

uv run pytest -q
# 267 passed

uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
# inputCount=15 completedTaskCount=15 failedTaskCount=0 missingArtifactCount=0
```

真实 batch ledger：

```text
backend/tmp/validation/upload_preview_batch_20260525_042023/upload_preview_batch_validation.json
```

batch 结果：

```text
totalVisibleReplayClaimCount=1762
totalVisibleOwnershipOverlapConflicts=0
totalSiblingGroupCandidateCount=354
totalLayoutEnergyCandidateCount=427
totalAutoLayoutAllowCandidateCount=344
totalDesignTokenCandidateCount=2218
all designTokenReport artifacts present=true
tokenTotals={color:939, text:918, radius:2, spacing:359}
```

本阶段未发现需要通过特化规则修补的问题。
