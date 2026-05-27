# Agent Guidelines 中文参考快照

本文件是根目录 `AGENTS.md` 的中文参考快照。根目录 `AGENTS.md` 是 agent 执行时的权威版本；如果两者冲突，以根目录 `AGENTS.md` 为准。

# Repository Guidelines

本仓库采用 agent-first 工作流。仓库文件是事实来源，不依赖聊天记录；旧计划、ADR 和 legacy 草稿只能作为背景，不能覆盖当前代码和当前 docs。

## Project Structure & Module Organization

本仓库是 pnpm workspace 加 FastAPI 后端。`packages/dsl-schema/` 维护 DSL v0.1 类型、schema 和校验；`packages/image-to-figma-renderer/` 负责把已校验 DSL 写入 Figma adapter；`figma-plugin/` 包含插件 UI、main thread、manifest 和 bundle 检查；`backend/` 包含 FastAPI app、上传主链、M29 source truth、plan materializer、routes、storage helper 和 `backend/tests/`。

当前文档入口是 [../index.md](../index.md)。正式规格在 `docs/product/`、`docs/architecture/`、`docs/engineering/`、`docs/runbooks/`、`docs/reference/`、`docs/decisions/`、`docs/plans/` 和 `docs/bugs/`；历史草稿只保留在 `docs/reference/legacy/`。

## Current Mainline

当前唯一产品主链是：

```text
Figma Plugin
-> POST /api/upload-preview
-> OCR
-> M29 perception model report
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29 perception source compiler
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 ownership conservation report
-> M29 hierarchy candidate report
-> M29 sibling group candidate report
-> M29 layout energy report
-> M29 Auto Layout permission report
-> M29 plan-driven materializer
-> M29 perception fate trace report
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma
```

旧的 M29.6 -> transparent asset -> evidence contract -> internal source promotion -> promoted rerun loop 已不属于 active upload-preview 主链。不要把它恢复成默认 runtime path；这些 package 只能作为 legacy tests、diagnostics 或归档参考保留，直到明确删除。

`/api/upload-preview` 是正式上传入口。`/api/tasks/{taskId}/dsl` 是唯一正式设计稿出口。当前主线详情以 [../engineering/current-mainline-code-map.md](../engineering/current-mainline-code-map.md) 为准。

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

后端使用 `.tool-versions` 中的 Python 3.12.7：

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

TypeScript 使用 ESM、两空格缩进、`camelCase` 值/函数和 `PascalCase` 类型。Python 使用四空格缩进，模块和函数用 `snake_case`，在有助于边界表达时添加类型提示。

保持边界清楚：Renderer 不导入 backend；backend 不导入插件；插件 UI 不直接调用 Figma API；共享合同只通过 `packages/dsl-schema/`。不要提交 `dist/`、`backend/storage/`、数据库、日志、cache、密钥或临时产物。

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

## M29 Perception Fate Debugging

任何 model-first M29 可见回归，先看最新 task 的 perception fate trace：

```text
backend/storage/upload_previews/{taskId}/m29_perception_fate_trace/perception_fate_trace_report.json
```

它只能作为只读诊断索引。修复前先确认 `candidateId`、`bbox`、`compilerDecision`、`firstBlockingStage`、`firstBlockingReason`、`compiledSourceObjectId`、`finalReplayDecision` 和 `materializerDecision`。

按 trace 指出的 owning layer 修。不要在 perception fate trace、materializer、Renderer 或 plugin 里按 label、brand、filename、task id、固定 bbox、固定坐标、主题色或单张截图规则写特化。

失败证据和回归保护应放在 `docs/bugs/`、`docs/plans/`、tests 或 validation ledger，不能塞进 trace 本身。

## Commit & Pull Request Guidelines

提交使用 Conventional Commit 风格，例如 `docs:`、`refactor:`、`test:`、`feat:`、`fix:`。阶段工作必须形成独立提交，提交范围只包含本阶段代码、测试、文档、ADR 和计划更新；不要混入下一阶段探索、临时调试、storage、dist、密钥或无关本地改动。

PR 或交付说明应包含 changed surface、关联 plan/bug/ADR、验证命令和可见 UI/Figma/产物证据。新增 env var 时同步 `.env.example` 和 `docs/reference/env-vars.md`。

## Agent-Specific Guardrails

不要恢复已删除的 M29 Direct compare、legacy M30 materialization product path、M31-M39/M39.1 runtime、routes、env 或 ONNX proposer。旧 ADR、completed plans 和 legacy 草稿提到这些路径时，只能作为历史背景。

M29 perception model report 默认开启且只报告模型候选；它不能创建 source object、DSL node、asset、replay 授权或 cleanup 授权。M29 perception source compiler 是模型候选进入增强 M29.2 source ownership 的默认桥；编译后的对象仍必须经过 M29.3/M29.4/M29.5 才能 materialize。M29 perception fate trace 只做诊断，不能参与 source ownership、M29.5、materializer、Renderer 或 plugin 决策。

M29.4 weak cluster、M29 ownership conservation、M29 hierarchy candidates、M29 sibling group candidates、M29 layout energy 和 M29 Auto Layout permission 是 active evidence/permission surfaces。C-stage materialization 只能消费高置信 structural evidence，在已 replay 的节点外创建透明 controlled structure group；不能创建 Auto Layout、Figma Component/Instance、variables、variants、vectors 或新的 visible owner nodes。M29.5 replay plan 是唯一 materialization order、node budget、dedupe、visible replay 和 cleanup 授权来源。M29 plan-driven materializer 只执行 plan，不重新判断 owner，不新增 cleanup 授权。

M29.6 media internal decomposition、M29 transparent asset report、M29 evidence contract report、M29 internal source promotion 和 M29 bridge fate trace 是 pre-model visual-discovery loop 的 legacy compatibility surfaces。它们不能重新接回默认 upload-preview pipeline。若未来显式用于归档对照，也只能保持 report-only/compat-only，不能在明确批准的 migration 之外创建 source objects、DSL nodes、assets、replay authorization 或 cleanup authorization。

Source ownership 问题必须从 raw M29 或 M29.2 修起；不要在 materializer、Renderer 或 plugin 里按颜色、文案、主题、行业、文件名或固定 bbox 写特化补丁。root/page 背景必须来自 source PNG 采样，不恢复固定浅色默认背景来掩盖 fallback-off 问题。
