# 后端架构

后端负责接收 PNG、创建任务、生成 DSL、保存资产并提供 API。

## Responsibilities

后端必须支持：

- 健康检查。
- PNG 上传。
- 任务创建。
- 任务状态查询。
- DSL 查询。
- 资产访问。
- 本地存储。
- 错误记录。

## Processing Pipeline

M30.1 plugin preview upload pipeline:

```text
receive multipart PNG at /api/upload-m30-preview
-> validate MIME, PNG signature, and IHDR metadata
-> save uploads/{taskId}/original.png
-> create task status=processing stage=m30_queued
-> run background OCR + M29 + M30 pipeline
-> OCR
-> M29 visual primitive graph
-> M29.1 symbol fragment grouping
-> M29.0.2 text-masked media audit
-> M29.0.3 visual evidence normalization with M29.1 lineage
-> M29.0.7 text/visual ownership gate
-> M29.0.4 visual object candidate audit with ownership routing
-> M29.0.5 text-aware visual object refinement
-> M30 evidence-grounded DSL materialization
-> copy local M30 DSL assets to assets/{taskId}/m30 and rewrite URLs
-> save dsl_results path to m30/m30_materialized_dsl.json
-> mark task completed
```

This pipeline is the plugin preview main path. It does not run M29.1.3, M29.0.3.2, M29.0.6, M19-M25, M24 visible fallback, M26-M28, Auto Layout, Figma Component/Instance, SVG/vectorization, text cover, or any 图标恢复 path.

M28 当前上传管线：

```text
receive multipart PNG
-> validate MIME and PNG signature
-> read PNG IHDR metadata
-> save original image
-> create compatibility full-image asset
-> plan deterministic regions
-> crop header/content/bottom region assets when supported
-> build deterministic region DSL
-> extract visual primitive candidates
-> extract OCR candidates
-> build hidden candidate DSL patch
-> evaluate text replacement candidates
-> run UI-aware text replacement sampling for safe rescue cases
-> score replacement quality and block risky replacements
-> optionally merge non-high-risk visible text replacements when TEXT_REPLACEMENT_MODE=apply
-> bind OCR/replacement text to visual primitives or inferred UI containers
-> aggregate bindings into component candidates and layout groups
-> annotate existing DSL elements with component/group metadata and layer names
-> build component-aware layer separation candidates
-> build local asset slice candidates
-> build icon candidate crops
-> build icon coverage audit
-> build region-guided icon gap candidates
-> build icon placement plan
-> optionally replay visible icon fallback
-> build region-guided business icon candidates
-> optionally run visual perception provider benchmark
-> optionally run SAM2 visual candidate filtering
-> save DSL JSON
-> save primitive JSON
-> save OCR JSON
-> save patch JSON
-> save text replacement JSON
-> save text binding JSON
-> save component structure JSON
-> save component annotation JSON
-> save layer separation candidate JSON
-> save asset slice candidate JSON
-> save icon candidate JSON
-> save icon coverage audit JSON
-> save icon gap candidate JSON
-> save icon placement plan JSON
-> save icon visible fallback JSON when enabled
-> save icon business candidate JSON
-> save perception benchmark JSON when enabled
-> save SAM visual candidate JSON when enabled
-> mark task completed
```

后续真实 v0.1 管线：

```text
load original image
-> validate PNG
-> preprocess image
-> run OCR
-> run AI / CV analysis
-> crop assets
-> build DSL
-> normalize DSL
-> validate DSL
-> repair DSL when safe
-> save result
```

## Storage

开发阶段使用本地文件存储：

```text
backend/storage/
  uploads/
  assets/
  m30_1_uploads/
  dsl/
  primitives/
  ocr/
  patches/
  text_replacements/
  text_bindings/
  component_structures/
  component_annotations/
  layer_separation_candidates/
  asset_slice_candidates/
  icon_candidates/
  icon_coverage_audits/
  icon_gap_candidates/
  icon_placement_plans/
  icon_visible_fallbacks/
  icon_business_candidates/
  perception_benchmarks/
  sam_visual_candidates/
  assets/{taskId}/slices/
  assets/{taskId}/icons/
  assets/{taskId}/icons_gap/
  assets/{taskId}/icons_business/
  assets/{taskId}/debug/
  assets/{taskId}/m30/
  logs/
```

