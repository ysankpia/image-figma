# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经进入 MVP 工程阶段。已完成文档 harness、pnpm monorepo、DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 后端、插件上传链路、真实 PNG deterministic region fallback DSL，以及 M8 visual primitive contract harness。

一期 MVP 只验证一条主链路：

```text
单张 PNG
-> 后端识别
-> visual primitive candidates
-> DSL v0.1
-> Figma Renderer
-> Figma 可编辑设计稿
```

当前 M8 只新增候选视觉基元合同，不改变插件输出。上传链路仍返回 M7 的 deterministic region fallback DSL；`GET /api/tasks/{taskId}/primitives` 只用于调试和后续 M9 合并逻辑。

下一步执行顺序：

1. 保持文档、ADR 和计划与实现同步。
2. 继续验证插件上传链路和 Figma 手动烟测。
3. 用固定样例目录持续验证三段 region fallback。
4. 在 M9 中合并 OCR boxes 和 visual primitives，生成可校验 DSL patch。
5. 把 deterministic fallback 逐步替换为可编辑元素。

从 [docs/index.md](docs/index.md) 开始阅读。
