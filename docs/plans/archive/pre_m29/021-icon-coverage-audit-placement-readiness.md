# M21 Icon Coverage Audit And Placement Readiness Harness

- 状态：completed
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M21 在 M20 icon candidate extraction 后新增 icon coverage audit 合同层：审计已裁 icon 的覆盖情况、页面里疑似漏裁 icon hints，以及未来把 icon 放回 DSL/Figma 前的 readiness 和 collision 风险。

M21 不是可见替换阶段。它不改变 Figma 可见输出，不新增可见 DSL 节点，不修改任何已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不把 M20 icon 放进画布，不做 SVG/icon semantic recognition，不做图标库匹配，不按中文文案特化，不接 AI，不引入 Pillow/OpenCV。

## Key Changes

- 新增 `IconCoverageAuditDocument v0.1`。
- 新增持久化目录 `backend/storage/icon_coverage_audits/{taskId}.json`。
- 新增 debug overlay 资产 `backend/storage/assets/{taskId}/debug/icon_coverage_overlay.png`。
- 新增只读接口 `GET /api/tasks/{taskId}/icon-coverage-audit`。
- 新增 SQLite 表 `icon_coverage_audit_results`。
- overlay PNG 写入现有 `assets` 表，role 固定为 `asset_icon_coverage_overlay`。
- 新增配置：
  - `ICON_COVERAGE_AUDIT_ENABLED=true`
  - `ICON_COVERAGE_OVERLAY_ENABLED=true`
  - `ICON_COVERAGE_MISSED_HINTS_ENABLED=true`
  - `ICON_COVERAGE_MIN_HINT_CONFIDENCE=0.60`
  - `ICON_COVERAGE_MAX_MISSED_HINTS=80`
  - `ICON_COVERAGE_FOREGROUND_DISTANCE=32`
- 上传链路在 M20 icon candidate 后执行 M21 icon coverage audit。
- DSL 只追加顶层 M21 meta，不修改任何已有 element 或 DSL `assets`。

## Behavior

M21 对每个 M20 `status=candidate` icon 生成 placement：

```text
M20 icon bbox/asset/source
-> M16 component bbox/role
-> M15 binding ids
-> DSL visible text / cover / fallback bbox
-> M19 slice bbox
-> placement readiness
```

placement readiness 状态：

- `blocked`：asset 缺失、bbox 非法、component/text/binding 引用缺失，或与 visible text / cover 冲突。
- `needs_fallback_coordination`：几何安全，但仍在 fallback region 内，直接放回会重复显示。
- `needs_slice_coordination`：不在 fallback 内，但在 M19 slice 内，后续要选择 slice 还是 icon 分层。
- `review_required`：来源或角色不够明确。
- `ready_for_future_visible_icon`：引用、几何和 collision 都安全。

M21 还会在低成本区域生成 missedIconHints：

- header 左右边缘小前景块。
- card/preview/activity 右侧小箭头。
- bottom nav label 上方漏裁候选。
- shortcut card 文本左侧漏裁候选。
- 多行字段左侧疑似 icon。

missed hints 不裁 PNG、不写 icon asset，只进入 JSON 和 overlay。

## Overlay

M21 使用标准库 PNG 能力复制原图 RGB rows，并在 bbox 边缘画 2px 彩色框：

- 绿色：ready placement。
- 紫色：needs fallback coordination。
- 蓝色：needs slice coordination。
- 红色：blocked/review required placement。
- 黄色：missedIconHint。

overlay 不画文字标签；source、role、confidence 和原因都在 JSON 中查。

## DSL Contract

M21 只允许修改 DSL 顶层 `meta`：

```text
qualityFlags += m21_icon_coverage_audit
iconCoverageCandidateCount
iconCoveragePlacementCount
iconCoverageMissedHintCount
iconPlacementReadyCount
iconPlacementNeedsFallbackCoordinationCount
iconPlacementNeedsSliceCoordinationCount
iconPlacementBlockedCount
```

M21 不允许修改任何已有 element 的：

```text
name
meta
layout
style
content
source
imageFill
visible
children
```

