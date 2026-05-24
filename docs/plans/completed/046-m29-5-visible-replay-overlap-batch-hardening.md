# M29.5 Visible Replay Overlap Batch Hardening

- 状态：completed
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

用 `/Users/luhui/Downloads/m29` 全部 15 张 PNG 的真实 upload-preview 批量验证结果，继续修复 M29.5 visible replay ownership overlap。这个阶段仍属于 replay plan / cleanup authorization 层，不属于 materializer、Renderer 或 plugin。

## Source Evidence

批量验证命令：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
```

ledger：

```text
backend/tmp/validation/upload_preview_batch_20260525_024410/upload_preview_batch_validation.json
```

结果：

```text
inputCount = 15
completedTaskCount = 15
failedTaskCount = 0
missingArtifactCount = 0
ownershipConflictTypeCounts.visible_ownership_overlap = 71
```

残留冲突主要来自：

```text
image_replay/text_replay overlaps
image_replay/icon_replay overlaps
image_replay/shape_replay overlaps
image_replay/image_replay containment/overlap
少量 text/text 和 shape/shape overlap
```

这说明 Phase 1 的同类 icon/shape overlap suppression 只修了单样本暴露的问题；全样本仍需要更完整的 replay owner 守恒策略。

## Scope

包含：

- 扩展 M29.5 visible overlap suppression 和 cleanup authorization。
- 处理 nested media duplicate、media-contained foreground/text cleanup、同类 text/shape 残留 duplicate。
- 更新 ownership conservation 的 explainable overlap 规则，使它只报告真实未解释冲突。
- 增加 focused regression tests。
- 重新跑 15 图 batch validation。

不包含：

- 不改 materializer replay 顺序或 cleanup 执行逻辑。
- 不创建 group/frame/layout/component。
- 不按文件名、颜色、主题、文案、行业或固定 bbox 特化。
- 不把 warning 静默吞掉；必须由 M29.5 plan relation/cleanup/suppression 解释。

## Generic Rules

规则必须只依赖：

```text
finalReplayAction
pixelOwner
visualKind
bbox relation metrics
M29.3 primary/secondary relation
M29.5 cleanupTargets
```

允许解释或 suppress 的关系：

- `image_replay` 与 `text_replay` overlap：如果 text bbox 与 media bbox 有实质交集，M29.5 必须给 text 增加 `copied_image_asset` cleanup target；否则 ownership report 继续记录 warning。
- `image_replay` 与 `icon_replay` / `shape_replay` overlap：如果 foreground/support 很大比例在 media 内部，M29.5 必须给 foreground/support 增加 `copied_image_asset` cleanup target。
- `image_replay` 与 `image_replay` nested/strong overlap：内层或低优先级 media 进入 `suppress_duplicate`，除非后续有明确多媒体并列证据。
- 同类 `text_replay/text_replay`、`shape_replay/shape_replay` 残留明显 overlap：低优先级 item 进入 `suppress_duplicate`。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_ownership_conservation.py -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
uv run pytest -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
cd ..
git diff --check
```

验收：

- 15 张真实样本全部 completed。
- required artifacts 全部存在。
- `ownershipConflictTypeCounts.visible_ownership_overlap = 0`，或残留必须明确记录为非本阶段可安全解释的问题并停止后续 phase。
- DSL/API/materialization response shape 不变。

## Result

实现内容：

- M29.5 copied-image cleanup authorization 支持 text 与 preserve-raster media 的实质 overlap，不再只依赖 strict containment。
- M29.5 visible overlap suppression 覆盖：
  - nested/overlapping `image_replay/image_replay`;
  - residual `text_replay/text_replay`;
  - `image_replay/icon_replay`;
  - `text_replay/icon_replay`;
  - 原有 `icon_replay/icon_replay` 与 `shape_replay/shape_replay`。
- Ownership conservation 将 source-proven `shape_replay` behind `image_replay` 视为 explainable background/foreground overlap，仍保持 report-only。

验证：

```text
uv run pytest tests/test_m29_replay_plan.py tests/test_ownership_conservation.py -q
28 passed

uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
47 passed

uv run pytest -q
239 passed
```

真实 15 图 batch：

```text
ledger: backend/tmp/validation/upload_preview_batch_20260525_031324/upload_preview_batch_validation.json
inputCount: 15
completedTaskCount: 15
failedTaskCount: 0
missingArtifactCount: 0
totalVisibleReplayClaimCount: 1762
totalVisibleOwnershipOverlapConflicts: 0
ownershipConflictTypeCounts: {}
```
