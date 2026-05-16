# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经进入 MVP 工程阶段。已完成文档 harness、pnpm monorepo、DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 后端、插件上传链路、真实 PNG deterministic region fallback DSL、M8 visual primitive contract harness、M9 OCR/DSL patch harness，M10 百度 PP-OCRv5 异步 OCR provider、M11 低风险可见文字替换 harness、M12 文字替换覆盖率扩展、M13 text replacement 质量控制、M14 UI-aware text replacement sampling、M15 text-primitive binding harness、M16 component structure harness，以及 M17 DSL component annotation 和 layer naming harness。

一期 MVP 只验证一条主链路：

```text
单张 PNG
-> 后端识别
-> visual primitive candidates
-> OCR / DSL patch candidates
-> DSL v0.1
-> Figma Renderer
-> Figma 可编辑设计稿
```

当前 M17 默认仍使用 fake OCR 和 `TEXT_REPLACEMENT_MODE=debug`；显式设置 `OCR_PROVIDER=baidu_ppocrv5` 和百度 token 后，上传链路会生成真实 OCR candidates。`TEXT_REPLACEMENT_MODE=apply` 会写入通过 quality gate 的 accepted visible text replacement；M14 在 M13 quality gate 前增加 UI-aware sampling，用 badge、legend、outline button、card/tip 和 bottom nav 局部采样减少 `complex_background` 误杀。M15 默认生成 text binding 报告，M16 默认生成 component structure 报告，M17 默认把 M16 结构以 annotation 和 layer name 形式挂回 DSL。M15-M17 都不改变 Figma 可见输出，fallback region 始终保留。M17 不切图，不做图标、圆形、三角形、五角星或复杂图形重建，不创建真实 Figma group、Component/Instance 或 Auto Layout。`GET /api/tasks/{taskId}/ocr`、`/primitives`、`/dsl-patch`、`/text-replacements`、`/text-bindings`、`/component-structures`、`/component-annotations` 用于调试后续识别合并、sampling strategy、replacement 质量决策、binding、结构报告和 DSL annotation。

下一步执行顺序：

1. 保持文档、ADR 和计划与实现同步。
2. 继续验证插件上传链路和 Figma 手动烟测。
3. 用固定样例目录持续验证三段 region fallback。
4. 持续用样例图验证 `TEXT_REPLACEMENT_MODE=debug/apply` 的 accepted/rejected/blocked 决策。
5. 下一步 M18 基于 M17 annotation 评估 local asset slicing，但默认仍不删除 fallback。

从 [docs/index.md](docs/index.md) 开始阅读。
