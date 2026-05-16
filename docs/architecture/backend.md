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

M19 当前管线：

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
  assets/{taskId}/slices/
  logs/
```

后端服务启动或测试运行时会创建这些目录。`backend/storage/` 不进入 git。

## Task State

M19 当前只实际写入：

- `completed`
- `failed`

M19 仍同步完成任务。后续接真实处理管线再补 `pending`、`uploaded`、`processing`。

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

## Backend Non-Goals

M19 不做：

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
- AI inpainting。
- 引入 Pillow/OpenCV。
- 图标、圆形、三角形、五角星或复杂图形重建。
