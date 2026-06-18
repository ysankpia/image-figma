# 文档地图

本目录是 Image-to-Figma Design 的事实来源。当前默认可交付产品是 **Slice Studio**，不是旧 Pencil Python Backend、Go Draft、Python upload-preview、Figma plugin runtime 或 Codia-like 自动生成路线。

当前主线：

```text
1..N UI screenshots/design images
-> repository root
-> project workspace
-> saved SliceRecord boxes in SQLite
-> assets.zip
-> project.zip / design.pen
```

旧代码和历史文档保留为 reference、fallback、deferred runtime 或 legacy research。它们不能覆盖 `AGENTS.md`、`PROGRESS.md`、`docs/product/direction-contract.md`、本文件和当前 code map。

## Start Here

按顺序阅读：

1. [../AGENTS.md](../AGENTS.md)：仓库规则、当前主线、禁止项。
2. [../PROGRESS.md](../PROGRESS.md)：当前目标、active plan、验证日志和 checkpoint。
3. [product/direction-contract.md](product/direction-contract.md)：最终产物、truth source、repair path、non-goals 和验证产物。
4. [roadmap.md](roadmap.md)：当前阶段、下一步和开放问题。
5. [../README.md](../README.md) 和 [reference/slice-studio-runtime.md](reference/slice-studio-runtime.md)：Slice Studio 运行、产品行为、配置和存储。
6. [engineering/current-code-map.md](engineering/current-code-map.md)：当前代码地图。
7. [engineering/legacy-code-inventory.md](engineering/legacy-code-inventory.md)：旧代码分类和恢复规则。
8. [engineering/validation.md](engineering/validation.md)：验证策略。
9. [reference/env-vars.md](reference/env-vars.md)：环境变量。
10. [reference/slice-studio-ai-slice-prompt-strategies.md](reference/slice-studio-ai-slice-prompt-strategies.md)：当前 AI 画框 prompt 策略记录。

## Current Runtime

Slice Studio local runtime:

```text
Next web:  http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
```

Primary API surface:

```text
GET    /api/health
GET    /api/auth/session
POST   /api/auth/sign-up
POST   /api/auth/sign-in
POST   /api/auth/sign-out
GET    /api/storage-download?token=...
GET    /api/ai-slice-settings
GET    /api/projects
POST   /api/projects
GET    /api/projects/:projectId
PATCH  /api/projects/:projectId
DELETE /api/projects/:projectId
POST   /api/projects/:projectId/pages
PATCH  /api/projects/:projectId/pages/order
PATCH  /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/replace
DELETE /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/ai-boxes
GET    /api/projects/:projectId/pages/:pageId/source
PUT    /api/projects/:projectId/slices
GET    /api/projects/:projectId/slices/:sliceId/preview.png
POST   /api/projects/:projectId/export-assets
GET    /api/projects/:projectId/assets.zip
POST   /api/projects/:projectId/export-project
POST   /api/projects/:projectId/pages/:pageId/export-project
GET    /api/projects/:projectId/project.zip
GET    /api/projects/:projectId/pages/:pageId/project.zip
```

Primary contracts:

- authenticated user/session: project access truth for production phase;
- saved Slice Studio slices: live edit/export truth;
- `manual_ui_slices.v1`: export manifest schema;
- `assets.zip`: frontend asset output;
- `project.zip/design.pen`: Pencil/Figma handoff output;
- AI boxes: transient suggestions converted into normal slices;
- OCR/M29: editable text evidence only.

## Active Production Plans

Completed prelaunch hardening work is tracked in [plans/completed/190-slice-studio-prelaunch-codebase-hardening.md](plans/completed/190-slice-studio-prelaunch-codebase-hardening.md).

Formal multi-user production-readiness work is tracked in [plans/active/189-slice-studio-multi-user-production-launch.md](plans/active/189-slice-studio-multi-user-production-launch.md).

