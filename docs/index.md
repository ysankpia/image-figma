# 文档地图

本目录是 Image-to-Figma Design 的事实来源。根目录旧草稿已归档到 [reference/legacy/](reference/legacy/index.md)，正式规格以本索引列出的文档为准。

## Start Here

- 项目入口：[../README.md](../README.md)
- Agent 工作规则：[../AGENTS.md](../AGENTS.md)
- 当前文档整理计划：[plans/active/001-doc-harness.md](plans/active/001-doc-harness.md)
- 下一步 MVP 启动计划：[plans/active/002-mvp-bootstrap.md](plans/active/002-mvp-bootstrap.md)
- 当前插件最小闭环计划：[plans/active/003-plugin-minimum-flow.md](plans/active/003-plugin-minimum-flow.md)
- 当前后端假任务流计划：[plans/active/004-backend-fake-task-flow.md](plans/active/004-backend-fake-task-flow.md)
- 当前插件后端上传计划：[plans/active/005-plugin-backend-upload-flow.md](plans/active/005-plugin-backend-upload-flow.md)
- 当前 deterministic PNG -> DSL 计划：[plans/active/006-deterministic-png-to-dsl.md](plans/active/006-deterministic-png-to-dsl.md)
- 当前 deterministic region slicer 计划：[plans/active/007-deterministic-region-slicer.md](plans/active/007-deterministic-region-slicer.md)
- 当前 visual primitive contract 计划：[plans/active/008-visual-primitive-contract-harness.md](plans/active/008-visual-primitive-contract-harness.md)
- 当前 OCR/DSL patch 计划：[plans/active/009-ocr-primitive-dsl-patch-harness.md](plans/active/009-ocr-primitive-dsl-patch-harness.md)
- 当前百度 PP-OCRv5 异步 OCR 计划：[plans/active/010-baidu-ppocrv5-async-ocr-provider.md](plans/active/010-baidu-ppocrv5-async-ocr-provider.md)
- 当前低风险可见文字替换计划：[plans/active/011-low-risk-visible-text-replacement.md](plans/active/011-low-risk-visible-text-replacement.md)
- 当前文字替换覆盖率扩展计划：[plans/active/012-text-replacement-coverage-expansion.md](plans/active/012-text-replacement-coverage-expansion.md)
- 当前文字替换质量控制计划：[plans/active/013-text-replacement-quality-control.md](plans/active/013-text-replacement-quality-control.md)
- 当前 UI-aware 文字采样计划：[plans/active/014-ui-aware-text-replacement-sampling.md](plans/active/014-ui-aware-text-replacement-sampling.md)
- 当前 text-primitive binding 计划：[plans/active/015-text-primitive-binding-harness.md](plans/active/015-text-primitive-binding-harness.md)
- 当前 component structure 计划：[plans/active/016-component-structure-harness.md](plans/active/016-component-structure-harness.md)
- 当前 DSL component annotation 计划：[plans/active/017-dsl-component-annotation-layer-naming.md](plans/active/017-dsl-component-annotation-layer-naming.md)
- 当前 component-aware layer separation candidate 计划：[plans/active/018-component-aware-layer-separation-candidates.md](plans/active/018-component-aware-layer-separation-candidates.md)
- 当前 local asset slice/simple fill 计划：[plans/active/019-local-asset-slice-simple-fill-experiment.md](plans/active/019-local-asset-slice-simple-fill-experiment.md)
- 当前 icon candidate extraction/crop 计划：[plans/active/020-icon-candidate-extraction-crop-harness.md](plans/active/020-icon-candidate-extraction-crop-harness.md)
- 当前 icon coverage audit/placement readiness 计划：[plans/active/021-icon-coverage-audit-placement-readiness.md](plans/active/021-icon-coverage-audit-placement-readiness.md)
- 当前 region-guided icon gap candidate 计划：[plans/active/022-region-guided-icon-gap-candidates.md](plans/active/022-region-guided-icon-gap-candidates.md)
- 当前 icon placement plan/layering readiness 计划：[plans/active/023-icon-placement-plan-layering-readiness.md](plans/active/023-icon-placement-plan-layering-readiness.md)
- 当前 visible icon fallback replay 计划：[plans/active/024-visible-icon-fallback-replay-experiment.md](plans/active/024-visible-icon-fallback-replay-experiment.md)
- 当前 region-guided business icon candidate 计划：[plans/active/025-region-guided-business-icon-candidates.md](plans/active/025-region-guided-business-icon-candidates.md)
- 当前 visual perception provider benchmark 计划：[plans/active/026-visual-perception-provider-benchmark.md](plans/active/026-visual-perception-provider-benchmark.md)
- 当前 SAM2 visual candidate filtering 计划：[plans/active/027-sam2-guided-ui-visual-candidate-filtering.md](plans/active/027-sam2-guided-ui-visual-candidate-filtering.md)
- 当前 single-image SAM2 UI visual extraction 计划：[plans/active/028-single-image-sam2-ui-visual-extraction.md](plans/active/028-single-image-sam2-ui-visual-extraction.md)
- 当前 visual primitive graph 计划：[plans/active/029-visual-primitive-graph-harness.md](plans/active/029-visual-primitive-graph-harness.md)
- 当前 M29 blocked evidence 增强计划：[plans/active/029-0-1-blocked-evidence-enhancement.md](plans/active/029-0-1-blocked-evidence-enhancement.md)
- 当前 M29.1 symbol fragment grouping 计划：[plans/active/029-1-symbol-fragment-grouping.md](plans/active/029-1-symbol-fragment-grouping.md)