后端服务启动或测试运行时会创建这些目录。`backend/storage/` 不进入 git。

## Task State

M30.1 preview tasks can be asynchronous. The task table can write:

- `processing`
- `completed`
- `failed`

Legacy `/api/upload` still completes synchronously.各阶段旁路结果表可以写入 `completed`、`failed` 或 `skipped`，例如 M25 在 PNG pixel decode unsupported 时保存 skipped document。

后续完整任务状态：

- `pending`
- `uploaded`
- `processing`
- `completed`
- `failed`

## Deterministic DSL Builder

M7 不接 OCR/AI。上传成功后，后端根据真实 PNG 尺寸生成 deterministic region fallback DSL：

- root frame 尺寸等于 PNG 宽高。
- 隐藏 `original_reference` 图层覆盖整图。
- 对 portrait/mobile-like PNG，生成可见 `fallback_region_header`、`fallback_region_content`、`fallback_region_bottom`。
- 每个 region 生成独立 PNG crop asset。
- `meta.notes` 写为 `deterministic_region_dsl`。
- 如果 PNG 可读尺寸但 cropper 不支持该 PNG 格式，退回整图 `fallback_full_image`，并写入 `meta.qualityFlags: ["region_crop_unsupported"]`。

这不是最终识别能力，只是把 M6 的整图 fallback 基线推进到可单独替换的区域层。

region 规则：

```text
header = min(max(round(height * 0.14), 120), 260)
bottom = min(max(round(height * 0.12), 100), 220)
content = height - header - bottom
```

图片过矮、非 portrait/mobile-like 或切分不安全时，使用整图 fallback。

当前标准库 PNG cropper 只支持：

- bit depth `8`
- color type `2` RGB 或 `6` RGBA
- non-interlaced PNG
- filter type `0..4`

任务阶段：

- `upload`
- `task_lookup`
- `dsl_lookup`
- `asset_lookup`
- `preprocess`
- `ocr`
- `ai_analyze`
- `asset_crop`
- `dsl_build`
- `dsl_validate`
- `completed`
- `failed`

## Visual Primitive Contract Harness

M8 引入 visual primitives，但不让 AI 直接生成 DSL。后端会保存一份 candidate primitive JSON：

- 默认 provider 是 `fake`，不需要 `OPENAI_API_KEY`。
- `fake` provider 根据 M7 region 生成 `vp_region_header`、`vp_region_content`、`vp_region_bottom`。
- 可选 `openai` provider 使用视觉模型提取非文字 UI candidate primitives。
- primitive bbox 使用整图像素坐标 `[x, y, width, height]`。
- primitives 不进入 DSL，不改变 Figma 插件输出。
- extraction 失败只影响 primitives 查询结果，不影响 M7 deterministic DSL。

OpenAI provider 规则：

- 只有 `VISUAL_PRIMITIVE_PROVIDER=openai` 时启用。
- 输入为 region PNG，不直接分析整张长图。
- 模型输出 normalized region-local box 后，由后端换算成整图像素 bbox。
- 模型输出必须经过 validator，非法 bbox、重复 id、无效 relation 不进入结果。

## AI Strategy

M18 之后的普通页面目标管线：

```text
OCR boxes
-> visual primitives
-> primitive merger
-> DSL patch builder
-> DSL validator
```

异常 JSON：

```text
最多 1 次 JSON repair
```

不做多轮复杂分析、多模型对比、评分后自动修复。

## OCR And DSL Patch Harness

M9 引入 OCR 合同和 DSL patch；M10 新增可选百度 PP-OCRv5 异步 OCR provider，但仍不做完整识别还原：

- 默认 `OCR_PROVIDER=fake`。
- 可选 `OCR_PROVIDER=baidu_ppocrv5`，使用百度 AI Studio `PP-OCRv5` 异步 OCR API。
- OCR bbox 使用整图像素坐标 `[x, y, width, height]`。
- 百度返回的 `rec_boxes` 从 `[x1, y1, x2, y2]` 转为 `[x, y, width, height]`。
- 百度 OCR 失败、超时、429 或 JSONL 异常只会让 OCR result failed，不能拖垮上传和 fallback DSL。
- OCR 结果写入 `backend/storage/ocr/{taskId}.json`。
- DSL patch 写入 `backend/storage/patches/{taskId}.json`。
- 默认 `DSL_PATCH_MODE=debug`。
- patch 只添加 hidden `candidate_text`。
- candidate text `style.visible` 固定为 `false`，避免双层文字。
- patch validation 失败时 `/dsl` 回退 deterministic base DSL。

