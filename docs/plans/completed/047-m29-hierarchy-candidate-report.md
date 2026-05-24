# M29 Hierarchy Candidate Report

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

新增一个 report-only 的 M29 hierarchy candidate stage，用当前 M29.2 source objects、M29.3 relation graph 和 M29.5 replay plan 生成可审计的 parent/child 候选。该阶段只报告结构证据，不创建 DSL group/frame，不改变 replay plan，不改变 materializer。

## Layer Diagnosis

source input：

```text
M29.2 sourceObjects
M29.3.1 relation graph
M29.5 replay plan
```

decision point：

```text
candidate parent score / child membership / confidence / risk
```

output surface：

```text
storage/upload_previews/{taskId}/m29_hierarchy_candidates/hierarchy_candidate_report.json
```

validation surface：

```text
pytest focused tests
upload-preview stage timing
15-image batch validation under /Users/luhui/Downloads/m29
```

## Scope

包含：

- 新增 `backend/app/hierarchy_candidate_report/` package。
- 新增 upload-preview stage `m29_hierarchy_candidates`，位于 `m29_ownership_conservation` 之后、`m29_materialization` 之前。
- 输出 schema `M29HierarchyCandidateReport` version `0.1`。
- 输出 `containerCandidates`、`parentCandidates`、`warnings`、`meta`。
- summary 必须包含 report-only invariant：

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
materializationChanged=false
```

不包含：

- 不创建 DSL group/frame。
- 不改变 M29.5 replay plan。
- 不改变 materializer。
- 不做 Auto Layout、Component、Token、Variant、Vectorization。
- 不按文件名、颜色、主题、文案、行业或固定 bbox 特化。

## Candidate Rules V1

父级候选只来自有物理容器意义的 source object：

```text
shape_replay / image_replay visible plan items
or preserve_raster media source objects
```

子级候选来自 accepted visible replay plan items：

```text
text_replay
image_replay
icon_replay
shape_replay
```

约束：

- parent 与 child 不能同一个 source object。
- `suppress_duplicate`、`diagnostic_only`、`fallback_only`、`preserve_in_parent_raster` 不作为 visible child。
- `near_equal` 不构成 hierarchy。
- containment 优先，其次高 overlap ratio。
- 每个 child 只选择最小/最紧的 best parent candidate；完整候选仍可在 report 中保留。

父级 score 只依赖：

```text
containment ratio
parent oversize
padding balance
parent action/kind
relation primary/secondary metrics
```

## Validation

```bash
cd backend
uv run pytest tests/test_hierarchy_candidate_report.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
git diff --check
```

验收：

- Focused report tests 覆盖 empty/report-only、shape contains text、media contains text/icon、best parent 选择、non-visible items 不参与。
- Upload pipeline stage timings 包含 `m29_hierarchy_candidates`。
- Production artifact profile 下 report 文件存在。
- 15 张真实样本全部 completed，required artifacts 全部存在。
- DSL/API/materialization response shape 不变。

## Result

实现内容：

- 新增 `backend/app/hierarchy_candidate_report/` report-only package。
- 新增 upload-preview stage：

```text
m29_ownership_conservation
-> m29_hierarchy_candidates
-> m29_materialization
```

- 新增 artifact：

```text
storage/upload_previews/{taskId}/m29_hierarchy_candidates/hierarchy_candidate_report.json
```

- report 输出 `containerCandidates`、`parentCandidates`、`selectedParentCandidates`、`warnings` 和 report-only invariants。
- batch validation ledger 增加 hierarchy report artifact 检查。

验证：

```text
uv run pytest tests/test_hierarchy_candidate_report.py -q
4 passed

uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
47 passed

uv run pytest -q
243 passed
```

真实 15 图 batch：

```text
ledger: backend/tmp/validation/upload_preview_batch_20260525_032636/upload_preview_batch_validation.json
inputCount: 15
completedTaskCount: 15
failedTaskCount: 0
missingArtifactCount: 0
totalVisibleOwnershipOverlapConflicts: 0
hierarchyCandidateReport artifacts: all present
```
