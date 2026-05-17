# 可靠性

v0.1 的可靠性目标是稳定跑通主链路，而不是建设复杂平台。

## Task State

任务必须有明确状态：

- `pending`
- `uploaded`
- `processing`
- `completed`
- `failed`

任务必须有明确阶段：

- `upload`
- `preprocess`
- `ocr`
- `ai_analyze`
- `asset_crop`
- `dsl_build`
- `dsl_validate`
- `render`
- `completed`
- `failed`

## Failure Strategy

局部失败优先 fallback，不让整页失败。

M8 primitive extraction 是可观测的非关键路径：

- `fake` provider 正常情况下应 completed。
- `openai` provider 缺 key、超时、坏 JSON、空结果时，primitive result 可为 `failed` 或 `partial`。
- primitive failure 写入 `error_logs` 和 `primitive_results`。
- primitive failure 不影响 `/api/tasks/{taskId}/dsl`。

M10 OCR 和 DSL patch 也是可观测的非关键路径：

- OCR failed 时写入 `ocr_results` 和 `error_logs`。
- 百度 PP-OCRv5 token 缺失、远端失败、429、超时或 JSONL 异常时，OCR result 为 `failed`，不让上传任务失败。
- Patch failed 时写入 `dsl_patch_results` 和 `error_logs`。
- Patch validation failed 时 `/dsl` 回退 base DSL。
- Hidden text candidates 不允许破坏 fallback 视觉输出。

M14 text replacement 是可观测的非关键路径：

- 默认 `TEXT_REPLACEMENT_MODE=debug` 不改变可见 DSL。
- `TEXT_REPLACEMENT_MODE=apply` 只阻断 high-risk replacement。
- high-risk accepted replacement 会被记录为 blocked，不进入 DSL；medium-risk replacement 会记录 caution 但仍可应用。
- UI-aware sampling 只在标准采样出现可救失败时尝试局部策略，不全局放宽背景容差。
- replacement failed/skipped 写入 `text_replacement_results` 和 `error_logs`。
- replacement validation failed 时 `/dsl` 回退 M10/M9 输出。
- fallback region 必须始终保留。

M15 text binding 是可观测的非关键路径：

- 默认 `TEXT_BINDING_ENABLED=true`，但不改变可见 DSL。
- binding failed/skipped 写入 `text_binding_results` 和 `error_logs`。
- binding validation failed 时 `/dsl` 回退 M14 输出，只是不追加 M15 meta。
- inferred containers 只存在于 binding report，不回写 visual primitives。

M16 component structure 是可观测的非关键路径：

- 默认 `COMPONENT_STRUCTURE_ENABLED=true`，但不改变可见 DSL。
- structure failed/skipped 写入 `component_structure_results` 和 `error_logs`。
- structure validation failed 时 `/dsl` 回退 M15 输出，只是不追加 M16 meta。
- component candidates 和 layout groups 只存在于 structure report，不创建 Figma Component/Instance，不删除 fallback region。

M17 component annotation 是可观测的非关键路径：

- 默认 `COMPONENT_ANNOTATION_ENABLED=true`，但不改变 Figma 可见输出。
- annotation failed/skipped 写入 `component_annotation_results` 和 `error_logs`。
- annotation validation failed 时 `/dsl` 回退 M16 输出，只是不追加 M17 meta/name。
- M17 只修改已有 DSL element 的 `name` 和 `meta`；不能修改 layout、style、content、source、imageFill 或 visible。
- group hints 只存在于 annotation report，不创建真实 Figma group。
- M17 不切图、不删除 fallback region、不创建 Figma Component/Instance 或 Auto Layout。

M18 layer separation candidate 是可观测的非关键路径：

- 默认 `LAYER_SEPARATION_ENABLED=true`，但不改变 Figma 可见输出。
- separation failed/skipped 写入 `layer_separation_results` 和 `error_logs`。
- separation validation failed 时 `/dsl` 回退 M17 输出，只是不追加 M18 meta。
- M18 只修改 DSL 顶层 `meta`；不能修改任何已有 element 的 name、meta、layout、style、content、source、imageFill、visible 或 children。
- simple fill candidate 只存在于 separation report，不生成实际 PNG，不切图，不删除 fallback。
- PNG pixel decode unsupported 只记录 warning，不让上传失败。
- M18 不做 AI inpainting，不引入 Pillow/OpenCV，不重建图标、圆形、三角形、五角星或复杂图形。

M19 local asset slice candidate 是可观测的非关键路径：

- 默认 `ASSET_SLICE_ENABLED=true`，但不改变 Figma 可见输出。
- asset slice failed/skipped 写入 `asset_slice_results` 和 `error_logs`。
- asset slice validation failed 时 `/dsl` 回退 M18 输出，只是不追加 M19 meta。
- M19 只修改 DSL 顶层 `meta`；不能修改任何已有 element，也不能修改 DSL `assets` 数组。
- 生成的 slice PNG 只作为实验资产存在于 storage 和 `/asset-slice-candidates` 报告里。
- 单个 slice crop/fill 失败不能让 upload 失败。
- M19 不做正式局部 fallback 替换，不删除 fallback，不做 AI inpainting，不引入 Pillow/OpenCV，不重建图标、圆形、三角形、五角星或复杂图形。

M20 icon candidate extraction 是可观测的非关键路径：

