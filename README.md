# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经进入 MVP 工程阶段。已完成文档 harness、pnpm monorepo、DSL Schema、Renderer、Figma 插件静态 UI、FastAPI 假任务流，以及插件上传 PNG 后调用后端获取 DSL 并写入 Figma 的第一版链路。

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
3. 接入真实 PNG -> DSL 识别管线。
4. 做资产裁切、original reference 和 fallback 收敛。
5. 用固定样例做 MVP 验收。

从 [docs/index.md](docs/index.md) 开始阅读。
