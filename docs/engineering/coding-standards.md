# 编码标准

本文档约束后续实现，不表示当前仓库已有代码。

## Project Shape

后续实现建议：

```text
figma-plugin/
backend/
packages/dsl-schema/
packages/image-to-figma-renderer/
```

不要在根目录散放实现文件。共享合同进 `packages/`，插件和后端通过合同交互。

## File And Module Shape

- 文件职责要窄。
- 大型 central 文件是设计压力，不是成就。
- Renderer 按元素类型拆模块。
- 后端按 API、service、pipeline、storage、dsl 拆模块。
- 插件 UI、Plugin Main、Renderer 调用不要混在同一个文件里。

## Boundary Rules

- Renderer 不导入后端代码。
- 后端不导入 Figma 插件代码。
- 插件 UI 不直接操作 Figma API。
- DSL 类型和 schema 是共享合同。
- API 响应结构必须和文档一致。

## Data Rules

- 不把业务语义塞进 style。
- 不用用户文件名作为服务端路径。
- 不让未校验 DSL 进入 Renderer。
- 不让 AI 自由改写金额、日期、手机号、订单号等敏感文本。

## Generated Artifacts

如果后续引入生成文件，必须记录：

- 生成命令。
- 输入来源。
- 输出路径。
- 何时需要重新生成。
- 如何检查漂移。
