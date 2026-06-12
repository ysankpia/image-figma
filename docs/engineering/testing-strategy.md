# Testing Strategy

当前分支的测试入口已收敛到 [validation.md](validation.md)。

保留本文件是为了兼容历史文档链接。不要在这里继续维护独立测试策略；新的测试、真实样本验证、Slice Studio artifact 验收、历史 Draft artifact 验收和 Codia eval 边界都应写入 [validation.md](validation.md)。

Current product path:

```text
1..N UI screenshots/design images
-> repository root
-> saved SliceRecord boxes in SQLite
-> assets.zip
-> project.zip / design.pen
```

Go Draft, legacy Codia Beta, Python Pencil, and Python upload-preview checks are not current product acceptance gates unless a task explicitly targets those historical paths.
