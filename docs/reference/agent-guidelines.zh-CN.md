# Agent Guidelines 中文参考快照

本文件是根目录 `AGENTS.md` 的中文参考快照。根目录 `AGENTS.md` 是 agent 执行时的权威版本；如果两者冲突，以根目录 `AGENTS.md` 为准。

# Repository Guidelines

本仓库采用 agent-first 工作流。仓库文件是事实来源，不依赖聊天记录；旧计划、ADR 和 legacy 草稿只能作为背景，不能覆盖当前代码和当前 docs。

## Project Structure & Module Organization

本仓库是 pnpm workspace 加两条后端运行面。`services/backend-go/` 是当前 Codia Beta / `Generate Beta` 的 Go 后端，负责 `codiaserver`、Go M29 physical evidence、UI detector 接入、Codia assembly/control/tree/emitter、DSL v0.2 export、本地 crop assets 和 Go tests。`backend/` 是保留的 Python/FastAPI M29 DSL v0.1 upload-preview 路径和历史算法/参考面；除非任务明确针对 `/api/upload-preview`，否则不要把它作为 Codia Beta 输出质量调试起点。`packages/dsl-schema/` 维护 DSL 合同；`packages/image-to-figma-renderer/` 负责把已校验 DSL 写入 Figma adapter；`figma-plugin/` 包含插件 UI、main thread、manifest 和 bundle 检查。

当前文档入口是 [../index.md](../index.md)。正式规格在 `docs/product/`、`docs/architecture/`、`docs/engineering/`、`docs/runbooks/`、`docs/reference/`、`docs/decisions/`、`docs/plans/` 和 `docs/bugs/`；历史草稿只保留在 `docs/reference/legacy/`。

## Current Runtime Surfaces

当前 Codia Beta 开发和调试主链是 Go：

```text
Figma Plugin Generate Beta
-> POST /api/codia-preview
-> Go codiaserver
-> OCR
-> Go M29 physical evidence
-> optional OpenAI-compatible UI detector
-> Codia assembly/control/tree/emitter
-> DSL v0.2 Codia Runtime
-> GET /api/codia-preview/{taskId}/dsl
-> GET /api/codia-preview/{taskId}/assets/{assetId}.png
-> renderCodiaRuntimeDesign
-> Figma
```

Codia Beta 缺陷先查：

```text
services/backend-go/
services/backend-go/storage/codia_server/codia_previews/{taskId}/compile/
packages/image-to-figma-renderer/src/renderCodiaRuntimeDesign.ts
figma-plugin/src/
```

保留的 Python/FastAPI preview 运行面是：

```text
Figma Plugin
-> POST /api/upload-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 ownership conservation report
-> M29.6 media internal decomposition report
-> M29 transparent asset report
-> M29 internal source promotion
-> M29.3/M29.4/M29.5 final reports from promoted M29.2
-> M29 hierarchy candidate report
-> M29 sibling group candidate report
-> M29 layout energy report
-> M29 Auto Layout permission report
-> M29 plan-driven materializer
-> M29 design token report
-> M29 B-stage quality report
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma
```

`/api/codia-preview` 是 Codia Beta 正式上传入口。`/api/codia-preview/{taskId}/dsl` 是 Codia Beta DSL v0.2 输出端点。`/api/upload-preview` 和 `/api/tasks/{taskId}/dsl` 仍是 Python DSL v0.1 preview 路径，不得当成 Codia Beta 后端。当前运行面详情以 [../engineering/current-mainline-code-map.md](../engineering/current-mainline-code-map.md) 为准。

## Documentation Routing

先读本文件，再读 [../index.md](../index.md)，然后按任务只读相关文档。

- 产品范围和验收：`docs/product/`。
- DSL、API、Renderer、后端、插件边界：`docs/architecture/`。
- 当前代码地图、测试、文档维护和 M29 regression matrix：`docs/engineering/`。
- 运行、发布、调试、迁移：`docs/runbooks/`。
- 环境变量、外部接口、术语和 legacy 草稿：`docs/reference/`。
- 计划：`docs/plans/active/`、`docs/plans/completed/`、`docs/plans/archive/`。
- bug 复盘和回归保护：`docs/bugs/`。

ADR 是历史决策记录，不等于 active runtime。涉及被删除链路时，以当前代码地图、测试策略和最新 completed plan 为准。

## Build, Test, and Development Commands

安装和 workspace 检查：