M12 扩展文字替换覆盖率：默认 `TEXT_REPLACEMENT_MODE=debug` 只记录 accepted/rejected 决策；`apply` 给低复杂度背景上的高置信 OCR block 添加 cover shape 和 visible text。M12 支持浅底深字、部分彩色/深色底浅字、保守 OCR block 合并和更稳的字号/行高。fallback region、original reference 和 hidden candidate text 都保留。

M13 增加 text replacement quality gate：每个 decision 会记录 `quality` 和 `application`，说明基础 replacement 是否 accepted、风险等级、粗略 region、阻断原因和 apply 状态。`TEXT_REPLACEMENT_MODE=apply` 阻断 high-risk accepted replacement；medium-risk replacement 记录 caution 但仍可应用。

M14 增加 UI-aware text replacement sampling：标准 perimeter sampling 仍先运行；只有标准策略因 `complex_background`、前景不确定或对比不足等可救原因失败时，才尝试 badge、legend、outline button、card/tip 和 bottom nav 的局部采样策略。每个 decision 可记录 `strategy.attempts` 和 `meta.strategySummary`，用于解释 OCR 已识别文本为何被 accepted、rejected 或 rescue。M14 不新增 OCR provider，不重建图标/组件，不删除 fallback region，也不全局调大背景容差。

M15 增加 text-primitive binding harness：后端把 M14 可用 text candidate 绑定到现有 visual primitives 或 M15 推断出的 UI containers，写入 `backend/storage/text_bindings/{taskId}.json` 并通过 `/api/tasks/{taskId}/text-bindings` 暴露。默认 fake visual primitive provider 只有 fallback regions，因此 M15 会生成 `inferred_from_text_cluster` 容器，例如 page header、hero profile、badge、status badge、activity card、summary stat card、primary button、outline button、shortcut card、preview card、legend group、tip card 和 bottom nav item。推断容器只存在于 binding report，不回写 visual primitives，也不改变 Figma 可见输出。`primary_button` 需要明确 action 背景证据，不能只靠居中和字号吞掉 summary/stat 文本；`card_title`、`card_subtitle` 和 `card_body` 按同容器内 y 顺序与相对字号判断。

M16 增加 component structure harness：后端把 M15 containers/bindings 聚合为 component candidates 和 layout groups，写入 `backend/storage/component_structures/{taskId}.json` 并通过 `/api/tasks/{taskId}/component-structures` 暴露。第一版 component role 覆盖 page header、hero profile、badge/status badge、activity card、summary stat card、primary/outline button、shortcut card、preview card、legend group、tip card、bottom nav 和 bottom nav item；group role 覆盖 summary stat group、shortcut grid、preview section、bottom nav group 和 page structure。M16 不按中文文案或单张图绝对坐标推断，只消费 M15 的 role、relationship、bbox、confidence 和 source。M16 只追加 DSL meta，不新增可见节点，不创建 Figma Component/Instance，不删除 fallback region。

M17 增加 component annotation harness：后端把 M16 component/group 结构通过确定性 ID 链路挂回已有 DSL element，写入 `backend/storage/component_annotations/{taskId}.json` 并通过 `/api/tasks/{taskId}/component-annotations` 暴露。M17 join 链路固定为 `component.bindingIds -> binding.id -> binding.ocrBlockId -> visible_text_{ocrBlockId} / cover_{ocrBlockId} / text_{safe_id(ocrBlockId)}`。M17 只允许修改已有 DSL element 的 `name` 和 `meta`，用于 Figma layer naming 和后续结构索引；不重新识图、不按中文文案特化、不切图、不删除 fallback region、不创建真实 Figma group、Component/Instance 或 Auto Layout。fallback region 只标记为 `fallback_context`，不绑定业务 component。

