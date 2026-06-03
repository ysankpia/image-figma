# 文档地图

本目录是 Image-to-Figma Design 的事实来源。当前分支的产品主线是 **Editable Draft Layer Pipeline**：从 PNG 生成可编辑 Figma 草稿。旧 Codia Beta、Python `/api/upload-preview`、历史 ADR、completed plans 和 legacy drafts 只作参考，不能覆盖当前主线。

## Start Here

按顺序阅读：

1. [../AGENTS.md](../AGENTS.md)：仓库规则、当前主线、禁止项。
2. [product/vision.md](product/vision.md)：产品目标。
3. [architecture/overview.md](architecture/overview.md)：系统边界总览。
4. [architecture/runtime.md](architecture/runtime.md)：Draft runtime 链路。
5. [architecture/draft-layer-graph.md](architecture/draft-layer-graph.md)：`editable_layer_graph.v1` 合同。
6. [architecture/vision-provider.md](architecture/vision-provider.md)：OpenAI-compatible 视觉候选与 review 边界。
7. [architecture/m29-physical-evidence.md](architecture/m29-physical-evidence.md)：M29 物理证据职责。
8. [engineering/current-code-map.md](engineering/current-code-map.md)：当前代码地图。
9. [engineering/validation.md](engineering/validation.md)：验证策略。
10. [plans/active/093-editable-draft-layer-pipeline-rebuild.md](plans/active/093-editable-draft-layer-pipeline-rebuild.md)：当前破坏性重构计划。

## Current Runtime

当前主线：

```text
Figma Plugin
-> POST /api/draft-preview
-> Go backend services/backend-go
-> OCR
-> M29 physical evidence
-> optional vision detector
-> optional vision review
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

旧路径状态：

- Codia Beta / `Generate Beta`：产品入口已撤掉，只能作为 legacy/eval reference，不再作为新功能落点。
- Python `/api/upload-preview`：historical/reference preview path，不是 Draft runtime。
- Official Codia JSON：eval/reference/training-label material only，禁止 generation 读取。

## By Task Type

- 做产品范围：读 [product/vision.md](product/vision.md)、[product/requirements.md](product/requirements.md)、[product/non-goals.md](product/non-goals.md)、[product/acceptance-criteria.md](product/acceptance-criteria.md)。
- 做 Draft graph：读 [architecture/draft-layer-graph.md](architecture/draft-layer-graph.md) 和 [engineering/validation.md](engineering/validation.md)。
- 做 Go 后端：读 [architecture/runtime.md](architecture/runtime.md)、[engineering/current-code-map.md](engineering/current-code-map.md) 和当前 active plan。
- 做视觉模型接入：读 [architecture/vision-provider.md](architecture/vision-provider.md) 和 [reference/env-vars.md](reference/env-vars.md)。
- 做 M29 物理证据：读 [architecture/m29-physical-evidence.md](architecture/m29-physical-evidence.md)。
- 做 Pencil `.pen` 项目导出、调用或部署：读 [engineering/current-code-map.md](engineering/current-code-map.md)、[reference/pencil-python-backend-api.md](reference/pencil-python-backend-api.md)、[reference/env-vars.md](reference/env-vars.md) 和 [runbooks/pencil-python-backend-deploy.md](runbooks/pencil-python-backend-deploy.md)。
- 做插件/Renderer：读 [architecture/plugin-rendering.md](architecture/plugin-rendering.md)、[architecture/dsl.md](architecture/dsl.md) 和 [engineering/validation.md](engineering/validation.md)。
- 做 bug 修复：读 [bugs/index.md](bugs/index.md)、相关 bug record 和 [engineering/validation.md](engineering/validation.md)。
- 做历史对比：读 [reference/codia-samples/](reference/codia-samples/) 和 `internal/eval/codia`，不要把 eval 数据接入 generation。

## Product

- [product/vision.md](product/vision.md)
- [product/requirements.md](product/requirements.md)
- [product/user-flows.md](product/user-flows.md)
- [product/non-goals.md](product/non-goals.md)
- [product/acceptance-criteria.md](product/acceptance-criteria.md)

## Architecture

- [architecture/overview.md](architecture/overview.md)
- [architecture/runtime.md](architecture/runtime.md)
- [architecture/draft-layer-graph.md](architecture/draft-layer-graph.md)
- [architecture/api-contracts.md](architecture/api-contracts.md)
- [architecture/dsl.md](architecture/dsl.md)
- [architecture/renderer.md](architecture/renderer.md)
- [architecture/plugin-rendering.md](architecture/plugin-rendering.md)
- [architecture/vision-provider.md](architecture/vision-provider.md)
- [architecture/m29-physical-evidence.md](architecture/m29-physical-evidence.md)
- [architecture/security.md](architecture/security.md)
- [architecture/reliability.md](architecture/reliability.md)
- [architecture/observability.md](architecture/observability.md)

## Engineering

- [engineering/current-code-map.md](engineering/current-code-map.md)
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
- Pencil Python Backend API：[reference/pencil-python-backend-api.md](reference/pencil-python-backend-api.md)
- 外部接口：[reference/external-apis.md](reference/external-apis.md)
- 术语表：[reference/glossary.md](reference/glossary.md)
- Codia golden samples：[reference/codia-samples/](reference/codia-samples/)
- 历史草稿：[reference/legacy/index.md](reference/legacy/index.md)

## Runbooks

- [runbooks/local-setup.md](runbooks/local-setup.md)
- [runbooks/pencil-python-backend-handoff.md](runbooks/pencil-python-backend-handoff.md)
- [runbooks/pencil-python-backend-deploy.md](runbooks/pencil-python-backend-deploy.md)