```bash
pnpm install
pnpm run check
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

当前 Codia Beta 后端是 Go：

```bash
cd services/backend-go
go test ./internal/codia/... ./cmd/codiacompile ./cmd/codiaserver
CODIA_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/codiaserver
```

保留的 Python/FastAPI preview 路径使用 `.tool-versions` 中的 Python 3.12.7；只有任务明确针对 `/api/upload-preview`、Python M29 v0.1 或历史 M29 参考行为时才使用：

```bash
cd backend
uv sync
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
uv run pytest -q
```

交付前至少检查：

```bash
git diff --check
git status --short --branch
```

## Coding Style & Boundary Rules

TypeScript 使用 ESM、两空格缩进、`camelCase` 值/函数和 `PascalCase` 类型。Go 代码使用 `gofmt`，在合适时使用 table-driven tests，包要小而职责清楚，默认优先标准库。Python 使用四空格缩进，模块和函数用 `snake_case`，在有助于边界表达时添加类型提示。

保持边界清楚：Renderer 不导入 backend；Go/Python 后端不导入插件；插件 UI 不直接调用 Figma API；共享合同只通过 `packages/dsl-schema/`。不要提交 `dist/`、`backend/storage/`、`services/backend-go/storage/`、数据库、日志、cache、密钥或临时产物。

优先简单、当前可验证的实现。不要为假想未来加抽象，不创建 `utils`、`common`、`misc` 垃圾桶模块。大型中心文件是设计压力；继续增加行为前优先按真实职责拆模块。

## Planning & Documentation Rules

以下工作必须先创建或更新 `docs/plans/active/` 中的计划：

- 影响多个模块或目录。
- 修改 DSL、API、数据模型、环境变量或运行方式。
- 增加依赖、工程脚本或 CI 行为。
- 修改插件、Renderer、后端、M29 evidence chain、replay plan 或 materializer 主链能力。
- 修复会影响主链路的缺陷。

计划状态必须和目录一致：未完成计划放 `active/`，已完成计划放 `completed/`，被替代或暂缓的计划放 `archive/` 对应子目录。行为、API、数据模型、环境变量、构建命令、运行步骤、架构边界或验收标准变化，必须同步更新相关 docs。

## Testing & Validation Rules

测试策略以 [../engineering/testing-strategy.md](../engineering/testing-strategy.md) 为准。DSL 改动必须有 schema 或等价合同校验；Renderer 改动必须能用测试 DSL 验证；后端 API 改动必须有接口级验证；插件或 Figma 可见行为改动必须按本项目验证文档记录可观察结果。

M29 owner、relation、replay、materializer、cleanup 授权或 fallback 行为改动，必须先映射到 [../engineering/m29-contract-regression-matrix.md](../engineering/m29-contract-regression-matrix.md)。没有覆盖就先补测试或明确记录无法自动化的替代 guard。

## Bugfix & Regression Rules

Bug 工作从 `docs/bugs/index.md` 和相关 bug 记录开始。修复前先复现，修复后记录根因、修复摘要、回归保护和验证证据。无法添加自动化回归时，必须在 bug 记录中写明替代 guard 和剩余风险。

## Runtime Debugging

Codia Beta / `Generate Beta` 回归先查最新 Go task：

```text
services/backend-go/storage/codia_server/codia_previews/{taskId}/compile/
```

优先看：

```text
codia_runtime.dsl.v0_2.json
codia_tree_ir.v1.json
assembly/codia_source_candidates.v1.json
assembly/codia_ownership_graph.v1.json
detector/ui_detector_candidates.v1.json
assets/
```

修复归属层必须在 Go 的 detector、assembly、control、tree、DSL v0.2 export、`codiaserver`、runtime renderer 或插件 Beta wiring 中判断。除非 Go artifact 证明 Python 是输入来源，否则不要在 Python `backend/app` 修 Codia Beta 问题。

## Commit & Pull Request Guidelines

提交使用 Conventional Commit 风格，例如 `docs:`、`refactor:`、`test:`、`feat:`、`fix:`。阶段工作必须形成独立提交，提交范围只包含本阶段代码、测试、文档、ADR 和计划更新；不要混入下一阶段探索、临时调试、storage、dist、密钥或无关本地改动。

PR 或交付说明应包含 changed surface、关联 plan/bug/ADR、验证命令和可见 UI/Figma/产物证据。新增 env var 时同步 `.env.example` 和 `docs/reference/env-vars.md`。

## Agent-Specific Guardrails

不要恢复已删除的 M29 Direct compare、legacy M30 materialization product path、M31-M39/M39.1 runtime、routes、env 或 ONNX proposer。旧 ADR、completed plans 和 legacy 草稿提到这些路径时，只能作为历史背景。

M29.4 weak cluster、M29 ownership conservation、M29.6 media internal decomposition、M29 transparent asset report、M29 hierarchy candidates、M29 sibling group candidates、M29 layout energy、M29 Auto Layout permission、M29 design token 和 M29 B-stage quality reports 都是 evidence/permission/diagnostic surfaces。C-stage materialization 只能消费高置信 structural evidence，在已 replay 的节点外创建透明 controlled structure group；不能创建 Auto Layout、Figma Component/Instance、variables、variants、vectors 或新的 visible owner nodes。M29.6 不能自己提升内部 media candidates 或授权 cleanup。M29 transparent asset report 只能生成诊断 RGBA artifact；不能自己替换 materialized assets 或授权 cleanup。M29 internal source promotion 是当前唯一能把 M29.6/transparent evidence 回灌到 M29.2 source ownership 的桥；promoted objects 必须重新经过 M29.3/M29.4/M29.5 才能 materialize。M29.5 replay plan 是唯一 materialization order、node budget、dedupe、visible internal icon replay 和 cleanup 授权来源。M29 plan-driven materializer 只执行 plan，不重新判断 owner，不新增 cleanup 授权。

Source ownership 问题必须从 raw M29 或 M29.2 修起；不要在 materializer、Renderer 或 plugin 里按颜色、文案、主题、行业、文件名或固定 bbox 写特化补丁。root/page 背景必须来自 source PNG 采样，不恢复固定浅色默认背景来掩盖 fallback-off 问题。
