# M29 Auto Layout Permission Report

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

新增 permission-only 的 M29 Auto Layout permission stage。它基于 M29 layout energy report，把候选 subject 分成 `allow_candidate`、`defer`、`reject`，为未来 Figma Auto Layout materialization 提供明确权限证据。

## Layer Diagnosis

source input：

```text
M29 layout energy report
```

decision point：

```text
auto layout permission / recommended axis / energy threshold / confidence / risk / denial reason
```

output surface：

```text
storage/upload_previews/{taskId}/m29_auto_layout_permission/auto_layout_permission_report.json
```

validation surface：

```text
pytest focused tests
upload-preview stage timing
15-image batch validation under /Users/luhui/Downloads/m29
```

## Scope

包含：

- 新增 `backend/app/auto_layout_permission_report/` package。
- 新增 upload-preview stage `m29_auto_layout_permission`，位于 `m29_layout_energy` 之后、`m29_materialization` 之前。
- 输出 schema `M29AutoLayoutPermissionReport` version `0.1`。
- 输出 `permissionItems`、`warnings`、permission-only invariants。
- batch validation 检查 permission report artifact。

不包含：

- 不写 DSL。
- 不创建 Auto Layout。
- 不创建 Group/Frame。
- 不改变 M29.5 replay plan。
- 不改变 materializer。
- 不推 responsive inference。
- 不按文件名、颜色、主题、文案、行业或固定 bbox 特化。

## Permission Rules V1

只对 layout energy 的 `row` / `column` / `grid` 模型做候选许可：

```text
allow_candidate:
  confidence in {high, medium}
  energy <= threshold
  no high_layout_energy
  no absolute_layout_fallback

defer:
  model supported but confidence/energy/risk 不够稳定

reject:
  overlay/absolute 或成员数不足/缺少 subject
```

该 permission 只说明“未来可以尝试自动布局”，不等于当前 materialization 权限。

## Validation

```bash
cd backend
uv run pytest tests/test_auto_layout_permission_report.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
git diff --check
```

验收：

- Focused report tests 覆盖 empty/permission-only、row allow、column allow、grid allow、high energy defer、absolute reject。
- Upload pipeline stage timings 包含 `m29_auto_layout_permission`。
- Production artifact profile 下 report 文件存在。
- 15 张真实样本全部 completed，required artifacts 全部存在。
- DSL/API/materialization response shape 不变。

## Result

已完成：

- 新增 `backend/app/auto_layout_permission_report/`。
- 新增 upload-preview stage `m29_auto_layout_permission`，位于 `m29_layout_energy` 之后、`m29_materialization` 之前。
- 新增 report artifact：

```text
storage/upload_previews/{taskId}/m29_auto_layout_permission/auto_layout_permission_report.json
```

保持 permission-only：

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
materializationChanged=false
autoLayoutCreated=false
permissionOnly=true
```

已验证：

```bash
cd backend
uv run pytest tests/test_auto_layout_permission_report.py -q
# 6 passed

uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
# 47 passed

uv run pytest -q
# 261 passed

uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
# inputCount=15 completedTaskCount=15 failedTaskCount=0 missingArtifactCount=0
```

真实 batch ledger：

```text
backend/tmp/validation/upload_preview_batch_20260525_040902/upload_preview_batch_validation.json
```

batch 结果：

```text
totalVisibleReplayClaimCount=1762
totalVisibleOwnershipOverlapConflicts=0
totalSiblingGroupCandidateCount=354
totalLayoutEnergyCandidateCount=427
totalAutoLayoutAllowCandidateCount=344
all autoLayoutPermissionReport artifacts present=true
permissionCounts={allow_candidate:344, defer:83}
recommendedModelCounts={column:63, grid:46, row:318}
```

本阶段未发现需要通过特化规则修补的问题。
