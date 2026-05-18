# 测试策略

当前仓库已有最小 `@image-figma/dsl-schema` 包。本文件定义当前验证层和后续必须补的验证层。

## Validation Focus

v0.1 重点验证：

- DSL 合同稳定。
- Renderer 能用假 DSL 渲染。
- 后端 API 能返回可用任务和 DSL。
- 插件能完成主流程。
- 真实 PNG 样例能完成端到端链路。

## Test Layers

DSL Schema：

- 合法 DSL 通过。
- 缺必填字段失败。
- 非法 element type 失败。
- image assetId 不存在失败。
- normalize 能补默认值。
- repair 只做安全修复。

当前命令：

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
```

Renderer：

- 假 DSL 生成 root Frame。
- Text、Shape、Image 可渲染。
- Line 可渲染。
- 单元素失败不会中断整页。
- 图片加载失败产生 warning。
- 原图参考层默认隐藏。
- fallback 图片能显示。
- icon 在 M2 返回 unsupported warning。

当前命令：

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

Figma Plugin：

- 构建命令：`pnpm --filter @image-figma/figma-plugin run build`
- 类型检查：`pnpm --filter @image-figma/figma-plugin run typecheck`
- 构建 target 使用 `es2017`。
- 构建时扫描 `dist/main.global.js`，避免残留 `??`、`?.`、ESM 和其他 Figma sandbox 风险语法。
- 在 Figma 开发模式加载 `figma-plugin/manifest.json`
- manifest 中 `localhost` 只能出现在 `networkAccess.devAllowedDomains`
- manifest 中阻断正式网络访问时使用 `networkAccess.allowedDomains: ["none"]`
- 运行后选择 PNG 并点击 `Generate from PNG`
- 当前页面应生成示例 root Frame
- UI 应显示成功、失败或 warning 列表
- 后端运行时，banner image 不应出现 `IMAGE_LOAD_FAILED`
- 停掉后端后，UI 应显示后端请求失败

Backend API：

- `GET /api/health` 成功。
- `POST /api/upload` 接受 PNG。
- 非 PNG 拒绝。
- PNG 尺寸不可读时拒绝。
- 过大图片拒绝。
- task 状态可查询。
- completed 后 DSL 可获取。
- M7 deterministic DSL 尺寸必须等于真实 PNG 尺寸。
- M7 upload DSL 不应包含 sample-only 元素如 `search_icon`。
- portrait/mobile-like PNG 应生成 `fallback_region_header`、`fallback_region_content`、`fallback_region_bottom`。
- region layout 必须连续覆盖整图，不能有空洞或重叠。
- region asset 文件必须存在，且宽高等于对应 layout。
- cropper 不支持的 PNG 格式必须退回整图 fallback，并写入 `qualityFlags`。
- 未完成任务获取 DSL 返回明确错误。
- asset 元信息可查询。
- `/files/uploads/...` 和 `/files/assets/...` 可返回 PNG。
- M8 上传后生成 primitive JSON 文件。
- `GET /api/tasks/{taskId}/primitives` 可返回 fake primitives。
- primitive extraction 失败不影响 DSL 查询。
- M9 上传后生成 OCR JSON 和 DSL patch JSON。
- `GET /api/tasks/{taskId}/ocr` 可返回 fake OCR blocks。
- `GET /api/tasks/{taskId}/dsl-patch` 可返回 patch document。
- `DSL_PATCH_MODE=debug` 时 `/dsl` 返回 hidden text candidates。
- `DSL_PATCH_MODE=off` 时 `/dsl` 返回 M7 base DSL。
- M10 `OCR_PROVIDER=baidu_ppocrv5` 使用 fake HTTP client 测试，不打真实百度网络。
- 百度 PP-OCRv5 `rec_boxes` 必须从 `[x1, y1, x2, y2]` 转成 `[x, y, width, height]`。
- 百度 OCR 失败、超时、缺 token 或 JSONL 异常时，上传仍 completed，DSL 回退 fallback。
- M12 `TEXT_REPLACEMENT_MODE=debug` 生成 replacement document，但不把 visible text 合并进 `/dsl`。
- M12 `TEXT_REPLACEMENT_MODE=apply` 只对 accepted 低复杂度背景文字添加 cover shape 和 visible text。
- M12 apply 必须保留 fallback region、original_ref 和 hidden candidate_text。
- M12 必须覆盖浅底深字、彩色/深色底浅字、低对比拒绝、无稳定前景色拒绝、短中文 bbox 字号约束和保守 OCR block 合并。
- M13 text replacement 必须给每个 decision 输出 quality/application 字段。
- M13 apply 只能阻断 high-risk accepted replacement，medium-risk replacement 应记录 caution 但仍可应用。
- M13 必须覆盖 accepted high-risk 被 quality gate blocked、accepted medium-risk 仍 applied、rejected high risk、region/reason summary，以及首页样例 OCR 已识别但 replacement 拒绝的回归。
- M14 UI-aware sampling 必须覆盖标准采样仍可用、复杂纹理仍拒绝、badge/status badge rescue、legend 三标签一致 rescue、outline button rescue、card/tip rescue、bottom nav label rescue、关闭 `TEXT_REPLACEMENT_UI_AWARE_SAMPLING` 后回退 M13 行为。
- M14 decision 必须输出 `strategy.attempts`，`meta.strategySummary` 和 `rescuedFromComplexBackgroundCount` 必须可用于解释 `complex_background` 误杀是否被恢复。
- M15 text binding 必须覆盖默认生成报告、`TEXT_BINDING_ENABLED=false` 不生成报告、`/text-bindings` API、DSL meta、不新增可见节点，以及 page header、hero profile、badge/status、activity card、summary stat card、primary/outline button、card、legend、tip、bottom nav 绑定规则。
- M15 回归必须保护 primary button 不吞 summary/stat 文本、outline button 优先于 preview card、card title/subtitle/body 按同容器内 row 顺序和相对字号判定。
- M16 component structure 必须覆盖默认生成报告、`COMPONENT_STRUCTURE_ENABLED=false` 不生成报告、`/component-structures` API、DSL meta、不新增可见节点，以及 page header、hero profile、activity card、summary stat group、primary/outline button、shortcut grid、preview section、tip card、bottom nav group、page structure 聚合规则。
- M16 回归必须保护 fallback region 不生成高置信业务 component，低于 `COMPONENT_STRUCTURE_MIN_CONFIDENCE` 的 container 进入 `unstructuredContainerIds`，component/group 引用的 M15 binding/container id 必须可校验。
- M17 component annotation 必须覆盖默认生成报告、`COMPONENT_ANNOTATION_ENABLED=false` 不生成报告、`/component-annotations` API、DSL meta、只改 `name/meta`、不新增可见节点，以及 visible text、cover、hidden candidate text 通过同一 OCR block 绑定到同一 component。
- M17 回归必须保护 fallback region 只标 `fallback_context`、不绑定业务 component；group hints 不创建真实 Figma group；layer naming 只来自 role/relationship/element type 和 text preview，不按中文文案特化。
- Renderer 必须覆盖显式 DSL `element.name` 会成为 Figma node name，M17 不需要改 Renderer 协议。
- M18 layer separation 必须覆盖默认生成报告、`LAYER_SEPARATION_ENABLED=false` 不生成报告、`/layer-separation-candidates` API、DSL meta、只改顶层 meta、不新增可见节点、不改任何已有 element。
- M18 回归必须保护 primary button/badge/status/outline/bottom nav label 的 simple fill candidate、tip/shortcut/preview 的 simple fill 或 repair required、fallback region 只进 fallbackContexts、component bbox 过大或 bottom nav fill target 侵入 icon 区域时 blocked。
- M19 asset slice 必须覆盖默认生成报告、`ASSET_SLICE_ENABLED=false` 不生成报告、`/asset-slice-candidates` API、DSL meta、只改顶层 meta、不新增可见节点、不改任何已有 element、不改 DSL assets。
- M19 回归必须保护 tip/shortcut 等低风险 slice role 能生成 original/filled slice PNG，primary button/badge/status/bottom nav 等 shape/text role 默认跳过，bbox 过大或 fill target 超出 crop 时 blocked 或 original-only，fallback region 不生成业务 slice。
- M20 icon candidate 必须覆盖默认生成报告、`ICON_CANDIDATE_ENABLED=false` 不生成报告、`/icon-candidates` API、DSL meta、只改顶层 meta、不新增可见节点、不改任何已有 element、不改 DSL assets。
- M20 回归必须保护 bottom nav label 上方、shortcut card 左侧、tip title 左侧和 field label 左侧的小图能生成 icon PNG，text/cover bbox 不能被误裁成 icon，candidate limit 和 bbox/置信度门禁能阻断不安全候选。
- M21 icon coverage audit 必须覆盖默认生成报告、`ICON_COVERAGE_AUDIT_ENABLED=false` 不生成报告、`/icon-coverage-audit` API、DSL meta、只改顶层 meta、不新增可见节点、不改任何已有 element、不改 DSL assets。
- M21 回归必须保护 M20 source 到 placementRole 的映射、fallback/slice/text/cover collision readiness、asset missing blocked、missedIconHints 去重和 overlay PNG 可读。
- M22 icon gap candidate 必须覆盖默认生成报告、`ICON_GAP_CANDIDATE_ENABLED=false` 不生成报告、`/icon-gap-candidates` API、DSL meta、只改顶层 meta、不新增可见节点、不改任何已有 element、不改 DSL assets。
- M22 回归必须保护 M21 missed hint 升级为 header/right/trailing/bottom-nav/shortcut gap icon、M20 icon 不重复裁、visible text/cover/hidden candidate_text 不误裁、状态栏不误裁、field text-stroke blocked、edge-clipped retry/blocked 逻辑和 overlay PNG 可读。
- M29.0.2 text-masked media audit 必须覆盖 OCR/text box 到 text mask 的转换、text-suppressed analysis 只作为分析视图、evidence crop 始终从原图裁、mediaEvidence 能区分 M29 image/unknown/symbol/blocked、M29.1 group 和 after-text-mask candidate，overlay/preview PNG 可读。
- M29.0.3 visual evidence normalization 必须覆盖每个 M29.0.2 mediaEvidence item 恰好生成一个 VisualEvidenceItem、所有 item 都从原图裁 asset、accepted image/media candidate/icon candidate/text noise 分桶、text noise 保留但排后、overlay/preview PNG 可读、document validation 拒绝坏 bbox/重复 id/缺失 asset。
- M29.0.4 generic visual object candidate audit 必须覆盖 candidate universe 只来自 M29.0.3 items + M29.0.2 textBoxes、M29/M29.1/M29.0.2 mediaEvidence refs 不直接新增候选、未知 visualKind 不崩溃并记录 warning、icon-like text_noise 只能作为 weak_visual 且带 text_overlap/icon_like_text_noise risk、wide bbox 只能生成 split_candidate 且不导出 child accepted crop、edge audit 覆盖 accepted/weak/rejected edges、sets 默认不引用 rejected objects、overlay 尺寸等于源图且 preview PNG 可读。
- M29.0.5 text-aware visual object refinement 必须覆盖每个 M29.0.4 object 恰好生成一个 RefinedVisualObject、M29.0.3/M29.0.2 lookup 不能直接新增 object、combined crop 只能 audit-only、formal visual_assets 只包含从原始 PNG 裁出的 image/icon 成员、shapeCandidates 不进入 visual_assets、高 text overlap 的 image/icon 成员进入 unresolved、split/wide source 进入 split_needed 且不导出 child asset、textPreview 必填并在 Markdown/overlay 截断、overlay 尺寸等于源图且 preview PNG 可读。
- M23 icon placement plan 必须覆盖默认生成报告、`ICON_PLACEMENT_PLAN_ENABLED=false` 不生成报告、`/icon-placement-plan` API、DSL meta、只改顶层 meta、不新增可见节点、不改任何已有 element、不改 DSL assets。
- M23 回归必须保护 M20/M22 icon 去重、fallback 内 icon 标记 `needs_fallback_mask`、M19 slice 内 icon 标记 `needs_slice_coordination`、text/cover/candidate_text 冲突 blocked、ready icon 的 futureDslNodeHint 只存在于 report，以及 overlay PNG 可读。
- M24 visible icon fallback 必须覆盖 `ICON_VISIBLE_FALLBACK_ENABLED=false` 默认不生成 result 且 DSL 保持 M23 输出、`ICON_VISIBLE_FALLBACK_ENABLED=true` 时生成 `/icon-visible-fallback` 报告并 append DSL nodes/assets、endpoint not found、validation failed 回退 M23 输出。
- M24 回归必须保护只消费 M23 `needs_fallback_mask` placement、role allowlist、置信度门禁、asset/bbox/text/cover/candidate_text/background blocking、cover node 在 icon node 之前、只追加实际使用的 icon asset、不修改已有 DSL element 或已有 asset。
- Renderer 必须覆盖 M24 `icon_fallback_cover` shape 和 `visible_icon_fallback` image node，且 imageFill `fit` 能解析。
- M25 business icon candidate 必须覆盖默认生成报告、`ICON_BUSINESS_CANDIDATE_ENABLED=false` 不生成报告、`/icon-business-candidates` API、DSL meta、只改顶层 meta、不新增可见节点、不改任何已有 element、不改 DSL assets。
- M25 回归必须保护 bottom nav、primary button trailing、shortcut tile、metric/stat、room card、row/card trailing 和 tip/info region probes；text/cover/hidden candidate_text 冲突必须 blocked；M20/M22/M23/M24 existing icon 不重复裁；状态栏、header title、banner/illustration、文字笔画、分割线和卡片边框不误裁。
- M26 perception benchmark 必须覆盖默认 `PERCEPTION_BENCHMARK_ENABLED=false` 不生成 result 且 DSL 不出现 M26 meta、显式开启后生成 `/perception-benchmark` 报告和 provider overlay、task/result/file not found 错误、current_rules provider 转换 M20/M22/M25 candidates、provider dependency missing 时 `unavailable`、单 provider exception 不拖垮 document、SAM2 checkpoint missing `unavailable`、UIED mock command JSON 转成统一 candidates。
- M27 SAM visual candidate filtering 必须覆盖默认 `SAM_VISUAL_CANDIDATE_ENABLED=false` 不生成 result 且 DSL 不出现 M27 meta、checkpoint/dependency missing 时保存 skipped document、`/sam-visual-candidates` API、mock SAM2 masks 转换和过滤、bbox 缩放映射、text/cover/candidate_text/existing-icon/status/header/illustration/bed-map/line/border/background blocking、valid visual candidate accepted、overlay asset 和 DSL 完全不变。
- unsupported PNG sampling 或 replacement validation failed 时上传仍 completed，`/dsl` 回退 M10/M9 输出。

当前命令：

```bash
cd backend
uv run pytest
```

PNG cropper / sampler：

- 标准库读取 PNG metadata，包括 width、height、bit depth、color type、interlace。
- 标准库 cropper 覆盖 bit depth `8`、color type `2`/`6`、non-interlaced PNG。
- scanline filter `0..4` 必须可还原。
- 不支持格式抛出明确异常，由上传链路降级为整图 fallback 或跳过 text replacement。
- RGB/RGBA PNG pixel decode 和背景采样必须覆盖。
- M14 局部 edge/dominant background sampling 必须能跳过图例色块、按钮边框和少量文字前景像素。
- M19 `encode_rgb_png` 和 `crop_and_fill_png` 必须覆盖可读 PNG 输出、solid fill 生效和 fill 越界拒绝。
- M20 `crop_png` 必须覆盖 icon crop 输出，生成资产宽高必须等于 icon bbox，PNG decode unsupported 或 crop out of bounds 不能影响 upload completed。
- M21 overlay PNG 必须覆盖尺寸等于原图、bbox 边缘像素被染色、overlay asset 写入 `assets` 表，PNG decode/overlay 写入失败不能影响 upload completed。
- M22 gap icon crop 必须覆盖 gap icon PNG 输出，生成资产宽高必须等于 bbox；M22 overlay PNG 必须覆盖尺寸等于原图、bbox 边缘像素被染色、overlay asset 写入 `assets` 表，PNG decode/crop/overlay 写入失败不能影响 upload completed。
- M23 overlay PNG 必须覆盖尺寸等于原图、bbox 边缘像素按 decision 染色、overlay asset 写入 `assets` 表，PNG decode/overlay 写入失败不能影响 upload completed。M23 不生成新的 icon PNG。
- M24 overlay PNG 必须覆盖尺寸等于原图、applied cover/icon 和 blocked bbox 被染色、overlay asset 写入 `assets` 表，PNG decode/overlay 写入失败不能影响 upload completed。M24 不生成新的 icon PNG，只复用 M20/M22 asset。
- M25 business icon crop 必须覆盖 business icon PNG 输出，生成资产宽高必须等于 bbox；M25 overlay PNG 必须覆盖尺寸等于原图、candidate/blocked/failed/duplicate bbox 边缘像素被染色、overlay asset 写入 `assets` 表，PNG decode/crop/overlay 写入失败不能影响 upload completed。
- M26 perception overlay PNG 必须覆盖尺寸等于原图、provider candidates 和 blocked bbox 被染色、overlay asset 写入 `assets` 表，PNG decode/overlay 写入失败不能影响 upload completed。M26 不生成新 icon PNG，也不修改 DSL。
- M27 SAM visual overlay PNG 必须覆盖尺寸等于原图、accepted/blocked bbox 被染色、overlay asset 写入 `assets` 表，PNG decode/overlay 写入失败不能影响 upload completed。M27 不生成新 icon PNG，也不修改 DSL。

Visual Primitives：

- 默认 fake provider 不需要 `OPENAI_API_KEY`。
- fake provider 根据 M7 region 输出 `vp_region_header`、`vp_region_content`、`vp_region_bottom`。
- M7 DSL 不应包含 `vp_*` 节点。
- normalized `0..999` bbox 必须转换为整图像素 bbox。
- primitive bbox 轻微越界必须 clamp 并记录 warning。
- 严重非法 bbox 必须丢弃。
- duplicate primitive id 必须丢弃。
- invalid relation 引用必须丢弃。
- OpenAI provider 缺 key、异常、空结果时，上传仍 completed，primitive result 为 `failed` 或 `partial`。
- OpenAI provider 测试使用 monkeypatch fake client，不打真实网络。

OCR And DSL Patch:

- 默认 fake OCR provider 不需要外部依赖。
- 可选百度 PP-OCRv5 provider 不引入本地 PaddleOCR/RapidOCR 依赖。
- OCR bbox 使用整图像素坐标。
- OCR 空文本必须丢弃。
- OCR 置信度低于 `OCR_MIN_CONFIDENCE` 必须丢弃并记录 warning。
- OCR bbox 轻微越界必须 clamp 并记录 warning。
- 严重非法 OCR bbox 必须丢弃。
- duplicate OCR id 必须丢弃。
- DSL patch 只添加 hidden `candidate_text`。
- patch 后 fallback region 和 `original_ref` 不能被删除。
- patch validation 失败必须回退 base DSL。

Plugin UI：

- UI 能发送 `request-plugin-state`。
- UI 能发送 `render-sample`。
- UI 能选择 PNG 并发送 `render-uploaded-png`。
- Main 能返回 `render-started`。
- Main 能返回 `render-succeeded` 或 `render-failed`。
- UI 能展示 rendered element count、warning count 和错误摘要。

后续正式上传流程再验证：

- PreviewView 显示文件信息。
- ProgressView 显示生成中。
- DoneView 显示成功。
- ErrorView 显示失败。
- UI 和 Main 消息流正确。

End-to-End：

- 单张 PNG -> taskId -> DSL -> Renderer -> Figma root Frame。
- M9 当前不要求主要文字可见可编辑。
- 图片资产显示。
- 复杂区域 fallback。

## API Validation

API 变更必须验证：

- 路径。
- 请求格式。
- 响应格式。
- 错误码。
- 任务状态。
- 插件端兼容性。

## Regression Expectation

Bug 修复必须增加回归保护。优先级：

1. 自动化单测或集成测试。
2. e2e 测试。
3. schema/contract 检查。
4. 运行时断言。
5. 手工验证记录。

如果只能手工验证，必须在 bug 记录里写明原因。

## Repository Checks

当前统一检查入口：

```bash
pnpm run check
```

后端当前独立验证入口：

```bash
cd backend
uv run pytest
```

M26 optional smoke：

```bash
cd backend
uv run python scripts/run_m26_perception_smoke.py --providers current_rules
uv run --with opencv-python-headless python scripts/run_m26_perception_smoke.py --providers current_rules,opencv
```

SAM2 smoke 只在本机已安装 `torch`/`sam2` 且配置 `PERCEPTION_SAM2_CHECKPOINT` 后运行。UIED smoke 只在配置 `PERCEPTION_UIED_COMMAND` 后运行。

M27 optional smoke：

```bash
cd backend
uv run python scripts/run_m27_sam_visual_smoke.py \
  --input-dir "/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/" \
  --checkpoint "/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt"
