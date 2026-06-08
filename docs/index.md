# 文档地图

本目录是 Image-to-Figma Design 的事实来源。当前分支的可交付产品主线是 **Pencil Assisted Slice Workspace**：从 1..N 张图片生成自动候选，由用户在 Canvas 工作台确认切片，然后导出 Pencil/Figma 项目包和前端资源包。151 之后新增的 **Pencil Asset Backend** 是更瘦的 image/icon 资产 handoff 路线，默认只交付工程切图 PNG 和单一 `pencil-handoff` `.pen`。旧 Codia Beta、Go Draft `/api/draft-preview`、Python `/api/upload-preview`、历史 ADR、completed plans 和 legacy drafts 只作参考，不能覆盖当前主线。

## Start Here

按顺序阅读：

1. [../AGENTS.md](../AGENTS.md)：仓库规则、当前主线、禁止项。
2. [../services/pencil-python-backend/README.md](../services/pencil-python-backend/README.md)：当前 Pencil assisted slice 服务运行、工作台和验收命令。
3. [../services/pencil-asset-backend/README.md](../services/pencil-asset-backend/README.md)：瘦 image/icon 资产 handoff 服务、单一 `.pen` 输出和验收命令。
4. [reference/pencil-python-backend-api.md](reference/pencil-python-backend-api.md)：当前 HTTP/API 合同。
5. [runbooks/pencil-python-backend-handoff.md](runbooks/pencil-python-backend-handoff.md)：当前交付、验收和部署交接。
6. [runbooks/pencil-python-backend-deploy.md](runbooks/pencil-python-backend-deploy.md)：部署 Runbook。
7. [engineering/current-code-map.md](engineering/current-code-map.md)：当前代码地图。
8. [engineering/legacy-code-inventory.md](engineering/legacy-code-inventory.md)：非主线代码、冷冻资产和可删除产物边界。
9. [engineering/validation.md](engineering/validation.md)：验证策略。
10. [plans/completed/141-pencil-assisted-slice-review-and-export.md](plans/completed/141-pencil-assisted-slice-review-and-export.md)：manual slices 真相源切换。
11. [plans/completed/144-assisted-slice-project-workspace.md](plans/completed/144-assisted-slice-project-workspace.md)：批量项目工作台。
12. [plans/completed/145-assisted-slice-workspace-acceptance-hardening.md](plans/completed/145-assisted-slice-workspace-acceptance-hardening.md)：验收脚本和 ZIP 合同检查。

## Current Runtime

当前主线：

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

瘦资产 handoff 路线：

```text
1..N images
-> services/pencil-asset-backend
-> YOLO/M29/PSD-like/OCR evidence
-> image/icon candidates
-> Canvas Review
-> user-confirmed manual_slices.v1.json
-> PNG assets
-> pencil-handoff project.zip + selected-assets.zip
```

旧路径状态：

- Codia Beta / `Generate Beta`：产品入口已撤掉，只能作为 legacy/eval reference，不再作为新功能落点。
- Go Draft `/api/draft-preview`：历史/延后自动可编辑稿路线，不是当前可交付产品主线。
- Python `/api/upload-preview`：historical/reference preview path，不是 Draft runtime。
- Official Codia JSON：eval/reference/training-label material only，禁止 generation 读取。
- YOLO/M29/PSD-like/foreground ownership 自动裁判：只作为候选、debug、eval 或未来研究输入；不能覆盖 `manual_slices.v1.json`。

## By Task Type

- 做当前产品范围：读 [../services/pencil-python-backend/README.md](../services/pencil-python-backend/README.md)、[reference/pencil-python-backend-api.md](reference/pencil-python-backend-api.md)、[runbooks/pencil-python-backend-handoff.md](runbooks/pencil-python-backend-handoff.md)。
- 做瘦 image/icon 资产 handoff：读 [../services/pencil-asset-backend/README.md](../services/pencil-asset-backend/README.md)、[engineering/current-code-map.md](engineering/current-code-map.md)、[reference/env-vars.md](reference/env-vars.md)。
- 做 assisted slice 工作台/API/导出：读 [engineering/current-code-map.md](engineering/current-code-map.md)、[reference/pencil-python-backend-api.md](reference/pencil-python-backend-api.md)、[reference/env-vars.md](reference/env-vars.md)、[plans/completed/141-pencil-assisted-slice-review-and-export.md](plans/completed/141-pencil-assisted-slice-review-and-export.md)、[plans/completed/144-assisted-slice-project-workspace.md](plans/completed/144-assisted-slice-project-workspace.md)。
- 做部署：读 [runbooks/pencil-python-backend-deploy.md](runbooks/pencil-python-backend-deploy.md) 和 [runbooks/pencil-python-backend-handoff.md](runbooks/pencil-python-backend-handoff.md)。
- 做 Draft graph / Go Draft 历史恢复：读 [architecture/draft-layer-graph.md](architecture/draft-layer-graph.md)、[architecture/runtime.md](architecture/runtime.md) 和 [plans/archive/superseded/093-editable-draft-layer-pipeline-rebuild.md](plans/archive/superseded/093-editable-draft-layer-pipeline-rebuild.md)，并先写新的 active plan。
- 做视觉模型接入实验：读 [architecture/vision-provider.md](architecture/vision-provider.md) 和 [reference/env-vars.md](reference/env-vars.md)，但模型输出不能成为当前 assisted slice 的最终 visible owner。
- 做 M29 物理证据：读 [architecture/m29-physical-evidence.md](architecture/m29-physical-evidence.md)，默认只作为候选/证据输入。
- 判断旧代码能不能删、能不能改、能不能恢复为产品路径：读 [engineering/legacy-code-inventory.md](engineering/legacy-code-inventory.md)。
- 做插件/Renderer：读 [architecture/plugin-rendering.md](architecture/plugin-rendering.md)、[architecture/dsl.md](architecture/dsl.md) 和 [engineering/validation.md](engineering/validation.md)，但它们不是当前 assisted slice 交付路径。
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
- Pencil Python Backend API：[reference/pencil-python-backend-api.md](reference/pencil-python-backend-api.md)
- 外部接口：[reference/external-apis.md](reference/external-apis.md)
- 术语表：[reference/glossary.md](reference/glossary.md)
- Codia golden samples：[reference/codia-samples/](reference/codia-samples/)
- 历史草稿：[reference/legacy/index.md](reference/legacy/index.md)

## Runbooks

- [runbooks/local-setup.md](runbooks/local-setup.md)
- [runbooks/pencil-python-backend-handoff.md](runbooks/pencil-python-backend-handoff.md)
- [runbooks/pencil-python-backend-deploy.md](runbooks/pencil-python-backend-deploy.md)
