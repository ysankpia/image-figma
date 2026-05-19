# M20 Icon Candidate Extraction And Crop Harness

- 状态：completed
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M20 在 M19 local asset slice candidate 后新增 icon candidate extraction 合同层：基于 M15-M17 的结构索引和原始 PNG 像素，在 component 内部寻找高置信小型 icon bbox，并用现有标准库 `png_tools.crop_png()` 生成本地 icon PNG 候选资产。

M20 解决的是“icon 从哪里切”的问题，不是 SVG 识别阶段。它不改变 Figma 可见输出，不新增可见 DSL 节点，不删除 fallback，不把 icon asset 写入 DSL `assets`，不创建真实 Figma group/component，不做 Auto Layout，不做图标库匹配或 Lucide/Material 替换，不按中文文案特化，不接 AI，不引入 Pillow/OpenCV。

## Key Changes

- 新增 `IconCandidateDocument v0.1`。
- 新增持久化目录 `backend/storage/icon_candidates/{taskId}.json`。
- 新增 icon 资产目录 `backend/storage/assets/{taskId}/icons/`。
- 新增只读接口 `GET /api/tasks/{taskId}/icon-candidates`。
- 新增 SQLite 表 `icon_candidate_results`。
- 生成的 icon PNG 写入现有 `assets` 表，role 固定为 `asset_icon_candidate`。
- 新增配置：
  - `ICON_CANDIDATE_ENABLED=true`
  - `ICON_CANDIDATE_MIN_CONFIDENCE=0.70`
  - `ICON_CANDIDATE_MAX_CANDIDATES=64`
  - `ICON_CANDIDATE_MIN_SIZE=8`
  - `ICON_CANDIDATE_MAX_SIZE=96`
  - `ICON_CANDIDATE_FOREGROUND_DISTANCE=32`
  - `ICON_CANDIDATE_MAX_COMPONENT_AREA_RATIO=0.20`
- 上传链路在 M19 asset slice candidate 后执行 M20 icon candidate。
- DSL 只追加顶层 M20 meta，不修改任何已有 element 或 DSL `assets`。

## Behavior

M20 只消费已有事实，不扫整张图乱找 icon：

```text
M17 annotation.componentId
-> M16 component bbox/role/confidence
-> M15 binding / OCR block id
-> DSL visible_text / cover exclusion bbox
-> component-local search window
-> foreground connected component
-> crop_png
```

第一版高置信来源：

- `bottom_nav_label_above`：bottom nav label 上方的小型前景块。
- `shortcut_card_leading_icon`：shortcut card 文本簇左侧的小型前景块。
- `tip_title_leading_icon`：tip card 标题左侧的小型前景块。
- `field_label_leading_icon`：多行文本 component 的字段 label 左侧小型前景块。

第一版不输出 `home/search/user` 这类语义标签，不把 PNG icon 替换成 SVG。`component_local_visual_blob` 仅作为保留来源，不默认裁剪低置信区域。

基础门禁：

- component confidence 不低于 `ICON_CANDIDATE_MIN_CONFIDENCE`。
- component bbox 合法，且面积不超过 `ICON_CANDIDATE_MAX_COMPONENT_AREA_RATIO`。
- icon bbox width/height 在 `ICON_CANDIDATE_MIN_SIZE..ICON_CANDIDATE_MAX_SIZE` 内。
- icon bbox 必须在 component bbox 内。
- icon bbox 与 visible text / cover bbox IoU 不超过 0.10。
- `field_label_leading_icon` 和 `tip_title_leading_icon` 的最终 crop bbox 必须接近 icon 形态，避免把文字笔画、窄边或裁残图标当成高置信 icon。
- 同 component 内 IoU 大于 0.70 的重复候选只保留一个。
- 单任务实际裁剪数不超过 `ICON_CANDIDATE_MAX_CANDIDATES`。

## DSL Contract

M20 只允许修改 DSL 顶层 `meta`：

```text
qualityFlags += m20_icon_candidate_extraction
iconCandidateCount
iconCroppedAssetCount
iconBlockedCount
iconFailedCropCount
```

M20 不允许修改任何已有 element 的：

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

M20 也不允许修改 DSL `assets` 数组。icon PNG 只通过 `/icon-candidates`、`/api/assets/{assetId}` 和 `/files/assets/{taskId}/icons/...` 暴露，供 M21+ 决定是否进入可见渲染路径。

## API And Storage

`GET /api/tasks/{taskId}/icon-candidates`：

- task 不存在 -> `TASK_NOT_FOUND`
- result 不存在或文件缺失 -> `ICON_CANDIDATE_NOT_FOUND`
- completed -> 返回 `icons`、`blockedComponentIds`、`warnings`、`meta`
- failed/skipped -> 返回 `success: true`，并带 `status`、`warnings`、`meta`、`error`

新增错误码：

```text
ICON_CANDIDATE_NOT_FOUND
ICON_CANDIDATE_FAILED
ICON_CANDIDATE_VALIDATION_FAILED
```

## Failure Strategy

- `ICON_CANDIDATE_ENABLED=false` 时不生成 result，不改 DSL。
- M15/M16/M17 未 completed 时保存 skipped document，上传仍 completed。
- PNG decode unsupported 时记录 `png_pixel_decode_unsupported` warning，不让上传失败。
- 单个 icon crop 失败只让该 icon `failed`，document 仍可 completed。
- document validation failed 时保存 failed document，写 `error_logs(stage=icon_candidate)`，`/dsl` 回退 M19 输出。

## Test Plan

必须通过：

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

覆盖点：

- 默认上传生成 icon candidate report 和 DSL M20 meta。
- `ICON_CANDIDATE_ENABLED=false` 不生成 report，DSL 保持 M19 输出。
- `/icon-candidates` 覆盖 completed、TASK_NOT_FOUND、ICON_CANDIDATE_NOT_FOUND。
- `bottom_nav_label_above`、`shortcut_card_leading_icon`、`tip_title_leading_icon`、`field_label_leading_icon` 四类来源可裁剪高置信 icon。
- text bbox / cover bbox 本身不能被误裁成 icon。
- candidate limit、低置信、bbox 越界、bbox 过大或过小必须阻断或跳过。
- 生成 PNG asset 后，`/api/assets/{assetId}` 返回 `asset_icon_candidate`，静态 URL 可读取。
- M20 不新增可见 DSL 节点，不修改任何已有 element，不修改 DSL `assets`。

## Assumptions

- M20 默认开启，因为它不改变 Figma 可见输出。
- M20 第一版只裁 icon PNG，不识别 icon 语义，不转 SVG。
- M20 只基于结构、文字 bbox、组件 bbox 和局部像素证据，不按中文文案特化。
- M20 不处理 OCR 根本没覆盖到、且没有结构关系可定位的孤立 icon。
- M21+ 再考虑 icon annotation、visible icon fallback 或 partial fallback replacement。