## By Task Type

- 做产品范围：读 [product/vision.md](product/vision.md)、[product/requirements.md](product/requirements.md)、[product/non-goals.md](product/non-goals.md)。
- 做用户流程：读 [product/user-flows.md](product/user-flows.md) 和 [architecture/frontend.md](architecture/frontend.md)。
- 做 DSL：读 [architecture/dsl.md](architecture/dsl.md)、[architecture/api-contracts.md](architecture/api-contracts.md)、[decisions/0001-use-dsl-v0.1-as-contract.md](decisions/0001-use-dsl-v0.1-as-contract.md)。
- 做 Renderer：读 [architecture/renderer.md](architecture/renderer.md)、[architecture/dsl.md](architecture/dsl.md)、[decisions/0002-use-fallback-over-perfect-editability.md](decisions/0002-use-fallback-over-perfect-editability.md)。
- 做后端：读 [architecture/backend.md](architecture/backend.md)、[architecture/api-contracts.md](architecture/api-contracts.md)、[architecture/data-model.md](architecture/data-model.md)。
- 做验收：读 [product/acceptance-criteria.md](product/acceptance-criteria.md)、[engineering/testing-strategy.md](engineering/testing-strategy.md)、[engineering/definition-of-done.md](engineering/definition-of-done.md)。
- 做 bug 修复：读 [bugs/index.md](bugs/index.md)、[bugs/template.md](bugs/template.md)、[engineering/testing-strategy.md](engineering/testing-strategy.md)。

## Product

- [product/vision.md](product/vision.md)：产品定位、目标用户、一期成功判断。
- [product/requirements.md](product/requirements.md)：一期 P0 能力。
- [product/user-flows.md](product/user-flows.md)：插件主流程和状态流转。
- [product/non-goals.md](product/non-goals.md)：一期硬性不做事项。
- [product/acceptance-criteria.md](product/acceptance-criteria.md)：P0/P1/P2 验收。

## Architecture

- [architecture/overview.md](architecture/overview.md)：系统总览和模块边界。
- [architecture/dsl.md](architecture/dsl.md)：DSL v0.1 合同。
- [architecture/renderer.md](architecture/renderer.md)：Image-to-Figma Renderer 边界。
- [architecture/frontend.md](architecture/frontend.md)：Figma 插件 UI 与 Main。
- [architecture/backend.md](architecture/backend.md)：后端 API 与处理管线。
- [architecture/api-contracts.md](architecture/api-contracts.md)：API v0.1 合同。
- [architecture/data-model.md](architecture/data-model.md)：SQLite 数据模型。
- [architecture/integrations.md](architecture/integrations.md)：OCR、AI、Figma、存储集成。
- [architecture/security.md](architecture/security.md)：MVP 安全边界。
- [architecture/reliability.md](architecture/reliability.md)：任务状态、失败策略。
- [architecture/observability.md](architecture/observability.md)：日志和调试字段。

