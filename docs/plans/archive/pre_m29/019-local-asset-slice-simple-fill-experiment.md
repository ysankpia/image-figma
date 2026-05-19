# M19 Local Asset Slice And Simple Fill Experiment Harness

- 状态：active
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M19 在 M18 `layer-separation-candidates` 后新增 local asset slice candidate 合同层，对低风险 component 生成本地 PNG slice，并在有可靠 `solid_color_fill` 证据时生成 filled slice PNG。

M19 仍不是正式局部 fallback 替换阶段。它不改变 Figma 可见输出，不删除 fallback，不新增可见 DSL 节点，不把实验 slice 写进 DSL `assets`，不创建真实 Figma group/component，不做 Auto Layout，不做图标、圆形、三角形、五角星或复杂图形重建，不做 AI inpainting，不引入 Pillow/OpenCV。

## Key Changes

- 新增 `AssetSliceCandidateDocument v0.1`。
- 新增持久化目录 `backend/storage/asset_slice_candidates/{taskId}.json`。
- 新增切片资产目录 `backend/storage/assets/{taskId}/slices/`。
- 新增只读接口 `GET /api/tasks/{taskId}/asset-slice-candidates`。
- 新增 SQLite 表 `asset_slice_results`。
- 生成的 slice PNG 写入现有 `assets` 表，role 为 `asset_slice_candidate` 或 `asset_slice_filled_candidate`。
- 新增配置：
  - `ASSET_SLICE_ENABLED=true`
  - `ASSET_SLICE_MAX_CANDIDATES=24`
  - `ASSET_SLICE_MIN_CONFIDENCE=0.70`
  - `ASSET_SLICE_MAX_AREA_RATIO=0.25`
  - `ASSET_SLICE_GENERATE_FILLED=true`
- 上传链路在 M18 layer separation 后执行 M19 asset slice candidate。
- DSL 只追加顶层 M19 meta，不修改任何已有 element 或 DSL `assets`。

## Behavior

M19 只消费 M18 事实，不重新理解图片语义：

```text
M18 candidate
-> M16 component confidence
-> original PNG crop
-> optional solid fill from M18 fillCandidate.targetBBoxes
```

第一版只切这些 M18 candidate：

- `status == candidate`
- `strategy == image_slice_with_simple_fill_candidate`
- component role 属于 `activity_card`、`shortcut_card`、`preview_card`、`tip_card`、`hero_profile`
- component confidence 不低于 `ASSET_SLICE_MIN_CONFIDENCE`
- bbox 在图片范围内，且面积不超过 `ASSET_SLICE_MAX_AREA_RATIO`

默认跳过 `primary_button`、`outline_button`、`badge`、`status_badge`、`summary_stat_card`、`bottom_nav_item`、`legend_group`、`bottom_nav`、`page_header` 等更适合 shape + editable text 的角色。

filled slice 只在 M18 `fillCandidate.enabled=true`、`mode=solid_color_fill`、颜色合法、target bbox 都落在 crop 内且面积安全时生成。否则只生成 original slice，并记录原因。

## DSL Contract

M19 只允许修改 DSL 顶层 `meta`：

```text
qualityFlags += m19_local_asset_slice_candidates
assetSliceCandidateCount
assetSliceFilledCandidateCount
assetSliceBlockedCount
assetSliceFailedCount
```

M19 不允许修改任何已有 element 的：

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

M19 也不允许修改 DSL `assets` 数组。实验 slice 只通过 `/asset-slice-candidates` 和 `/files/assets/{taskId}/slices/...` 暴露。

## API And Storage

`GET /api/tasks/{taskId}/asset-slice-candidates`：

- task 不存在 -> `TASK_NOT_FOUND`
- result 不存在或文件缺失 -> `ASSET_SLICE_NOT_FOUND`
- completed -> 返回 `slices`、`blockedComponentIds`、`warnings`、`meta`
- failed/skipped -> 返回 `success: true`，并带 `status`、`warnings`、`meta`、`error`

新增错误码：

```text
ASSET_SLICE_NOT_FOUND
ASSET_SLICE_FAILED
ASSET_SLICE_VALIDATION_FAILED
```

## Failure Strategy

- `ASSET_SLICE_ENABLED=false` 时不生成 result，不改 DSL。
- M18 未 completed 时保存 skipped document，上传仍 completed。
- 单个 crop/fill 失败只让该 slice `failed` 或降级为 original slice，不让 upload 失败。
- document validation failed 时保存 failed document，写 `error_logs(stage=asset_slice)`，`/dsl` 回退 M18 输出。
- 不支持的 PNG crop/fill 记录 `png_crop_unsupported` 或 `png_fill_unsupported`。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 默认上传生成 asset slice report 和 DSL M19 meta。
- `ASSET_SLICE_ENABLED=false` 不生成 report，DSL 保持 M18 输出。
- `/asset-slice-candidates` 覆盖 completed、TASK_NOT_FOUND、ASSET_SLICE_NOT_FOUND。
- `encode_rgb_png` 和 `crop_and_fill_png` 生成可读 PNG，并拒绝越界 fill。
- tip/shortcut 等低风险 slice role 生成 original slice 和 filled slice。
- primary button、badge、status badge、bottom nav item 等 shape/text role 默认跳过，不强行切图。
- bbox 过大、fill target 超出 crop 时记录 blocked 或 original-only。
- component 置信度低或超过 `ASSET_SLICE_MAX_CANDIDATES` 时记录 blocked，不生成 PNG。
- M19 不新增可见 DSL 节点，不修改任何已有 element，不修改 DSL `assets`。

## Assumptions

- M19 默认开启，因为它不改变 Figma 可见输出。
- M19 第一版只实现 `solid_color_fill`，不做边缘扩散或智能修复。
- M19 生成真实本地 PNG，但只是候选资产，不进入 Renderer 输入。
- M20 再考虑 partial fallback replacement。
