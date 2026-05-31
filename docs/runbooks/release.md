# 发布 Runbook

当前项目没有正式发布流程。本文件定义后续发布前必须补的内容。

## Release Targets

未来可能存在：

- Figma 插件开发版。
- Figma 插件内测版。
- 后端 API 开发环境。
- 后端 API 内测环境。

## Release Checklist

后续发布前必须确认：

- P0 验收通过。
- Draft Runtime DSL 版本明确。
- API 合同无未记录变更。
- 本地和 CI 检查通过。
- 样例验收记录完成。
- 已知问题记录清楚。
- 回滚方式明确。

## Versioning

DSL 版本和产品版本分开：

- Draft Runtime DSL：`1.0`，artifact 文件名为 `draft_runtime.dsl.v1.json`。
- Editable Layer Graph：`ui.editable_layer_graph.v1` / `editable_layer_graph.v1.json`。
- 产品 MVP：`draft-mvp`，具体产品版本另行定义。

不兼容 DSL 变更必须升级 DSL 版本。
