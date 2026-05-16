# MVP Bootstrap 实现计划

- 状态：active
- 创建日期：2026-05-16
- 负责人：Codex

## Goal

在文档 harness 完成后，进入最小工程实现，按主链路顺序建立可运行 MVP。

## Scope

包含：

- 初始化工程骨架。
- 实现 DSL Schema 与示例 DSL。
- 实现 Renderer 假 DSL 渲染。
- 实现 Figma 插件最小 UI。
- 实现后端上传、任务、假 DSL。
- 接入真实 OCR/AI/裁切。
- 做样例验收。

不包含：

- 账号、支付、额度。
- 批量上传。
- 历史记录。
- 质量报告。
- 代码生成。
- Component/Instance。
- Auto Layout。

## Steps

1. 初始化 repo 工程骨架，建立 `figma-plugin/`、`backend/`、`packages/dsl-schema/`、`packages/image-to-figma-renderer/`。状态：完成。
2. 做 DSL Schema、类型、示例 DSL 和校验。状态：完成第一版。
3. 做 Renderer，用假 DSL 在 Figma 生成 root、text、shape、image。
4. 做插件最小 UI 和 UI/Main 消息流。
5. 做后端 `health`、`upload`、`task`、`dsl`、`asset` API，先返回假 DSL。
6. 接入真实 PNG -> OCR/AI -> DSL Builder。
7. 加入资产裁切、original reference 和 fallback。
8. 用固定样例做 MVP 收敛。

## Acceptance

- 假 DSL 能渲染到 Figma。
- 插件能通过后端拿到 DSL。
- 真实 PNG 能生成可校验 DSL。
- 主要文字可编辑。
- 图片资产能显示。
- 复杂区域能 fallback。
- 失败能定位阶段和错误码。

## Validation

- DSL schema 测试。
- Renderer 假 DSL 测试。
- 后端 API 集成测试。
- 插件 UI 状态测试。
- 样例端到端验收。

## Current Evidence

当前已完成：

- Git 仓库初始化。
- pnpm workspace 初始化。
- `@image-figma/dsl-schema` 最小包。
- DSL TypeScript 类型。
- JSON Schema。
- 四份示例 DSL。
- normalize、validator、repair。
- 单元测试。

验证命令：

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
pnpm run check
```
