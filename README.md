# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库处于文档 harness 阶段，还没有代码实现。现在的核心工作是把产品范围、系统边界、DSL/API/Renderer 合同、验收标准和后续计划写进仓库文件，让后续实现不再依赖聊天上下文。

一期 MVP 只验证一条主链路：

```text
单张 PNG
-> 后端识别
-> DSL v0.1
-> Figma Renderer
-> Figma 可编辑设计稿
```

下一步执行顺序：

1. 完成并维护文档 harness。
2. 初始化工程骨架。
3. 实现 DSL Schema 与示例 DSL。
4. 实现 Renderer 用假 DSL 写入 Figma。
5. 实现插件最小 UI 与后端 API。
6. 接入真实 PNG -> DSL 识别管线。

从 [docs/index.md](docs/index.md) 开始阅读。
