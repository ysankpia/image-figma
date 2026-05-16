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
- M15 text binding 必须覆盖默认生成报告、`TEXT_BINDING_ENABLED=false` 不生成报告、`/text-bindings` API、DSL meta、不新增可见节点，以及 badge/status/button/card/legend/tip/bottom nav 绑定规则。
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

阶段级工作必须先形成独立 commit，再在该提交之上运行完整验证。这样测试结果能绑定到明确阶段，避免 M11、M12 这类阶段被堆在同一个 dirty tree 里。如果提交后验证失败，使用同阶段 fix commit 修正并重新跑验证；不要继续开发下一阶段。

后续应继续扩展到：

- lint。
- 更完整 typecheck。
- 更完整 unit tests。
- integration tests。
- e2e tests。
- doc link checks。
