# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经进入 MVP 工程阶段。已完成文档 harness、pnpm monorepo、DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 后端、插件上传链路，以及基于真实 PNG 的 deterministic region fallback DSL 第一版链路。

一期 MVP 只验证一条主链路：

```text
单张 PNG
-> 后端识别
-> DSL v0.1
-> Figma Renderer
-> Figma 可编辑设计稿
```

下一步执行顺序：

1. 保持文档、ADR 和计划与实现同步。
2. 继续验证插件上传链路和 Figma 手动烟测。
3. 用固定样例目录持续验证三段 region fallback。
4. 接入 OCR/AI 识别管线，把 deterministic fallback 逐步替换为可编辑元素。
5. 做更细资产裁切和局部 fallback 收敛。

从 [docs/index.md](docs/index.md) 开始阅读。