## Engineering

- [engineering/coding-standards.md](engineering/coding-standards.md)
- [engineering/testing-strategy.md](engineering/testing-strategy.md)
- [engineering/definition-of-done.md](engineering/definition-of-done.md)
- [engineering/dependency-policy.md](engineering/dependency-policy.md)
- [engineering/browser-validation.md](engineering/browser-validation.md)
- [engineering/ui-guidelines.md](engineering/ui-guidelines.md)
- [engineering/doc-maintenance.md](engineering/doc-maintenance.md)

## Plans, Bugs, And Decisions

- 计划模板：[plans/template.md](plans/template.md)
- 当前计划：[plans/active/](plans/active/)
- 已完成计划：[plans/completed/](plans/completed/)
- ADR 模板：[decisions/adr-template.md](decisions/adr-template.md)
- Monorepo 初始化决策：[decisions/0003-initialize-pnpm-monorepo.md](decisions/0003-initialize-pnpm-monorepo.md)
- Renderer Adapter 决策：[decisions/0004-renderer-uses-figma-adapter.md](decisions/0004-renderer-uses-figma-adapter.md)
- M3 插件 UI 决策：[decisions/0005-use-static-html-for-m3-plugin-ui.md](decisions/0005-use-static-html-for-m3-plugin-ui.md)
- M4 后端决策：[decisions/0006-use-fastapi-sqlite-for-m4-backend.md](decisions/0006-use-fastapi-sqlite-for-m4-backend.md)
- M5 插件后端接入决策：[decisions/0007-plugin-uses-backend-api-after-m4.md](decisions/0007-plugin-uses-backend-api-after-m4.md)
- M6 deterministic DSL 决策：[decisions/0008-use-deterministic-png-dsl-builder-before-ai.md](decisions/0008-use-deterministic-png-dsl-builder-before-ai.md)
- M7 PNG region slicer 决策：[decisions/0009-use-standard-library-png-region-slicer.md](decisions/0009-use-standard-library-png-region-slicer.md)
- M8 visual primitives 决策：[decisions/0010-ai-proposes-visual-primitives-not-dsl.md](decisions/0010-ai-proposes-visual-primitives-not-dsl.md)
- M9 DSL patch 决策：[decisions/0011-use-dsl-patch-builder-before-editable-reconstruction.md](decisions/0011-use-dsl-patch-builder-before-editable-reconstruction.md)
- M10 百度 PP-OCRv5 决策：[decisions/0012-use-baidu-ppocrv5-async-for-real-ocr.md](decisions/0012-use-baidu-ppocrv5-async-for-real-ocr.md)
- M11 低风险文字替换决策：[decisions/0013-use-low-risk-text-replacement-before-full-editable-reconstruction.md](decisions/0013-use-low-risk-text-replacement-before-full-editable-reconstruction.md)
- M12 文字替换覆盖率扩展决策：[decisions/0014-expand-text-replacement-with-color-sampling-before-components.md](decisions/0014-expand-text-replacement-with-color-sampling-before-components.md)
- M12 replacement 上限决策：[decisions/0015-raise-text-replacement-max-blocks-default.md](decisions/0015-raise-text-replacement-max-blocks-default.md)
- M13 文字替换质量门禁决策：[decisions/0016-use-quality-gate-before-formal-text-replacement.md](decisions/0016-use-quality-gate-before-formal-text-replacement.md)
- M14 UI-aware 文字采样决策：[decisions/0017-use-ui-aware-sampling-before-formal-text-reconstruction.md](decisions/0017-use-ui-aware-sampling-before-formal-text-reconstruction.md)
- M15 text-primitive binding 决策：[decisions/0018-bind-text-to-visual-primitives-before-components.md](decisions/0018-bind-text-to-visual-primitives-before-components.md)
- M16 component structure 决策：[decisions/0019-use-component-structure-report-before-dsl-grouping.md](decisions/0019-use-component-structure-report-before-dsl-grouping.md)
- M17 DSL component annotation 决策：[decisions/0020-annotate-dsl-before-slicing-or-componentization.md](decisions/0020-annotate-dsl-before-slicing-or-componentization.md)
- M18 layer separation candidate 决策：[decisions/0021-use-layer-separation-candidates-before-asset-slicing.md](decisions/0021-use-layer-separation-candidates-before-asset-slicing.md)
- M19 local asset slice 决策：[decisions/0022-generate-slice-candidates-before-partial-fallback-replacement.md](decisions/0022-generate-slice-candidates-before-partial-fallback-replacement.md)
- M20 icon candidate 决策：[decisions/0023-crop-icon-candidates-before-visible-partial-replacement.md](decisions/0023-crop-icon-candidates-before-visible-partial-replacement.md)
- M21 icon coverage audit 决策：[decisions/0024-audit-icon-coverage-before-visible-icon-replacement.md](decisions/0024-audit-icon-coverage-before-visible-icon-replacement.md)
- M22 icon gap candidate 决策：[decisions/0025-crop-region-guided-icon-gaps-before-visible-icon-placement.md](decisions/0025-crop-region-guided-icon-gaps-before-visible-icon-placement.md)
- M23 icon placement plan 决策：[decisions/0026-plan-icon-placement-before-visible-icon-layers.md](decisions/0026-plan-icon-placement-before-visible-icon-layers.md)
- M24 visible icon fallback 决策：[decisions/0027-experiment-with-visible-icon-fallback-after-placement-plan.md](decisions/0027-experiment-with-visible-icon-fallback-after-placement-plan.md)
- M25 business icon candidate 决策：[decisions/0028-crop-business-icon-candidates-before-visible-business-icon-replay.md](decisions/0028-crop-business-icon-candidates-before-visible-business-icon-replay.md)
- M26 visual perception benchmark 决策：[decisions/0029-benchmark-visual-perception-providers-before-replacing-rule-probes.md](decisions/0029-benchmark-visual-perception-providers-before-replacing-rule-probes.md)
- M27 SAM2 visual candidate filtering 决策：[decisions/0030-filter-sam2-visual-candidates-before-business-icon-pool-merge.md](decisions/0030-filter-sam2-visual-candidates-before-business-icon-pool-merge.md)
- M28 UI visual extraction 决策：[decisions/0031-extract-ui-visual-objects-before-figma-replay.md](decisions/0031-extract-ui-visual-objects-before-figma-replay.md)
- M29 visual primitive graph 决策：[decisions/0032-build-visual-primitive-graph-before-figma-replay.md](decisions/0032-build-visual-primitive-graph-before-figma-replay.md)
- M29.1 symbol fragment grouping 决策：[decisions/0033-group-symbol-fragments-after-primitive-graph.md](decisions/0033-group-symbol-fragments-after-primitive-graph.md)
- Bug 索引：[bugs/index.md](bugs/index.md)
- Bug 模板：[bugs/template.md](bugs/template.md)

## Runbooks And Reference

- 本地设置：[runbooks/local-setup.md](runbooks/local-setup.md)
- 发布：[runbooks/release.md](runbooks/release.md)
- 事故调试：[runbooks/incident-debugging.md](runbooks/incident-debugging.md)
- 数据库迁移：[runbooks/database-migration.md](runbooks/database-migration.md)
- 环境变量：[reference/env-vars.md](reference/env-vars.md)
- 术语表：[reference/glossary.md](reference/glossary.md)
- 外部接口：[reference/external-apis.md](reference/external-apis.md)
- DevTools MCP：[reference/devtools-mcp.md](reference/devtools-mcp.md)
- 历史草稿：[reference/legacy/index.md](reference/legacy/index.md)