- 默认 `ICON_CANDIDATE_ENABLED=true`，但不改变 Figma 可见输出。
- icon candidate failed/skipped 写入 `icon_candidate_results` 和 `error_logs`。
- icon candidate validation failed 时 `/dsl` 回退 M19 输出，只是不追加 M20 meta。
- M20 只修改 DSL 顶层 `meta`；不能修改任何已有 element，也不能修改 DSL `assets` 数组。
- 生成的 icon PNG 只作为候选资产存在于 storage 和 `/icon-candidates` 报告里。
- 单个 icon crop 失败不能让 upload 失败。
- PNG pixel decode unsupported 只记录 warning，不让上传失败。
- M20 不做 SVG/icon 语义识别，不做图标库匹配，不做可见 icon replacement，不删除 fallback，不做 AI inpainting，不引入 Pillow/OpenCV，不重建圆形、三角形、五角星或复杂图形。

M21 icon coverage audit 是可观测的非关键路径：

- 默认 `ICON_COVERAGE_AUDIT_ENABLED=true`，但不改变 Figma 可见输出。
- icon coverage audit failed/skipped 写入 `icon_coverage_audit_results` 和 `error_logs`。
- icon coverage audit validation failed 时 `/dsl` 回退 M20 输出，只是不追加 M21 meta。
- M21 只修改 DSL 顶层 `meta`；不能修改任何已有 element，也不能修改 DSL `assets` 数组。
- 生成的 overlay PNG 只作为调试资产存在于 storage 和 `/icon-coverage-audit` 报告里。
- overlay 生成或写入失败只记录 warning，不能让 upload 失败。
- PNG pixel decode unsupported 只记录 warning，不让上传失败。
- M21 不把 M20 icon 放进画布、不删除 fallback、不做 SVG/icon 语义识别、不做图标库匹配、不按中文文案特化、不做 AI inpainting、不引入 Pillow/OpenCV。

M22 icon gap candidate 是可观测的非关键路径：

- 默认 `ICON_GAP_CANDIDATE_ENABLED=true`，但不改变 Figma 可见输出。
- icon gap candidate failed/skipped 写入 `icon_gap_candidate_results` 和 `error_logs`。
- icon gap candidate validation failed 时 `/dsl` 回退 M21 输出，只是不追加 M22 meta。
- M22 只修改 DSL 顶层 `meta`；不能修改任何已有 element，也不能修改 DSL `assets` 数组。
- 生成的 gap icon PNG 和 overlay PNG 只作为候选/调试资产存在于 storage 和 `/icon-gap-candidates` 报告里。
- 单个 gap icon crop 失败不能让 upload 失败。
- overlay 生成或写入失败只记录 warning，不能让 upload 失败。
- PNG pixel decode unsupported 只记录 warning，不让上传失败。
- M22 不做全局 icon detection、不做 Codia 式全量可拖动图层、不把 gap icon 放进画布、不删除 fallback、不做 SVG/icon 语义识别、不做图标库匹配、不按中文文案特化、不做 AI inpainting、不引入 Pillow/OpenCV。

M23 icon placement plan 是可观测的非关键路径：

- 默认 `ICON_PLACEMENT_PLAN_ENABLED=true`，但不改变 Figma 可见输出。
- icon placement plan failed/skipped 写入 `icon_placement_plan_results` 和 `error_logs`。
- icon placement plan validation failed 时 `/dsl` 回退 M22 输出，只是不追加 M23 meta。
- M23 只修改 DSL 顶层 `meta`；不能修改任何已有 element，也不能修改 DSL `assets` 数组。
- 生成的 placement plan 和 overlay PNG 只作为计划/调试资产存在于 storage 和 `/icon-placement-plan` 报告里。
- overlay 生成或写入失败只记录 warning，不能让 upload 失败。
- PNG pixel decode unsupported 只记录 warning，不让上传失败。
- M23 不裁新 icon、不把 icon 放进画布、不删除 fallback、不做全局 icon detection、不做 Codia 式全量可拖动图层、不做 SVG/icon 语义识别、不做图标库匹配、不做 AI inpainting、不引入 Pillow/OpenCV。

M24 visible icon fallback replay 是默认关闭的实验路径：

- 默认 `ICON_VISIBLE_FALLBACK_ENABLED=false`，不生成 result，不修改 DSL。
- 显式开启后，visible fallback failed/skipped 写入 `icon_visible_fallback_results` 和 `error_logs`。
- visible fallback validation failed 时 `/dsl` 回退 M23 输出，不追加 M24 节点、asset 或 meta。
- M24 只能 append 新 asset、`icon_fallback_cover` shape 和 `visible_icon_fallback` image node，不能修改任何已有 element 或已有 asset。
- 单个 placement 不安全时进入 `blockedPlacements`，不影响其他 placement，也不让 upload 失败。
- overlay 生成或写入失败只记录 warning，不能让 upload 失败。
- PNG pixel decode unsupported 时保存 skipped document，DSL 保持 M23 输出。
- M24 不处理没拆出来的 icon，不补 M21 missed hints，不处理 M22 blocked hints，不裁新 icon、不做全局 icon detection、不做 Codia 式全量可拖动图层、不做透明 PNG/SVG/icon 语义识别、不做图标库匹配、不做 AI inpainting、不引入 Pillow/OpenCV。

整页失败只发生在：

- PNG 无法读取。
- 后端任务不可恢复。
- DSL 无法生成或校验失败。
- Renderer 无法创建 root Frame。

## Timeout Strategy

建议目标：

- 简单页面：15 到 30 秒。
- 中等页面：30 到 60 秒。
- 复杂页面：60 到 90 秒。
- 超过 120 秒返回超时或失败提示。

## Retry Strategy

v0.1 不做复杂自动重试。

允许：

- JSON repair 最多 1 次。
- 用户手动重新上传。
- 后续可选 retry endpoint。

不允许：

- 多轮低分自动修复。
- 无限等待。
- 后台静默重跑但不更新任务状态。

## Degradation

- 图片加载失败：记录 warning，跳过或占位。
- 字体加载失败：降级默认字体。
- 图标识别不确定：fallback 图片或普通 shape。
- 复杂区域：fallback 图片。