Current user-only cleanup is tracked in [plans/completed/196-user-only-surface-simplification.md](plans/completed/196-user-only-surface-simplification.md). Plan 196 deliberately removes the admin, billing, payment, entitlement, usage, order, quota, and XPay side chain from the current runtime. Do not reintroduce those surfaces from older 189 notes without a new active plan.

Plan 190 should run before disruptive production implementation:

```text
protect existing local storage
-> clarify the repository root as the mainline
-> mark legacy/reference code in place
-> harden OpenRouter/OpenAI-compatible AI provider support
-> run repeatable smoke validation
```

Current implementation has landed same-origin `/api` browser access, custom session auth, repeatable local bootstrap owner, project ownership, `/settings`, user-scoped local storage keys, signed downloads, AI-assisted boxes, and assets/Pencil exports. Billing/admin/payment/entitlement work is no longer part of the current runtime after plan 196.

This plan changes the next phase from local/private tool hardening to formal multi-user product launch planning:

```text
landing page
-> login/register
-> authenticated project workspace
-> user-owned projects/pages/slices/exports
-> production deployment and backup/restore
```

Payment provider selection is intentionally deferred. The current product can later point users to an external purchase link or add a new provider behind a separate plan, but no payment/admin/entitlement code is active today.

AI provider selection is also replaceable. OpenRouter or another OpenAI-compatible provider can be evaluated through the AI provider configuration boundary without changing the saved-slice/export truth source.

## By Task Type

- Slice Studio UI/API/export work: read [../README.md](../README.md), [reference/slice-studio-runtime.md](reference/slice-studio-runtime.md), [architecture/overview.md](architecture/overview.md), [architecture/api-contracts.md](architecture/api-contracts.md), [engineering/validation.md](engineering/validation.md).
- Prelaunch codebase hardening: read [plans/completed/190-slice-studio-prelaunch-codebase-hardening.md](plans/completed/190-slice-studio-prelaunch-codebase-hardening.md), [engineering/current-code-map.md](engineering/current-code-map.md), [engineering/legacy-code-inventory.md](engineering/legacy-code-inventory.md), and [reference/env-vars.md](reference/env-vars.md).
- Multi-user/user-only production work: read [plans/completed/196-user-only-surface-simplification.md](plans/completed/196-user-only-surface-simplification.md), [plans/active/189-slice-studio-multi-user-production-launch.md](plans/active/189-slice-studio-multi-user-production-launch.md), [product/direction-contract.md](product/direction-contract.md), [product/requirements.md](product/requirements.md), [product/user-flows.md](product/user-flows.md), [reference/env-vars.md](reference/env-vars.md), and [engineering/validation.md](engineering/validation.md). Treat 196 as the current runtime boundary where it conflicts with older 189 payment/admin notes.
- Frontend redesign handoff: read [reference/slice-studio-frontend-function-inventory.md](reference/slice-studio-frontend-function-inventory.md) for the current page, feature, field, API, and boundary inventory. This is a function contract, not a UX or visual direction document.
- AI slice boxes: read [reference/slice-studio-ai-slice-prompt-strategies.md](reference/slice-studio-ai-slice-prompt-strategies.md), [plans/completed/182-slice-studio-ai-rect-slice-assist.md](plans/completed/182-slice-studio-ai-rect-slice-assist.md), [plans/completed/183-slice-studio-ai-tile-merge-and-progress.md](plans/completed/183-slice-studio-ai-tile-merge-and-progress.md).
- OCR / editable text / M29 physical evidence: read [plans/completed/177-slice-studio-pencil-editable-text-layer-v1.md](plans/completed/177-slice-studio-pencil-editable-text-layer-v1.md), [plans/completed/178-slice-studio-baidu-ocr-provider-and-text-quality-gate.md](plans/completed/178-slice-studio-baidu-ocr-provider-and-text-quality-gate.md), [plans/completed/181-slice-studio-m29-physical-evidence-ts.md](plans/completed/181-slice-studio-m29-physical-evidence-ts.md).
- Old code classification or cleanup: read [engineering/legacy-code-inventory.md](engineering/legacy-code-inventory.md) first; do not delete or revive old directories by default.
- Historical Pencil Python work: read [../archive/legacy-code/services/pencil-python-backend/README.md](../archive/legacy-code/services/pencil-python-backend/README.md) only when explicitly targeting that service.
- Historical Go Draft / Renderer / plugin work: read [architecture/draft-layer-graph.md](architecture/draft-layer-graph.md), [architecture/runtime.md](architecture/runtime.md), [architecture/plugin-rendering.md](architecture/plugin-rendering.md), and create a new active plan before implementation.
- Bugs: read [bugs/index.md](bugs/index.md), the related bug record, and [engineering/validation.md](engineering/validation.md).

