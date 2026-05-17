# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经进入 MVP 工程阶段。已完成文档 harness、pnpm monorepo、DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 后端、插件上传链路、真实 PNG deterministic region fallback DSL、M8 visual primitive contract harness、M9 OCR/DSL patch harness，M10 百度 PP-OCRv5 异步 OCR provider、M11 低风险可见文字替换 harness、M12 文字替换覆盖率扩展、M13 text replacement 质量控制、M14 UI-aware text replacement sampling、M15 text-primitive binding harness、M16 component structure harness、M17 DSL component annotation 和 layer naming harness、M18 component-aware layer separation candidate harness、M19 local asset slice/simple fill experiment harness、M20 icon candidate extraction/crop harness、M21 icon coverage audit/placement readiness harness、M22 region-guided icon gap candidate harness，以及 M23 icon placement plan/layering readiness harness。

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

当前 M23 默认仍使用 fake OCR 和 `TEXT_REPLACEMENT_MODE=debug`；显式设置 `OCR_PROVIDER=baidu_ppocrv5` 和百度 token 后，上传链路会生成真实 OCR candidates。`TEXT_REPLACEMENT_MODE=apply` 会写入通过 quality gate 的 accepted visible text replacement；M14 在 M13 quality gate 前增加 UI-aware sampling。M15-M18 生成 binding、structure、annotation 和 layer separation 报告，M19 生成本地 slice PNG 实验资产，M20 生成 icon PNG 候选资产，M21 审计 icon 覆盖和漏裁 hints，M22 补裁可靠 gap icon，M23 把 M20/M22 icon 统一成 placement plan，判断 dedupe、fallback mask、slice coordination、blocked 和 futureDslNodeHint。M15-M23 都不改变 Figma 可见输出，fallback region 始终保留。M19/M20/M21/M22/M23 不把实验 slice、icon、overlay 或 placement plan 写进 DSL assets，不做正式局部 fallback 替换，不做全局 icon detection，不做 Codia 式全量可拖动图层，不做 SVG/icon 语义识别、图标库匹配、复杂图形重建、AI inpainting，不引入 Pillow/OpenCV，不创建真实 Figma group、Component/Instance 或 Auto Layout。调试接口包括 `/ocr`、`/primitives`、`/dsl-patch`、`/text-replacements`、`/text-bindings`、`/component-structures`、`/component-annotations`、`/layer-separation-candidates`、`/asset-slice-candidates`、`/icon-candidates`、`/icon-coverage-audit`、`/icon-gap-candidates` 和 `/icon-placement-plan`。

下一步执行顺序：

1. 保持文档、ADR 和计划与实现同步。
2. 继续验证插件上传链路和 Figma 手动烟测。
3. 用固定样例目录持续验证三段 region fallback。
4. 持续用样例图验证 `TEXT_REPLACEMENT_MODE=debug/apply` 的 accepted/rejected/blocked 决策。
5. 下一步 M24 基于 M23 placement plan 做小范围 visible icon fallback experiment；默认仍不应盲目删除 fallback。

从 [docs/index.md](docs/index.md) 开始阅读。