M18 增加 layer separation candidate harness：后端基于 M14 replacement evidence、M15 bindings、M16 components/groups 和 M17 annotations 判断每个 component 后续适合的分层策略，写入 `backend/storage/layer_separation_candidates/{taskId}.json` 并通过 `/api/tasks/{taskId}/layer-separation-candidates` 暴露。M18 可以为纯色/低复杂背景文字生成 `solid_color_fill` simple fill candidate，用于回答后续切图前是否能把原文字与背景分离。M18 只追加 DSL 顶层 meta，不修改任何已有 DSL element；不切图、不生成填充 PNG、不删除 fallback、不做 AI inpainting、不引入 Pillow/OpenCV、不重建图标或复杂形状。

M19 增加 local asset slice candidate harness：后端基于 M18 的低风险 `image_slice_with_simple_fill_candidate` 生成本地 original slice PNG 和可选 filled slice PNG，写入 `backend/storage/assets/{taskId}/slices/` 与 `backend/storage/asset_slice_candidates/{taskId}.json`，并通过 `/api/tasks/{taskId}/asset-slice-candidates` 暴露。M19 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组；生成的 PNG 只是实验资产，不进入 Renderer 可见路径。

M20 增加 icon candidate extraction/crop harness：后端基于 M15-M17 的结构索引，在 bottom nav label 上方、shortcut card 文本左侧、tip title 左侧和字段 label 左侧等 component-local search window 中寻找小型前景块，使用 `decode_png_pixels()` 和简单 connected component 找 bbox，再用 `crop_png()` 生成 icon PNG，写入 `backend/storage/assets/{taskId}/icons/` 与 `backend/storage/icon_candidates/{taskId}.json`，并通过 `/api/tasks/{taskId}/icon-candidates` 暴露。M20 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组；生成的 PNG 只是候选资产，不进入 Renderer 可见路径。M20 不做 SVG/icon 语义识别，不做图标库匹配，不按中文文案特化，不引入 Pillow/OpenCV。

M21 增加 icon coverage audit/placement readiness harness：后端基于 M20 icon candidates、M19 slice candidates、当前 DSL 和原始 PNG 像素，生成 placement readiness、missedIconHints 和 debug overlay，写入 `backend/storage/icon_coverage_audits/{taskId}.json` 与 `backend/storage/assets/{taskId}/debug/icon_coverage_overlay.png`，并通过 `/api/tasks/{taskId}/icon-coverage-audit` 暴露。M21 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组；overlay 只是调试资产，不进入 Renderer 可见路径。M21 不把 M20 icon 放进画布，不删除 fallback，不做 SVG/icon 语义识别，不做图标库匹配，不按中文文案特化，不引入 Pillow/OpenCV。overlay 只画彩色 bbox，不画文字标签。

M22 增加 region-guided icon gap candidate harness：后端基于 M21 missedIconHints、M20 icon candidates、M15-M17 结构索引、当前 DSL 和原始 PNG 像素，把可靠的 header、bottom nav、shortcut、card/row/button trailing 等漏裁区域补裁成本地 gap icon PNG，写入 `backend/storage/icon_gap_candidates/{taskId}.json`、`backend/storage/assets/{taskId}/icons_gap/*.png` 与 `backend/storage/assets/{taskId}/debug/icon_gap_overlay.png`，并通过 `/api/tasks/{taskId}/icon-gap-candidates` 暴露。M22 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组；gap icon 和 overlay 都只是候选/调试资产，不进入 Renderer 可见路径。M22 不做全局 icon detection，不做 Codia 式全量可拖动图层，不把 icon 放进画布，不删除 fallback，不做 SVG/icon 语义识别，不做图标库匹配，不按中文文案特化，不引入 Pillow/OpenCV。顶部右侧小程序胶囊只裁内部小 blob，不裁整块胶囊。

M23 增加 icon placement plan/layering readiness harness：后端基于 M20 icon candidates、M22 gap icon candidates、M19 slice candidates、M15/M16 引用和当前 DSL collision facts，统一规划 dedupe、blocked、needs_fallback_mask、needs_slice_coordination、needs_fallback_coordination、review_required 和 ready_for_visible_icon，写入 `backend/storage/icon_placement_plans/{taskId}.json` 与 `backend/storage/assets/{taskId}/debug/icon_placement_overlay.png`，并通过 `/api/tasks/{taskId}/icon-placement-plan` 暴露。M23 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组；futureDslNodeHint 和 overlay 都只是计划/调试信息，不进入 Renderer 可见路径。M23 不裁新 icon，不把 icon 放进画布，不删除 fallback，不做全局 icon detection，不做 Codia 式全量可拖动图层，不做 SVG/icon 语义识别，不做图标库匹配，不引入 Pillow/OpenCV。

