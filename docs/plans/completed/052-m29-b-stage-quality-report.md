# M29 B-Stage Quality Report

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

新增 report-only 的 M29 B-stage quality report。它汇总 ownership conservation、hierarchy、sibling group、layout energy、Auto Layout permission、design token 和 materialization summary，输出当前 B 阶段的质量、风险和 repair-cost 概览。

## Layer Diagnosis

source input：

```text
M29 ownership conservation report
M29 hierarchy candidate report
M29 sibling group candidate report
M29 layout energy report
M29 Auto Layout permission report
M29 design token report
M29 materialization report
```

decision point：

```text
quality score / repair cost estimate / risk counts / capability maturity summary
```

output surface：

```text
storage/upload_previews/{taskId}/m29_b_stage_quality/b_stage_quality_report.json
```

validation surface：

```text
pytest focused tests
upload-preview stage timing
15-image batch validation under /Users/luhui/Downloads/m29
```

## Scope

包含：

- 新增 `backend/app/b_stage_quality_report/` package。
- 新增 upload-preview stage `m29_b_stage_quality`，位于 `m29_design_tokens` 之后、`m29_asset_publish` 之前。
- 输出 schema `M29BStageQualityReport` version `0.1`。
- 输出 `qualitySummary`、`riskSummary`、`repairCost`、`capabilityMaturity`、`warnings`、report-only invariants。
- batch validation 检查 B-stage quality report artifact。

不包含：

- 不改 DSL。
- 不阻断 upload-preview。
- 不创建 Group/Frame/Auto Layout/Component/Instance/variables。
- 不改变 materializer。
- 不按文件名、颜色、主题、文案、行业或固定 bbox 特化。

## Quality Rules V1

质量分只作为诊断，不作为任务失败条件：

```text
baseScore = 1.0
- ownership conflicts
- hierarchy/group/layout warnings
- deferred/rejected Auto Layout permission
- token extraction gaps
- materialization warnings/skips
```

repair cost 只做相对估计：

```text
ownershipError cost > materializationWarning cost > deferredPermission cost > tokenGap cost
```

## Validation

```bash
cd backend
uv run pytest tests/test_b_stage_quality_report.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
git diff --check
```

验收：

- Focused report tests 覆盖 empty/report-only、ownership conflict penalty、permission defer cost、token coverage summary、materialization warning cost。
- Upload pipeline stage timings 包含 `m29_b_stage_quality`。
- Production artifact profile 下 report 文件存在。
- 15 张真实样本全部 completed，required artifacts 全部存在。
- DSL/API/materialization response shape 不变。

## Result

已完成：

- 新增 `backend/app/b_stage_quality_report/`。
- 新增 upload-preview stage `m29_b_stage_quality`，位于 `m29_design_tokens` 之后、`m29_asset_publish` 之前。
- 新增 report artifact：

```text
storage/upload_previews/{taskId}/m29_b_stage_quality/b_stage_quality_report.json
```

保持 report-only：

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
materializationChanged=false
blockingUpload=false
reportOnly=true
```

已验证：

```bash
cd backend
uv run pytest tests/test_b_stage_quality_report.py -q
# 6 passed

uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
# 47 passed

uv run pytest -q
# 273 passed

uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
# inputCount=15 completedTaskCount=15 failedTaskCount=0 missingArtifactCount=0
```

真实 batch ledger：

```text
backend/tmp/validation/upload_preview_batch_20260525_043029/upload_preview_batch_validation.json
```

batch 结果：

```text
totalVisibleReplayClaimCount=1762
totalVisibleOwnershipOverlapConflicts=0
totalSiblingGroupCandidateCount=354
totalLayoutEnergyCandidateCount=427
totalAutoLayoutAllowCandidateCount=344
totalDesignTokenCandidateCount=2218
totalBStageRepairCost=789
all bStageQualityReport artifacts present=true
qualityScoreRange=0.760..0.993
qualityScoreAverage=0.869
qualityGrades={high:5, medium:10}
```

本阶段未发现需要通过特化规则修补的问题。
