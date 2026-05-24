# M29 Sibling Group Candidate Report

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

新增 report-only 的 M29 sibling group candidate stage。它基于 M29.3 relation graph、M29.4 weak clusters、M29.5 visible replay plan 和 M29 hierarchy candidates，输出兄弟组候选，为后续 layout energy 提供输入证据。

## Layer Diagnosis

source input：

```text
M29.3.1 relation graph
M29.4 weak structural clusters
M29.5 replay plan
M29 hierarchy candidate report
```

decision point：

```text
sibling group membership / relation density / alignment / confidence / risk
```

output surface：

```text
storage/upload_previews/{taskId}/m29_sibling_groups/sibling_group_candidate_report.json
```

validation surface：

```text
pytest focused tests
upload-preview stage timing
15-image batch validation under /Users/luhui/Downloads/m29
```

## Scope

包含：

- 新增 `backend/app/sibling_group_candidate_report/` package。
- 新增 upload-preview stage `m29_sibling_groups`，位于 `m29_hierarchy_candidates` 之后、`m29_materialization` 之前。
- 输出 schema `M29SiblingGroupCandidateReport` version `0.1`。
- 输出 `siblingGroupCandidates`、`warnings`、report-only invariants。
- batch validation 检查 sibling report artifact。

不包含：

- 不创建 DSL Group/Frame。
- 不改变 M29.5 replay plan。
- 不改变 materializer。
- 不做 Layout Energy、Auto Layout、Component、Token、Variant、Vectorization。
- 不按文件名、颜色、主题、文案、行业或固定 bbox 特化。

## Candidate Rules V1

成员只来自 accepted visible M29.5 plan items：

```text
text_replay
image_replay
icon_replay
shape_replay
```

候选来源：

- M29.4 `row_like` / `column_like` / `repeated_item_like` cluster。
- M29.3 directed row/column relation connected components。

过滤：

- `suppress_duplicate`、`diagnostic_only`、`fallback_only`、`preserve_in_parent_raster` 不进入 sibling group。
- hierarchy selected parent-child 边不作为 sibling edge。
- `near_equal` 不进入 sibling group。
- 成员数小于 2 不输出。

score 只依赖：

```text
relation density
alignment signal
gap/near signal
member confidence
role pattern
M29.4 cluster support
```

## Validation

```bash
cd backend
uv run pytest tests/test_sibling_group_candidate_report.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
git diff --check
```

验收：

- Focused report tests 覆盖 empty/report-only、row group、column group、hierarchy parent-child exclusion、non-visible exclusion。
- Upload pipeline stage timings 包含 `m29_sibling_groups`。
- Production artifact profile 下 report 文件存在。
- 15 张真实样本全部 completed，required artifacts 全部存在。
- DSL/API/materialization response shape 不变。

## Result

已完成：

- 新增 `backend/app/sibling_group_candidate_report/`。
- 新增 upload-preview stage `m29_sibling_groups`，位于 `m29_hierarchy_candidates` 之后、`m29_materialization` 之前。
- 新增 report artifact：

```text
storage/upload_previews/{taskId}/m29_sibling_groups/sibling_group_candidate_report.json
```

保持 report-only：

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
materializationChanged=false
groupMaterializationPermission=false
```

已验证：

```bash
cd backend
uv run pytest tests/test_sibling_group_candidate_report.py -q
# 6 passed

uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
# 47 passed

uv run pytest -q
# 249 passed

uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
# inputCount=15 completedTaskCount=15 failedTaskCount=0 missingArtifactCount=0
```

真实 batch ledger：

```text
backend/tmp/validation/upload_preview_batch_20260525_034929/upload_preview_batch_validation.json
```

batch 结果：

```text
totalVisibleReplayClaimCount=1762
totalVisibleOwnershipOverlapConflicts=0
totalSiblingGroupCandidates=354
all siblingGroupCandidateReport artifacts present=true
```

本阶段未发现需要通过特化规则修补的问题。