M24 增加 visible icon fallback replay experiment harness：后端默认不启用 `ICON_VISIBLE_FALLBACK_ENABLED=false`，因为它会改变可见 DSL/Figma 输出。显式开启后，M24 只消费 M23 `needs_fallback_mask` 且低风险的 M20/M22 icon placement，使用 solid background sampling 生成 `icon_fallback_cover` shape，再追加 `visible_icon_fallback` image node，并只把实际使用的 icon asset 追加进 DSL `assets`。M24 写入 `backend/storage/icon_visible_fallbacks/{taskId}.json` 与 `backend/storage/assets/{taskId}/debug/icon_visible_fallback_overlay.png`，并通过 `/api/tasks/{taskId}/icon-visible-fallback` 暴露。M24 不处理没拆出来的 icon，不补 M21 missed hints，不处理 M22 blocked hints，不裁新 icon，不做全局 icon detection，不做 Codia 式全量可拖动图层，不做透明 PNG/SVG/icon 语义识别，不做图标库匹配，不引入 Pillow/OpenCV。

M25 增加 region-guided business icon candidate harness：后端基于当前 DSL、原始 PNG 像素、M20/M22/M23 已有 icon bbox 和 M24 visible icon bbox，在稳定业务区域直接 probe，裁出 bottom nav、primary button trailing arrow、shortcut tile、metric card、room card、row/card trailing 和 tip/info 等高价值业务 icon 候选 PNG。M25 写入 `backend/storage/icon_business_candidates/{taskId}.json`、`backend/storage/assets/{taskId}/icons_business/*.png` 与 `backend/storage/assets/{taskId}/debug/icon_business_overlay.png`，并通过 `/api/tasks/{taskId}/icon-business-candidates` 暴露。M25 只追加 DSL 顶层 meta，不修改已有 DSL element，不修改 DSL `assets` 数组；business icon 和 overlay 都只是候选/调试资产，不进入 Renderer 可见路径。M25 不依赖完整 M16 业务组件识别，不重新 OCR，不按中文文案特化，不处理插画、头像、建筑或床位平面图复杂资产，不做全图无边界 detection，不做 Codia 式全量拆层，不把 icon 放进画布，不做 SVG/icon 语义识别，不做图标库匹配，不引入 Pillow/OpenCV。

M26 增加 visual perception provider benchmark harness：后端默认不启用 `PERCEPTION_BENCHMARK_ENABLED=false`。显式开启后，M26 基于当前任务已有 M20/M22/M25 候选、当前 DSL collision facts 和原始 PNG 像素，生成统一 provider benchmark document。`current_rules` provider 只读取已有候选作为 baseline；`opencv` provider 只有安装并启用 OpenCV 时才运行轻量 connected-component bbox proposal；`sam2` provider 只有启用、checkpoint 存在且 `torch`/`sam2` 可 import 时才运行 automatic mask generation；`uied` provider 只作为外部命令 adapter。M26 写入 `backend/storage/perception_benchmarks/{taskId}.json` 与 `backend/storage/assets/{taskId}/debug/perception_overlay_*.png`，并通过 `/api/tasks/{taskId}/perception-benchmark` 暴露。M26 不修改 DSL、不追加 DSL meta、不裁新 icon asset、不改变 Figma 可见输出、不把 provider 输出当 Renderer 输入；OpenCV/SAM2/UIED 都不是默认生产依赖。

M27 增加 SAM2-guided visual candidate filtering harness：后端默认不启用 `SAM_VISUAL_CANDIDATE_ENABLED=false`。显式开启且本地 checkpoint、torch、numpy 和 sam2 可用时，M27 运行 SAM2 automatic mask generation，把 mask bbox 映射回原图，再基于当前 DSL text/cover/candidate_text、M20/M22/M23/M24/M25 existing icon bbox、状态栏/header/插画/床位图排除区和 line/border/background-like 规则过滤成 accepted candidates 与 blocked candidates。M27 写入 `backend/storage/sam_visual_candidates/{taskId}.json` 与 `backend/storage/assets/{taskId}/debug/sam_visual_candidate_overlay.png`，并通过 `/api/tasks/{taskId}/sam-visual-candidates` 暴露。M27 不修改 DSL、不追加 DSL meta、不裁新 icon asset、不生成透明 PNG、不改变 Figma 可见输出、不把 SAM2 输出当 Renderer 输入。

