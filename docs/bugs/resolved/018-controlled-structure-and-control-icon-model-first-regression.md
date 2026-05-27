# Bug: Controlled Structure Groups Bind Tab Assets And Control Icons Stay Report-Only

- 状态：resolved
- 创建日期：2026-05-27
- 影响范围：M29 model-first interactive upload-preview materialization

## Summary

真实上传 `task_95a6381580e9` 中，底部 tab icon/text 被 `M29 C Group` 结构组绑定成额外可见组；同时上方 media action row 的四个纵向 icon+label action item 只保留了文字，图标没有进入 M29.2 source ownership，最终不可选。

## Reproduction

复现步骤：

1. 后端以 `UPLOAD_PREVIEW_RUNTIME_MODE=interactive`、`M29_PERCEPTION_MODEL_ENABLED=true` 运行。
2. 从 Figma plugin 上传资产总览截图。
3. 检查 `backend/storage/upload_previews/task_95a6381580e9/materialized_design/design.dsl.json`。
4. 可见 `m29_c_group_m29_sibling_group_0021`、`m29_c_group_m29_sibling_group_0023` 被写入 DSL root；同时 action row 的 `perception_candidate_0005`、`0008`、`0013`、`0017` 因 `content_region_too_large_for_control_background` 停在 `m29_perception_source_compiler`，没有转成 icon source。

## Root Cause

两个边界错误叠加：

1. `controlledStructureMaterialization` 把 hierarchy/sibling/layout 证据从诊断/结构权限面升级成真实 DSL group，改变了 root children，导致 tab/text/icon 被额外绑定。结构组不是 source owner，不应该创建可见 owner 节点。
2. `perception_source_compiler` 只有横向 control child icon 和 leading-icon 推断路径，缺少“纵向 icon 在上、OCR label 在下”的 action tile source ownership path。真实 action tile 被模型框住后，compiler 因内容区域过大拒绝整块 tile，但没有从 label 上方像素推导 icon source。

## Fix

修复方案：

- Controlled structure 只保留 report，不修改 DSL root，不创建可见 group。
- Perception source compiler 增加通用 parent-control child icon 接纳条件：已编译 control parent containment、低面积、模型低分阈值、可接受 text-overlap/edge-overlap，进入 `raster_icon / icon_replay`。
- Perception source compiler 增加 vertical label tile path：单个 OCR label 位于候选底部时，在 label 上方 ROI 做前景连通域，生成 `raster_icon / icon_replay`；候选整块仍 report-only，不当成背景或按钮。
- 所有新增 icon source 仍流经 M29.2 -> M29.3/M29.4 -> M29.5 -> materializer。

## Regression Guard

- `tests/test_m29_plan_materializer.py` 覆盖 controlled structure report 不得创建 visible DSL group。
- `tests/test_perception_source_compiler.py` 覆盖已接受控件内部低分小 icon 可进入 source ownership，text-sized 候选仍被拒绝；并覆盖 vertical icon-over-label tile 只生成 icon source、不 replay 整块 tile。

## Validation Evidence

```bash
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_plan_materializer.py tests/test_m29_perception_fate_trace.py tests/test_m29_replay_plan.py -q
# 73 passed

git diff --check
# pass
```

真实样本复跑：

```bash
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /tmp/m29-070-retest2.UBmzF9 \
  --poll-timeout 300
```

结果：

```text
taskId=task_a63cb7885ae6
completedTaskCount=1
backendCrashCount=0
ownershipConflictCount=0
compiledSourceObjectCount=23
compiledRasterIconCount=8
plannedIconReplayCount=25
materializedVisibleNodeCount=139
controlledStructureMaterializationChanged=false
```

Artifact inspection:

```text
No m29_controlled_structure_group remains in design.dsl.json root children.
Action row icons are materialized as m29_symbol_0052, m29_symbol_0053, m29_symbol_0054, and m29_symbol_0055.
Each icon traces through perception_candidate_*:vertical_label_icon -> M29.2 raster_icon -> M29.5 icon_replay -> materializer.
```

## Prevention Notes

结构证据和 fate trace 都是诊断/权限面，不能成为 DSL visible owner。模型候选也不能直连 materializer，必须先进入 M29.2，再由 M29.5 replay/cleanup 授权。
