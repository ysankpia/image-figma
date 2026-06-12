# 编码标准

本文档约束后续实现，不表示当前仓库已有代码。

## Project Shape

后续实现建议：

```text
app/
components/
server/
shared/
tests/
```

不要新增无归属的散装实现文件。UI 放 `app/` 或 `components/`，API/导出/OCR/M29/AI provider 放 `server/`，跨前后端合同放 `shared/`，回归放 `tests/`。旧插件、旧后端和旧 renderer 在 `archive/legacy-code/`，不作为新产品代码落点。

## File And Module Shape

- 文件职责要窄。
- 大型 central 文件是设计压力，不是成就。
- UI 组件按工作台区域或页面职责拆模块。
- 后端按 API、storage、export、OCR、M29、AI provider 等边界拆模块。
- 不把 provider 调用、文件系统写入、UI 状态管理混进同一个文件。

## Boundary Rules

- 前端组件不直接读写本地文件系统。
- 服务端 provider 不绕过保存后的 SliceRecord。
- OCR/M29/AI 只能提供 evidence/candidates，不能成为最终可见 ownership。
- `shared/` 类型和 schema 是跨层合同。
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
