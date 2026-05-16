# 测试策略

当前仓库已有最小 `@image-figma/dsl-schema` 包。本文件定义当前验证层和后续必须补的验证层。

## Validation Focus

v0.1 重点验证：

- DSL 合同稳定。
- Renderer 能用假 DSL 渲染。
- 后端 API 能返回可用任务和 DSL。
- 插件能完成主流程。
- 真实 PNG 样例能完成端到端链路。

## Test Layers

DSL Schema：

- 合法 DSL 通过。
- 缺必填字段失败。
- 非法 element type 失败。
- image assetId 不存在失败。
- normalize 能补默认值。
- repair 只做安全修复。

当前命令：

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
```

Renderer：

- 假 DSL 生成 root Frame。
- Text、Shape、Image 可渲染。
- 单元素失败不会中断整页。
- 图片加载失败产生 warning。
- 原图参考层默认隐藏。
- fallback 图片能显示。

Backend API：

- `GET /api/health` 成功。
- `POST /api/upload` 接受 PNG。
- 非 PNG 拒绝。
- 过大图片拒绝。
- task 状态可查询。
- completed 后 DSL 可获取。
- 未完成任务获取 DSL 返回明确错误。

Plugin UI：

- UploadView 能选择 PNG。
- PreviewView 显示文件信息。
- ProgressView 显示生成中。
- DoneView 显示成功。
- ErrorView 显示失败。
- UI 和 Main 消息流正确。

End-to-End：

- 单张 PNG -> taskId -> DSL -> Renderer -> Figma root Frame。
- 主要文字可编辑。
- 图片资产显示。
- 复杂区域 fallback。

## API Validation

API 变更必须验证：

- 路径。
- 请求格式。
- 响应格式。
- 错误码。
- 任务状态。
- 插件端兼容性。

## Regression Expectation

Bug 修复必须增加回归保护。优先级：

1. 自动化单测或集成测试。
2. e2e 测试。
3. schema/contract 检查。
4. 运行时断言。
5. 手工验证记录。

如果只能手工验证，必须在 bug 记录里写明原因。

## Repository Checks

当前统一检查入口：

```bash
pnpm run check
```

后续应继续扩展到：

- lint。
- 更完整 typecheck。
- 更完整 unit tests。
- integration tests。
- e2e tests。
- doc link checks。