M21 也不允许修改 DSL `assets` 数组。icon coverage overlay 只通过 `/icon-coverage-audit`、`/api/assets/{assetId}` 和 `/files/assets/{taskId}/debug/...` 暴露。

## API And Storage

`GET /api/tasks/{taskId}/icon-coverage-audit`：

- task 不存在 -> `TASK_NOT_FOUND`
- result 不存在或文件缺失 -> `ICON_COVERAGE_AUDIT_NOT_FOUND`
- completed -> 返回 `placements`、`missedIconHints`、`coverageOverlay`、`blockedIconCandidateIds`、`warnings`、`meta`
- failed/skipped -> 返回 `success: true`，并带 `status`、`warnings`、`meta`、`error`

新增错误码：

```text
ICON_COVERAGE_AUDIT_NOT_FOUND
ICON_COVERAGE_AUDIT_FAILED
ICON_COVERAGE_AUDIT_VALIDATION_FAILED
```

## Failure Strategy

- `ICON_COVERAGE_AUDIT_ENABLED=false` 时不生成 result，不改 DSL。
- M20 未 completed 时保存 skipped document，上传仍 completed。
- PNG decode unsupported 时记录 `png_pixel_decode_unsupported` warning，不让上传失败。
- overlay 生成或写入失败只记录 `coverage_overlay_write_failed` warning，不让上传失败。
- document validation failed 时保存 failed document，写 `error_logs(stage=icon_coverage_audit)`，`/dsl` 回退 M20 输出。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 默认上传生成 icon coverage audit report、overlay asset 和 DSL M21 meta。
- `ICON_COVERAGE_AUDIT_ENABLED=false` 不生成 report，DSL 保持 M20 输出。
- `/icon-coverage-audit` 覆盖 completed、TASK_NOT_FOUND、ICON_COVERAGE_AUDIT_NOT_FOUND。
- M20 source 映射到 nav/leading/title/field placementRole。
- fallback/slice/text/cover collision 产生正确 readiness。
- asset 缺失进入 blocked。
- header、bottom nav、card trailing 等 missedIconHints 可被报告，但不裁图。
- overlay PNG 可读、尺寸等于原图，bbox 边缘像素被染色。
- overlay asset 后，`/api/assets/{assetId}` 返回 `asset_icon_coverage_overlay`，静态 URL 可读取。
- M21 不新增可见 DSL 节点，不修改任何已有 element，不修改 DSL `assets`。

## Assumptions

- M21 默认开启，因为它不改变 Figma 可见输出。
- M21 只生成审计报告、debug overlay 和 DSL 顶层 meta。
- M21 不重新 OCR，不按中文文案判断。
- M21 不新增生产依赖，不使用 Pillow/OpenCV。
- M21 missedIconHints 只做审计，不裁图、不写 icon asset。
- M21 placements 只描述 `futureDslNodeHint`，不实际写入 DSL。
- M22 再根据 M21 overlay 和 missed hints 决定补哪些 icon detection 规则，或开始 visible icon fallback experiment。

## Verification

2026-05-17 已完成自动化和真实样例验证：

- `cd backend && uv run pytest` -> 139 passed。
- `pnpm run check` -> dsl-schema、renderer、figma-plugin typecheck/test/build 通过。
- `git diff --check` -> 通过。
- 使用 `/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/` 下 7 张 PNG 做真实百度 OCR smoke；7 个任务上传均 completed，M14-M21 报告均 completed。
- 七张图 M20 icon cropped 数量分别为 7、3、4、3、8、7、2，failed crop 均为 0。
- 七张图 M21 placement 数量分别为 7、3、4、3、8、7、2；全部因为 fallback 仍保留而进入 `needs_fallback_coordination`，blocked 均为 0。
- 真实 overlay 视觉复核后修正了两类误报：header status bar 时间/电池不再生成 missed hint；hidden `candidate_text` 和过大视觉块不再生成 missed hint。
- 最终基于真实 smoke 已保存合同重建 M21 overlay，summary 写入 `backend/storage/m21_student_smoke_20260517_154043_after_header_fix/m21_recheck_final_summary.json`。