```

M28 single-image extraction smoke：

```bash
cd backend
uv run pytest tests/test_ui_visual_extraction.py -q
uv run python scripts/run_m28_single_visual_extraction.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --checkpoint "/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt" \
  --output-dir "storage/m28_single_visual_extraction"
```

M28 smoke 产物是人工验收证据，不提交 `backend/storage/`。验收重点是 `preview_sheet` 中图片资产保持整块、图片内部碎片被阻断、文字和数字不进入 accepted icon/control。

M29 visual primitive graph smoke：

```bash
cd backend
uv run pytest tests/test_visual_primitive_graph.py -q
uv run python scripts/run_m29_visual_primitive_graph.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --output-dir "storage/m29_visual_primitive_graph"
```

M29 合成测试严格校验 bbox/mask、metrics、components、text exclusion、shape/image/symbol 分类、asset export、overlay 和 document validation。真实图 smoke 是人工诊断证据，不要求 0 false positive；验收重点是 `preview_sheet` 和 overlays 能解释 accepted/blocked reasons，并且 M29 不污染 M8 `/primitives`、DSL、Renderer 或 Figma 可见输出。

M29.0.1 回归必须保护 accepted nodes 的 type/subtype/bbox 签名不因 blocked evidence 增强而变化；同时校验 blocked item 都有 bbox、metrics、细粒度 reasons、最小 context、`meta.blockedEvidenceVersion=0.2` 和 `meta.blockedReasonSummary`。真实图 smoke 重点看 blocked reasons 不再塌缩为 `symbol_metrics_rejected`。

M29.1 symbol fragment grouping smoke：

```bash
cd backend
uv run pytest tests/test_symbol_fragment_grouping.py -q
uv run python scripts/run_m29_1_symbol_grouping.py \
  --m29-output storage/m29_visual_primitive_graph \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png"
```

M29.1 合成测试必须覆盖 legacy evidence 拒绝、eligible blocked primitive 准入、hard-block reason 排除、edge accepted/weak/rejected audit、fragment group asset export、icon_button_group role、text-like sequence rejection、image internal texture 排除、原始 M29 nodes 不回写和 overlay PNG 可读。真实图 smoke 是人工诊断证据，不以 group 数量作为质量目标；验收重点是半截 symbol 是否减少、grouped asset 是否更完整、是否有明显误合并，以及 edge audit 是否解释得通。

阶段级工作必须先形成独立 commit，再在该提交之上运行完整验证。这样测试结果能绑定到明确阶段，避免 M11、M12 这类阶段被堆在同一个 dirty tree 里。如果提交后验证失败，使用同阶段 fix commit 修正并重新跑验证；不要继续开发下一阶段。

后续应继续扩展到：

- lint。
- 更完整 typecheck。
- 更完整 unit tests。
- integration tests。
- e2e tests。
- doc link checks。
