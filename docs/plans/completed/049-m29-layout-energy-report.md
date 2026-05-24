# M29 Layout Energy Report

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

新增 report-only 的 M29 layout energy stage。它基于 M29.5 visible replay plan、M29 hierarchy candidates 和 M29 sibling group candidates，对候选 group/container 计算 row、column、grid、overlay、absolute 的 layout energy，为后续 Auto Layout permission report 提供输入证据。

## Layer Diagnosis

source input：

```text
M29.5 replay plan
M29 hierarchy candidate report
M29 sibling group candidate report
```

decision point：

```text
layout subject membership / row energy / column energy / grid energy / overlay energy / absolute energy / best model / confidence / drift risk
```

output surface：

```text
storage/upload_previews/{taskId}/m29_layout_energy/layout_energy_report.json
```

validation surface：

```text
pytest focused tests
upload-preview stage timing
15-image batch validation under /Users/luhui/Downloads/m29
```

## Scope

包含：

- 新增 `backend/app/layout_energy_report/` package。
- 新增 upload-preview stage `m29_layout_energy`，位于 `m29_sibling_groups` 之后、`m29_materialization` 之前。
- 输出 schema `M29LayoutEnergyReport` version `0.1`。
- 输出 `layoutSubjects`、`layoutEnergyCandidates`、`warnings`、report-only invariants。
- batch validation 检查 layout energy report artifact。

不包含：

- 不生成 Auto Layout。
- 不创建 DSL Group/Frame。
- 不改变 M29.5 replay plan。
- 不改变 materializer。
- 不做 Component、Token、Variant、Vectorization。
- 不按文件名、颜色、主题、文案、行业或固定 bbox 特化。

## Candidate Rules V1

subject 来源：

- `siblingGroupCandidates`：成员来自 `memberSourceObjectIds`。
- `selectedParentCandidates`：同一 parent 下的 visible children 聚合为 container subject。

成员 bbox 来源只使用 M29.5 visible plan items：

```text
text_replay
image_replay
icon_replay
shape_replay
```

energy 模型：

```text
row
column
grid
overlay
absolute
```

输出只说明哪个模型当前能量较低、置信度如何、风险是什么；不授予 Auto Layout 权限。

## Validation

```bash
cd backend
uv run pytest tests/test_layout_energy_report.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
git diff --check
```

验收：

- Focused report tests 覆盖 empty/report-only、row energy、column energy、grid candidate、hierarchy container subject、non-visible exclusion。
- Upload pipeline stage timings 包含 `m29_layout_energy`。
- Production artifact profile 下 report 文件存在。
- 15 张真实样本全部 completed，required artifacts 全部存在。
- DSL/API/materialization response shape 不变。

## Result

已完成：

- 新增 `backend/app/layout_energy_report/`。
- 新增 upload-preview stage `m29_layout_energy`，位于 `m29_sibling_groups` 之后、`m29_materialization` 之前。
- 新增 report artifact：

```text
storage/upload_previews/{taskId}/m29_layout_energy/layout_energy_report.json
```

保持 report-only：

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
materializationChanged=false
autoLayoutPermission=false
```

已验证：

```bash
cd backend
uv run pytest tests/test_layout_energy_report.py -q
# 6 passed

uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
# 47 passed

uv run pytest -q
# 255 passed

uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
# inputCount=15 completedTaskCount=15 failedTaskCount=0 missingArtifactCount=0
```

真实 batch ledger：

```text
backend/tmp/validation/upload_preview_batch_20260525_035952/upload_preview_batch_validation.json
```

batch 结果：

```text
totalVisibleReplayClaimCount=1762
totalVisibleOwnershipOverlapConflicts=0
totalSiblingGroupCandidateCount=354
totalLayoutEnergyCandidateCount=427
all layoutEnergyReport artifacts present=true
bestModelCounts={column:63, grid:46, row:318}
```

本阶段未发现需要通过特化规则修补的问题。