M28 增加 single-image SAM2 UI visual extraction harness：它是 `backend/scripts/run_m28_single_visual_extraction.py` 脚本能力，不进入上传主链路。M28 针对固定复杂样例图运行 SAM2 proposal，再按对象级边界输出 `icons/*.png`、`images/*.png`、`controls/*.png`、`m28_visual_extraction.json`、`m28_visual_extraction_overlay.png` 和 `m28_visual_extraction_preview_sheet.png`。M28 先把 hero/product/supplier 等图片槽作为整块 image asset 保护，再从非图片区域提取 UI icon/control，阻断文字、数字、状态栏、图片内部碎片、线条、背景和容器片段。M28 不修改 DSL、不写数据库、不暴露 API、不调用 Renderer、不做 Figma visible replay。

M29 增加 visual primitive graph harness：它是 `backend/scripts/run_m29_visual_primitive_graph.py` 脚本能力，不进入上传主链路，也不替换 M8 `backend/app/visual_primitives.py` 与 `/api/tasks/{taskId}/primitives` 合同。M29 直接从 PNG pixels 构建 `text`、`shape`、`image`、`symbol`、`unknown` primitive graph，输出 `nodes.json`、`assets/images/*.png`、`assets/symbols/*.png`、`overlays/*.png` 和 `preview_sheet.png`。M29 固定 bbox 为 `[x, y, width, height]` 原图像素坐标，mask 为 row-major 1 byte per pixel。M29 先做 text exclusion、obvious shape detection 和 conservative image protection，再从剩余 foreground 中找 symbol candidate。M29 不修改 DSL、不写数据库、不暴露 API、不调用 Renderer、不接 SAM2/OpenCV/OCR provider，不做 SVG/vectorization。

M29.0.1 增强 M29 blocked evidence，不改变 accepted nodes 或检测接受逻辑。M29 document 仍为 `version=0.1`，但 `meta.blockedEvidenceVersion=0.2`；每个 blocked item 必须保留 bbox、metrics、细粒度 reasons 和最小 context。`symbol_metrics_rejected` 被拆成 color/texture/edge/area/line/text/image/protective 等可消费 reason，供后续 M29.1 判断 eligible blocked fragments。M29.0.1 不新增 detector，不接 OCR/SAM2/SVG/Figma/DSL，不进入上传主链路。

M29.1 增加 symbol fragment grouping harness：它是 `backend/scripts/run_m29_1_symbol_grouping.py` 脚本能力，要求读取 M29.0.1 的 `meta.blockedEvidenceVersion=0.2` 输出。M29.1 的候选全集固定为 accepted symbol nodes 与 eligible blocked primitives；它建立 fragment edge audit，保守生成 grouped symbol candidates 和 icon button group relation，输出 `m29_1/group_nodes.json`、`symbol_asset_audit.json`、`edge_audit.json`、`assets/symbol_groups/*.png`、group overlays 和 preview sheet。M29.1 不重新扫描整图、不重新跑 connected components、不重新做 detector、不回写 M29 `nodes.json`、不覆盖原始 symbol assets、不接 OCR/SAM2/SVG/Figma/DSL、不进入上传主链路。

M29.0.2 之后的 M29+ 证据链是当前重建分析主线。M20-M28 保留为 legacy experiments / diagnostic references，不再作为后续对象归因、文字归属或 visual asset 判断的主链路事实来源。OCR 仍然保留，因为 text ownership 需要独立文字证据；当前判断默认从 OCR/textBoxes + M29/M29.1/M29.0.x 输出开始。

M29.0.3.1 在 M29.0.3 的 lineage-aware path 前移 `text_owned_rejected_lineage` gate。未传 M29.1 lineage JSON 时 M29.0.3 baseline 不变；传入 lineage 时，high OCR overlap + surviving lineage 会先检查 full OCR coverage、single text-like token、text-like aspect、M29.1 candidate baseline glyph risk、weak eligible-blocked high overlap 等文字反证。强文字反证成立时仍输出 `text_noise`，但保留 `sourceLineage` 并标记 `conflictClass=text_owned_rejected_lineage`、`survivingPreOcrSymbolCandidate=false`。M29.0.7 只透传该审计信息，不为它打开 visual side。

