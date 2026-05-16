# M18 Component-Aware Layer Separation Candidate Harness

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M18 在 M17 `component-annotations` 后新增 layer separation candidate 合同层，基于已有结构索引判断每个 component 后续应如何分层，并为纯色或低复杂背景文字生成 simple fill candidate。

M18 不是切图阶段。它不删除 fallback，不新增可见 DSL 节点，不创建真实 Figma group/component，不做 Auto Layout，不做图标、圆形、三角形、五角星或复杂图形重建，不做 AI inpainting，不引入 Pillow/OpenCV。`draw-ui-main` 只作为策略参考，不复制脚本或依赖。

## Key Changes

- 新增 `LayerSeparationDocument v0.1`。
- 新增持久化目录 `backend/storage/layer_separation_candidates/{taskId}.json`。
- 新增只读接口 `GET /api/tasks/{taskId}/layer-separation-candidates`。
- 新增 SQLite 表 `layer_separation_results`。
- 新增配置：
  - `LAYER_SEPARATION_ENABLED=true`
  - `LAYER_SEPARATION_MIN_CONFIDENCE=0.70`
  - `LAYER_SEPARATION_SIMPLE_FILL_TOLERANCE=24`
  - `LAYER_SEPARATION_MAX_COMPONENT_AREA_RATIO=0.35`
- 上传链路在 M17 component annotation 后执行 M18 layer separation。
- DSL 只追加顶层 M18 meta，不修改任何已有 element。

## Behavior

M18 只消费已有事实，不重新理解图片语义：

```text
M17 annotation.componentId
-> M16 component.id
-> M15 binding.id
-> binding.ocrBlockId
-> M14 decision.ocrBlockId
-> DSL visible_text_*/cover_*/text_* element ids
```

背景证据优先级：

1. M14 accepted decision 的 `background`、`expandedBBox`、`quality` 和 `strategy`。
2. 现有 cover element 的 `style.fill` 和 `layout`。
3. 仓库已有标准库 PNG pixel sampler 的低成本局部采样。
4. 仍无证据时记录 `background.kind=unknown`。

第一版稳定生成 `solid_color_fill` candidate。`local_edge_fill` 只保留枚举，不在证据不足时生成。

角色倾向：

- `badge`、`status_badge`、`primary_button`、`outline_button`、`summary_stat_card`、`bottom_nav_item` 优先 `shape_background_plus_editable_text`。
- `activity_card`、`shortcut_card`、`preview_card`、`tip_card`、`hero_profile` 有稳定 fill 时为 `image_slice_with_simple_fill_candidate`。
- 背景复杂但文字可追踪时为 `image_slice_with_repair_required`。
- 缺少 replacement/background 证据时为 `image_slice_with_embedded_text`。
- 无 annotated text 时为 `image_slice_without_text`。
- fallback region 只进入 `fallbackContexts`，不生成业务 candidate。

## DSL Contract

M18 只允许修改 DSL 顶层 `meta`：

```text
qualityFlags += m18_layer_separation_candidates
layerSeparationCandidateCount
layerSeparationFillCandidateCount
layerSeparationRepairRequiredCount
layerSeparationEmbeddedTextCount
layerSeparationBlockedCount
```

M18 不允许修改任何已有 element 的：

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

## API And Storage

`GET /api/tasks/{taskId}/layer-separation-candidates`：

- task 不存在 -> `TASK_NOT_FOUND`
- result 不存在或文件缺失 -> `LAYER_SEPARATION_NOT_FOUND`
- completed -> 返回 `candidates`、`fallbackContexts`、`blockedComponentIds`、`warnings`、`meta`
- failed/skipped -> 返回 `success: true`，并带 `status`、`warnings`、`meta`、`error`

新增错误码：

```text
LAYER_SEPARATION_NOT_FOUND
LAYER_SEPARATION_FAILED
LAYER_SEPARATION_VALIDATION_FAILED
```

## Failure Strategy

- `LAYER_SEPARATION_ENABLED=false` 时不生成 result，不改 DSL。
- M15/M16/M17 未 completed 时保存 skipped document，上传仍 completed。
- exception 或 validation failed 时保存 failed document，写 `error_logs(stage=layer_separation)`，`/dsl` 回退 M17 输出。
- PNG pixel decode unsupported 时不失败，记录 `png_pixel_decode_unsupported` 或缺少背景采样证据。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 默认上传生成 layer separation report 和 DSL M18 meta。
- `LAYER_SEPARATION_ENABLED=false` 不生成 report，DSL 保持 M17 输出。
- `/layer-separation-candidates` 覆盖 completed、TASK_NOT_FOUND、LAYER_SEPARATION_NOT_FOUND。
- primary button、badge/status badge、outline button 和 bottom nav label 可生成 simple fill candidate。
- shortcut/tip/preview 等容器在低风险背景下生成 simple fill candidate，复杂背景进入 repair required。
- fallback region 只作为 fallback context，不生成业务 candidate。
- component 过大、低置信度或 bottom nav fill target 侵入 icon 区域时 blocked。
- M18 不新增可见 DSL 节点，不改任何已有 element 字段，只改 DSL 顶层 meta。

## Assumptions

- 用户已选择方案 B：分层策略报告 + 简单填充候选，但不改变画布。
- simple fill candidate 第一版只写 JSON 合同，不生成填充后的 PNG 预览资产。
- M18 默认开启，因为它不改变可见输出。
- M18 不引入新依赖，不使用 Pillow/OpenCV。
- M18 不处理 OCR 根本没识别到的文字。
- M19 再考虑 local asset slice + simple fill 实验。
- M20 再考虑 partial fallback replacement。
