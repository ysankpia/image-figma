# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经进入 MVP 工程阶段。已完成文档 harness、pnpm monorepo、DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 后端、插件上传链路、真实 PNG deterministic region fallback DSL、M8 visual primitive contract harness，以及 M9 OCR/DSL patch harness。

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

当前 M9 默认生成 hidden OCR text candidates，但不做可见文字替换。上传链路仍保留 M7 fallback 视觉稳定性；`GET /api/tasks/{taskId}/ocr`、`/primitives`、`/dsl-patch` 用于调试后续识别合并。

下一步执行顺序：

1. 保持文档、ADR 和计划与实现同步。
2. 继续验证插件上传链路和 Figma 手动烟测。
3. 用固定样例目录持续验证三段 region fallback。
4. 在 M10 中做局部可见替换策略，先处理低风险文字或简单底板。
5. 把 deterministic fallback 逐步替换为更细的可编辑元素。

从 [docs/index.md](docs/index.md) 开始阅读。
