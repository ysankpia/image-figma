# MVP Bootstrap 实现计划

- 状态：active
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

在文档 harness 完成后，进入最小工程实现，按主链路顺序建立可运行 MVP。

## Scope

包含：

- 初始化工程骨架。
- 实现 DSL Schema 与示例 DSL。
- 实现 Renderer 假 DSL 渲染。
- 实现 Figma 插件最小 UI。
- 实现后端上传、任务、假 DSL。
- 建立 visual primitive contract harness。
- 接入 OCR boxes + visual primitives -> DSL patch builder。
- 接入百度 PP-OCRv5 异步 OCR provider。
- 接入文字替换覆盖率扩展 harness。
- 接入 UI-aware text replacement sampling。
- 接入 text-primitive binding harness。
- 接入 component structure harness。
- 接入 DSL component annotation/layer naming harness。
- 接入 component-aware layer separation candidate harness。
- 接入 local asset slice/simple fill experiment harness。
- 做样例验收。

不包含：

- 账号、支付、额度。
- 批量上传。
- 历史记录。
- 质量报告。
- 代码生成。
- Component/Instance。
- Auto Layout。

## Steps

1. 初始化 repo 工程骨架，建立 `figma-plugin/`、`backend/`、`packages/dsl-schema/`、`packages/image-to-figma-renderer/`。状态：完成。
2. 做 DSL Schema、类型、示例 DSL 和校验。状态：完成第一版。
3. 做 Renderer，用假 DSL 在 Figma 生成 root、text、shape、image。状态：完成第一版。
4. 做插件最小 UI 和 UI/Main 消息流。状态：完成第一版。
5. 做后端 `health`、`upload`、`task`、`dsl`、`asset` API，先返回假 DSL。状态：完成第一版。
6. 插件接入后端上传、任务查询和 DSL 获取。状态：完成第一版。
7. 接入真实 PNG -> deterministic DSL Builder。状态：完成第一版。
8. 接入 deterministic region slicer，把整图 fallback 拆成稳定区域。状态：完成第一版。
9. 建立 visual primitive contract harness，AI/OCR/CV 只产生可验证候选，不直接生成 DSL。状态：完成第一版。
10. 接入 OCR boxes + visual primitives -> DSL patch builder。状态：完成第一版。
11. 接入百度 PP-OCRv5 异步 OCR provider。状态：完成第一版。
12. 接入文字替换覆盖率扩展 harness。状态：完成第一版。
13. 接入 text replacement quality gate。状态：完成第一版。
14. 接入 UI-aware text replacement sampling，减少 `complex_background` 误杀。状态：完成第一版。
15. 接入 text-primitive binding harness，为组件化前的归属关系打基础。状态：完成第一版。
16. 接入 component structure harness，把 M15 bindings 聚合为 component candidates 和 layout groups。状态：完成第一版。
17. 接入 DSL component annotation/layer naming harness，把 M16 结构安全挂回已有 DSL element 的 `name/meta`。状态：完成第一版。
18. 接入 component-aware layer separation candidate harness，先生成分层策略报告和 simple fill candidate，不改变画布。状态：完成第一版。
19. 接入 local asset slice/simple fill experiment harness，生成候选 PNG 资产但不改变画布。状态：完成第一版。
20. 加入 partial fallback replacement 实验，基于 M19 资产做局部替换验证。
21. 用固定样例做 MVP 收敛。

## Acceptance

- 假 DSL 能渲染到 Figma。
- 插件能通过后端拿到 DSL。
- 真实 PNG 能生成可校验 DSL。
- visual primitive candidates 可查询且不污染 DSL。
- 后续主要文字可见可编辑。
- 图片资产能显示。
- 复杂区域能 fallback。
- 失败能定位阶段和错误码。

## Validation

- DSL schema 测试。
- Renderer 假 DSL 测试。
- 后端 API 集成测试。
- 插件 UI 状态测试。
- 样例端到端验收。

## Current Evidence

当前已完成：

