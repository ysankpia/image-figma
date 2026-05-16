# 发布 Runbook

当前项目没有可发布代码。本文件定义后续发布前必须补的内容。

## Release Targets

未来可能存在：

- Figma 插件开发版。
- Figma 插件内测版。
- 后端 API 开发环境。
- 后端 API 内测环境。

## Release Checklist

后续发布前必须确认：

- P0 验收通过。
- DSL 版本明确。
- API 合同无未记录变更。
- 本地和 CI 检查通过。
- 样例验收记录完成。
- 已知问题记录清楚。
- 回滚方式明确。

## Versioning

DSL 版本和产品版本分开：

- DSL：`0.1`。
- 产品 MVP：`v0.1`。

不兼容 DSL 变更必须升级 DSL 版本。
