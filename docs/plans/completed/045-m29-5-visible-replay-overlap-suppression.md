# M29.5 Visible Replay Overlap Suppression

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

修复真实上传 `task_ed8387636f80` 中 ownership conservation report 暴露的同类 visible replay owner 重叠问题。这个修复属于 M29.5 replay plan 的 dedupe/permission 职责，不属于 materializer、Renderer 或 plugin。

## Source Evidence

`ownership_conservation_report.json` 显示：

```text
visibleReplayClaimCount = 97
conflictTypeCounts.visible_ownership_overlap = 9
```

冲突类型集中在：

```text
raster_icon vs raster_icon
control_background vs control_background
```

这说明多个 accepted visible replay items 正在主张同一或高度重叠的 foreground/support pixels。

## Scope

包含：

- 在 `backend/app/m29_replay_plan/` 中新增 visible overlap suppression。
- 只对同类 visible replay owner 做保守去重。
- 保持 existing near_equal duplicate suppression。
- 更新 M29.5 summary，暴露 overlap suppression count。
- 更新 ownership conservation regression。

不包含：

- 不改 M29.2 source object classification。
- 不改 materializer cleanup。
- 不改 Renderer/plugin。
- 不因 shape/text、shape/icon background overlap suppress。
- 不按颜色、主题、文案、文件名或固定 bbox 特化。

## Suppression Rule V1

可 suppress 的对象对必须满足：

```text
both finalReplayAction in {icon_replay, shape_replay}
same finalReplayAction
same pixelOwner
overlapRatio >= threshold
or containment ratio >= threshold
or primarySetRelation == near_equal
```

保留优先级：

```text
higher replay priority
then higher confidence
then larger area for icon
then larger/outer area for shape
then stable sourceObjectId
```

被 suppress item：

```text
finalReplayAction = suppress_duplicate
targetRole = None
cleanupTargets = []
reasons += visible_overlap_duplicate_suppressed
risks += visible_overlap_duplicate
relationEdgeIds includes explaining edge when available
```

## Validation

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_ownership_conservation.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
cd ..
git diff --check
```

真实上传验证：

```bash
curl -F "file=@backend/storage/uploads/task_ed8387636f80/original.png;type=image/png" \
  http://127.0.0.1:8000/api/upload-preview
```

验收：

- task completed。
- `m29_ownership_conservation/ownership_conservation_report.json` 存在。
- 同类 visible ownership overlap conflict 明显下降，目标为 0；若仍有 warning，必须说明是背景/前景允许关系还是下一阶段处理对象。
- materialization response shape 不变。

## Result

实现内容：

- 新增 `backend/app/m29_replay_plan/overlap.py`，只处理同类 visible replay owner overlap suppression。
- M29.5 在 node budget 前压制明显重复的 `icon_replay/icon_replay` 和 `shape_replay/shape_replay`。
- M29.5 summary 新增 `visibleOverlapSuppressedCount`。
- ownership conservation report 不再把小面积 bbox 擦边当成 visible ownership conflict。

真实上传验证：

```text
input: backend/storage/uploads/task_ed8387636f80/original.png
taskId: task_624dfba069bc
status: completed
m29_ownership_conservation: completed
visibleReplayClaimCount: 90
conflictCount: 0
visibleOverlapSuppressedCount: 7
```

Phase 1 前后对比：

```text
before: visible_ownership_overlap = 9
after:  visible_ownership_overlap = 0
```