- Git 仓库初始化。
- pnpm workspace 初始化。
- `@image-figma/dsl-schema` 最小包。
- `@image-figma/image-to-figma-renderer` 最小包。
- Figma dev harness。
- Figma 插件最小静态 UI。
- DSL TypeScript 类型。
- JSON Schema。
- 四份示例 DSL。
- normalize、validator、repair。
- Renderer adapter、P0 元素渲染、warning/error 收集。
- UI/Main `render-sample` 消息流。
- Figma 插件 bundle 兼容性扫描。
- FastAPI 后端假任务流。
- SQLite `tasks`、`assets`、`dsl_results`、`error_logs`。
- 本地 `/files/uploads` 和 `/files/assets` 静态文件服务。
- 插件 PNG 上传 -> 后端 deterministic DSL -> Renderer 主链路。
- 后端 deterministic DSL 使用真实 PNG 宽高、原图隐藏层和三段 region fallback。
- 标准库 PNG cropper。
- `header`、`content`、`bottom` region asset。
- VisualPrimitiveDocument v0.1 合同。
- 默认 fake primitive provider。
- 可选 OpenAI primitive provider。
- SQLite `primitive_results`。
- `GET /api/tasks/{taskId}/primitives`。
- OCRDocument v0.1 合同。
- 默认 fake OCR provider。
- DSLPatchDocument v0.1 合同。
- SQLite `ocr_results` 和 `dsl_patch_results`。
- `GET /api/tasks/{taskId}/ocr`。
- `GET /api/tasks/{taskId}/dsl-patch`。
- hidden `candidate_text` debug 合并。
- 百度 PP-OCRv5 异步 OCR provider。
- `OCR_PROVIDER=baidu_ppocrv5`。
- OCR 低置信度过滤。
- 百度失败回退 fallback DSL。
- TextReplacementDocument v0.1 合同。
- SQLite `text_replacement_results`。
- `GET /api/tasks/{taskId}/text-replacements`。
- `TEXT_REPLACEMENT_MODE=debug/apply`。
- 低复杂度背景文字 cover/text replacement，包含浅底深字和部分彩色/深色底浅字。
- text replacement quality gate，包含 applied/blocked/risk/region/reason 报告。
- UI-aware text replacement sampling，包含 strategy attempts、strategy summary 和 rescued count。
- TextPrimitiveBindingDocument v0.1 合同。
- SQLite `text_binding_results`。
- `GET /api/tasks/{taskId}/text-bindings`。
- text-to-container binding 报告，包含 inferred UI containers、bindings 和 unboundTextIds。
- ComponentStructureDocument v0.1 合同。
- SQLite `component_structure_results`。
- `GET /api/tasks/{taskId}/component-structures`。
- component structure 报告，包含 component candidates、layout groups 和 unstructuredContainerIds。
- ComponentAnnotationDocument v0.1 合同。
- SQLite `component_annotation_results`。
- `GET /api/tasks/{taskId}/component-annotations`。
- component annotation 报告，包含 annotations、groupHints、unannotatedElementIds 和 unresolvedComponentIds。
- DSL element `name/meta` annotation，且只改已有 element 的 `name` 和 `meta`。
- LayerSeparationDocument v0.1 合同。
- SQLite `layer_separation_results`。
- `GET /api/tasks/{taskId}/layer-separation-candidates`。
- layer separation candidate 报告，包含 candidates、fallbackContexts、blockedComponentIds 和 simple fill candidate 统计。
- DSL 顶层 M18 meta，且不改任何已有 element。
- AssetSliceCandidateDocument v0.1 合同。
- SQLite `asset_slice_results`。
- `GET /api/tasks/{taskId}/asset-slice-candidates`。
- local asset slice candidate 报告，包含 slices、blockedComponentIds 和 original/filled slice 统计。
- 本地 `assets/{taskId}/slices/*.png` 实验资产。
- DSL 顶层 M19 meta，且不改任何已有 element 或 DSL assets。
- 单元测试。

验证命令：

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
pnpm --filter @image-figma/figma-plugin run build
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm run check
cd backend && uv run pytest
```