## Product

- [product/direction-contract.md](product/direction-contract.md)
- [product/vision.md](product/vision.md)
- [product/requirements.md](product/requirements.md)
- [product/user-flows.md](product/user-flows.md)
- [product/non-goals.md](product/non-goals.md)
- [product/acceptance-criteria.md](product/acceptance-criteria.md)

## Architecture

- [architecture/overview.md](architecture/overview.md)
- [architecture/api-contracts.md](architecture/api-contracts.md)
- [architecture/m29-physical-evidence.md](architecture/m29-physical-evidence.md)
- [architecture/vision-provider.md](architecture/vision-provider.md)
- Historical/deferred: [architecture/runtime.md](architecture/runtime.md), [architecture/draft-layer-graph.md](architecture/draft-layer-graph.md), [architecture/dsl.md](architecture/dsl.md), [architecture/renderer.md](architecture/renderer.md), [architecture/plugin-rendering.md](architecture/plugin-rendering.md)

## Engineering

- [engineering/current-code-map.md](engineering/current-code-map.md)
- [engineering/legacy-code-inventory.md](engineering/legacy-code-inventory.md)
- [engineering/validation.md](engineering/validation.md)
- [engineering/coding-standards.md](engineering/coding-standards.md)
- [engineering/definition-of-done.md](engineering/definition-of-done.md)
- [engineering/dependency-policy.md](engineering/dependency-policy.md)
- [engineering/doc-maintenance.md](engineering/doc-maintenance.md)
- [engineering/anti-specialization.md](engineering/anti-specialization.md)
- [engineering/artifact-policy.md](engineering/artifact-policy.md)

## Plans, Bugs, Decisions

- 当前计划：[plans/active/](plans/active/)
- 已完成计划：[plans/completed/index.md](plans/completed/index.md)
- 已替代计划：[plans/archive/superseded/index.md](plans/archive/superseded/index.md)
- 已暂缓计划：[plans/archive/deferred/index.md](plans/archive/deferred/index.md)
- Bug 索引：[bugs/index.md](bugs/index.md)
- ADR：历史决策记录，不是当前 runtime truth。

## Reference

- 环境变量：[reference/env-vars.md](reference/env-vars.md)
- 前端重做功能清单：[reference/slice-studio-frontend-function-inventory.md](reference/slice-studio-frontend-function-inventory.md)
- AI prompt 策略：[reference/slice-studio-ai-slice-prompt-strategies.md](reference/slice-studio-ai-slice-prompt-strategies.md)
- 外部接口：[reference/external-apis.md](reference/external-apis.md)
- 历史支付候选 reference（非当前 runtime）：[reference/payment-provider-xpay.md](reference/payment-provider-xpay.md)
- 术语表：[reference/glossary.md](reference/glossary.md)
- Codia golden samples：[reference/codia-samples/](reference/codia-samples/)
- 历史草稿：[reference/legacy/index.md](reference/legacy/index.md)

## Runbooks

- [runbooks/local-setup.md](runbooks/local-setup.md)
- [runbooks/slice-studio-production-deploy.md](runbooks/slice-studio-production-deploy.md)
- Historical Pencil Python deployment: [runbooks/pencil-python-backend-handoff.md](runbooks/pencil-python-backend-handoff.md), [runbooks/pencil-python-backend-deploy.md](runbooks/pencil-python-backend-deploy.md)