M29.0.3.2 增加 residual mixed boundary review。它只读取 M29.0.3.1 收紧后仍残留的 `mixed_symbol_text_candidate`，结合 M29.1.3、M29.0.7、M29.0.2、M29.1、M29.1.1 和 source PNG existing bbox crop 信息，输出 `m2903_tightening_candidate`、`m2913_classification_adjustment_candidate`、`keep_residual_mixed_conflict`、`candidate_for_future_uncertain_review`、`insufficient_evidence` 五类 review conclusion。M29.0.3.2 是 actionable audit，不是 routing contract；M29.0.4/M29.0.5/M29.0.7 不消费它，所有 promotion/visual-side/formal-asset permission flags 恒为 false。

## Backend Non-Goals

M29 不做：

- 用户系统。
- 支付和额度。
- 批量任务。
- 完整历史记录。
- 复杂队列。
- Redis 缓存。
- 微服务拆分。
- 正式对象存储策略。
- 同步 OCR API。
- PaddleOCR/RapidOCR 本地 provider。
- AI 直接生成 DSL。
- AI 直接生成 patch。
- OCR/AI 语义裁切。
- 全量可编辑文字生成。
- 完整可编辑还原。
- 删除 fallback region。
- 复杂纹理背景强行文字替换。
- 图标、头像、圆形组件、卡片组件重建。
- fallback 删除和正式组件化重建。
- 把 inferred containers 写回 visual primitives。
- 通过 binding 结果重组 Figma 图层。
- 通过 component structure 结果创建 Figma group、component 或 Auto Layout。
- 正式局部 asset replacement 或 partial fallback replacement。
- 图标、头像、圆形、三角形、五角星、复杂图形或组件视觉重建。
- 通过 component annotation 结果创建真实 Figma group、component 或 Auto Layout。
- 把 M19 实验 asset slice 写入 DSL `assets`。
- 把 M20 icon candidate 写入 DSL `assets`。
- 把 M21 overlay 写入 DSL `assets`。
- 把 M22 gap icon 或 overlay 写入 DSL `assets`。
- 把 M23 placement plan 或 overlay 写入 DSL `assets`。
- 默认或未经 M24 allowlist/mask 门禁把 M20 icon 放进 Figma 可见画布。
- 默认或未经 M24 allowlist/mask 门禁把 M22 gap icon 放进 Figma 可见画布。
- 把 M23 futureDslNodeHint 放进 Figma 可见画布。
- 默认把 M24 visible icon fallback 打开。
- 在 M24 处理没拆出来的 icon、M21 missed hints 或 M22 blocked hints。
- 在 M24 做新的 icon crop。
- 把 M25 business icon candidate 写入 DSL `assets`。
- 把 M25 business icon 放进 Figma 可见画布。
- 在 M25 做可见 replay。
- 在 M25 处理插画、头像、建筑或床位平面图复杂资产。
- 默认运行 M26 benchmark。
- 把 M26 provider 输出写进 DSL、Renderer 或 Figma 可见画布。
- 默认运行 M27 SAM visual filtering。
- 把 M27 SAM candidates 写进 DSL、Renderer 或 Figma 可见画布。
- 默认运行 M28 visual extraction。
- 把 M28 `icons/`、`images/`、`controls/` 写进 DSL、Renderer 或 Figma 可见画布。
- 默认运行 M29 visual primitive graph。
- 把 M29 `nodes.json` 或 assets 写进 M8 `/primitives`、DSL、Renderer 或 Figma 可见画布。
- 把 OpenCV/UIED 作为默认生产依赖。
- 默认下载 SAM2 checkpoint 或 vendoring UIED 源码。
- 全局 icon detection。
- Codia 式全量可拖动图层。
- SVG/icon semantic recognition 或图标库匹配。
- 按中文文案特化 missed icon hints。
- AI inpainting。
- 引入 Pillow 或把 OpenCV/SAM2/UIED 放进默认生产链路。
- SVG/icon 语义识别或图标库匹配。
- 全量或默认开启的可见 icon replacement。
- 圆形、三角形、五角星或复杂图形重建。
