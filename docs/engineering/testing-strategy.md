# Testing Strategy

当前分支的测试入口已收敛到 [validation.md](validation.md)。

保留本文件是为了兼容历史文档链接。不要在这里继续维护独立测试策略；新的测试、真实样本验证、Draft artifact 验收和 Codia eval 边界都应写入 [validation.md](validation.md)。

Current product path:

```text
Figma Plugin
-> /api/draft-preview
-> Go backend
-> M29 physical evidence
-> optional vision detector/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma
```

Legacy Codia Beta and Python upload-preview checks are not current product acceptance gates unless a task explicitly targets those legacy paths.
