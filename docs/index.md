# 文档地图

本目录是 Image-to-Figma Design 的事实来源。根目录旧草稿已归档到 [reference/legacy/](reference/legacy/index.md)，正式规格以本索引列出的文档为准。

## Start Here

- 项目入口：[../README.md](../README.md)
- Agent 工作规则：[../AGENTS.md](../AGENTS.md)
- 当前项目演进路线图：[roadmap.md](roadmap.md)
- 当前主链架构入口：[architecture/backend.md](architecture/backend.md)
- 当前主线代码地图：[engineering/current-mainline-code-map.md](engineering/current-mainline-code-map.md)
- M29 数学合同：[architecture/m29-experimental-mathematical-contract.md](architecture/m29-experimental-mathematical-contract.md)
- M29 入门数学推演：[architecture/m29-math-from-first-principles.md](architecture/m29-math-from-first-principles.md)
- M29 之后 Codia 级数学草案：[architecture/m29-to-codia-math-contract-v0.1.md](architecture/m29-to-codia-math-contract-v0.1.md)
- 全链路第一性原理本地核对：[reference/full-chain-first-principles-local-audit.md](reference/full-chain-first-principles-local-audit.md)
- M29 contract regression matrix：[engineering/m29-contract-regression-matrix.md](engineering/m29-contract-regression-matrix.md)
- 测试策略：[engineering/testing-strategy.md](engineering/testing-strategy.md)
- 当前 active plan：[plans/active/056-m29-525-real-sample-batch-hardening.md](plans/active/056-m29-525-real-sample-batch-hardening.md)；最近完成计划见 [plans/completed/054-m29-media-internal-decomposition-and-transparent-assets.md](plans/completed/054-m29-media-internal-decomposition-and-transparent-assets.md)。

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
- [architecture/m29-experimental-mathematical-contract.md](architecture/m29-experimental-mathematical-contract.md)：M29 主链的 bbox、ownership、relation、cluster、replay plan 和 plan-driven materialization 数学合同。
- [architecture/m29-math-from-first-principles.md](architecture/m29-math-from-first-principles.md)：面向初中数学基础读者的 M29 bbox、pixelOwner、region relation、cluster 和 replay plan 推演。
- [architecture/m29-to-codia-math-contract-v0.1.md](architecture/m29-to-codia-math-contract-v0.1.md)：M29 之后 hierarchy、layout、component、token、vectorization、materialization 和 quality metrics 的未来数学草案；不是当前 runtime 合同。
- [architecture/api-contracts.md](architecture/api-contracts.md)：API v0.1 合同。
- [architecture/data-model.md](architecture/data-model.md)：SQLite 数据模型。
- [architecture/integrations.md](architecture/integrations.md)：OCR、AI、Figma、存储集成。
- [architecture/security.md](architecture/security.md)：MVP 安全边界。
- [architecture/reliability.md](architecture/reliability.md)：任务状态、失败策略。
- [architecture/observability.md](architecture/observability.md)：日志和调试字段。

## Engineering

- [engineering/coding-standards.md](engineering/coding-standards.md)
- [engineering/testing-strategy.md](engineering/testing-strategy.md)
- [engineering/current-mainline-code-map.md](engineering/current-mainline-code-map.md)
- [engineering/m29-contract-regression-matrix.md](engineering/m29-contract-regression-matrix.md)
- [engineering/definition-of-done.md](engineering/definition-of-done.md)
- [engineering/dependency-policy.md](engineering/dependency-policy.md)
- [engineering/browser-validation.md](engineering/browser-validation.md)
- [engineering/ui-guidelines.md](engineering/ui-guidelines.md)
- [engineering/doc-maintenance.md](engineering/doc-maintenance.md)

## Plans, Bugs, And Decisions

- 计划模板：[plans/template.md](plans/template.md)
- 当前计划：[plans/active/](plans/active/)
- 已完成计划：[plans/completed/index.md](plans/completed/index.md)
- 已替代计划：[plans/archive/superseded/index.md](plans/archive/superseded/index.md)
- 已暂缓计划：[plans/archive/deferred/index.md](plans/archive/deferred/index.md)
- Pre-M29 历史实验计划归档：[plans/archive/pre_m29/](plans/archive/pre_m29/)
- ADR 是历史决策记录，不等于全部仍是 active runtime。M31-M39/M39.1 相关 ADR 当前仅作历史追溯。
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
- M29 direct replay 分支实验决策：[decisions/0065-test-m29-direct-replay-before-more-unit-promotion.md](decisions/0065-test-m29-direct-replay-before-more-unit-promotion.md)
- M29 direct replay Figma 对比决策：[decisions/0066-render-m29-direct-and-mainline-side-by-side-in-figma.md](decisions/0066-render-m29-direct-and-mainline-side-by-side-in-figma.md)
- M29.2 source pixel ownership 决策：[decisions/0067-solve-pixel-ownership-at-m29-source-layer.md](decisions/0067-solve-pixel-ownership-at-m29-source-layer.md)
- M29 pixel topology and ownership graph 决策：[decisions/0068-treat-m29-as-pixel-topology-and-ownership-graph.md](decisions/0068-treat-m29-as-pixel-topology-and-ownership-graph.md)
- Componentization on set-relation graph isomorphism 决策：[decisions/0069-base-componentization-on-set-relation-graph-isomorphism.md](decisions/0069-base-componentization-on-set-relation-graph-isomorphism.md)
- M29 region relation before clustering 决策：[decisions/0070-define-m29-region-relation-before-clustering.md](decisions/0070-define-m29-region-relation-before-clustering.md)
- M29 pixel ownership decision 决策：[decisions/0071-define-m29-pixel-ownership-decision.md](decisions/0071-define-m29-pixel-ownership-decision.md)
- M29 replay plan quality gate 决策：[decisions/0072-use-replay-plan-as-m29-direct-quality-gate.md](decisions/0072-use-replay-plan-as-m29-direct-quality-gate.md)
- M29 shape geometry fitting 决策：[decisions/0073-require-shape-geometry-fitting-before-radius-replay.md](decisions/0073-require-shape-geometry-fitting-before-radius-replay.md)
- M29.1 symbol fragment grouping 决策：[decisions/0033-group-symbol-fragments-after-primitive-graph.md](decisions/0033-group-symbol-fragments-after-primitive-graph.md)
- M29.0.2 text mask media audit 决策：[decisions/0034-use-text-mask-before-media-recovery.md](decisions/0034-use-text-mask-before-media-recovery.md)
- M29.0.3 visual evidence normalization 决策：[decisions/0035-normalize-visual-evidence-after-text-mask.md](decisions/0035-normalize-visual-evidence-after-text-mask.md)
- M29.0.4 generic visual object candidate 决策：[decisions/0036-generic-visual-object-candidates-after-evidence-normalization.md](decisions/0036-generic-visual-object-candidates-after-evidence-normalization.md)
- M29.0.5 text-aware visual object refinement 决策：[decisions/0037-refine-visual-objects-into-text-and-visual-members.md](decisions/0037-refine-visual-objects-into-text-and-visual-members.md)
- M29.0.6 member boundary quality audit 决策：[decisions/0038-audit-member-boundary-quality-after-text-aware-refinement.md](decisions/0038-audit-member-boundary-quality-after-text-aware-refinement.md)
- M29.0.7 text ownership gate 决策：[decisions/0039-route-text-owned-evidence-before-object-graph.md](decisions/0039-route-text-owned-evidence-before-object-graph.md)
- M29 pre-OCR symbol lineage 决策：[decisions/0040-preserve-pre-ocr-symbol-lineage-through-text-overlap.md](decisions/0040-preserve-pre-ocr-symbol-lineage-through-text-overlap.md)
- M29.1.3 mixed conflict classification 决策：[decisions/0041-classify-mixed-symbol-text-conflicts-before-promotion.md](decisions/0041-classify-mixed-symbol-text-conflicts-before-promotion.md)
- M29.0.3.1 text-like lineage rejection 决策：[decisions/0042-reject-text-like-lineage-before-mixed-conflict.md](decisions/0042-reject-text-like-lineage-before-mixed-conflict.md)
- M29.0.3.2 residual mixed boundary review 决策：[decisions/0043-review-residual-mixed-before-promotion.md](decisions/0043-review-residual-mixed-before-promotion.md)
- M30 evidence-grounded DSL materialization 决策：[decisions/0044-materialize-trusted-m29-evidence-into-existing-dsl.md](decisions/0044-materialize-trusted-m29-evidence-into-existing-dsl.md)
- M30.1 plugin M29-to-M30 upload preview 决策：[decisions/0045-route-plugin-upload-through-m29-m30-preview-pipeline.md](decisions/0045-route-plugin-upload-through-m29-m30-preview-pipeline.md)
- M30.2 conservative text cover 决策：[decisions/0046-use-conservative-text-cover-before-fallback-masking.md](decisions/0046-use-conservative-text-cover-before-fallback-masking.md)
- M30.2.1 pre-M29 legacy upload surface freeze 决策，已被 0048 取代：[decisions/0047-freeze-pre-m29-legacy-upload-surface.md](decisions/0047-freeze-pre-m29-legacy-upload-surface.md)
- M30.2.2 remove frozen pre-M29 backend chain 决策：[decisions/0048-remove-frozen-pre-m29-legacy-backend-chain.md](decisions/0048-remove-frozen-pre-m29-legacy-backend-chain.md)
- M31 reconstruction UI tree 决策：[decisions/0049-build-reconstruction-ui-tree-from-m29-primitive-evidence.md](decisions/0049-build-reconstruction-ui-tree-from-m29-primitive-evidence.md)
- M31.1 upload diagnostics 决策：[decisions/0050-attach-m31-diagnostics-to-upload-pipeline-before-layer-recovery.md](decisions/0050-attach-m31-diagnostics-to-upload-pipeline-before-layer-recovery.md)
- M31.1.1 decoded-pixels fallback crop 决策：[decisions/0051-crop-m31-fallbacks-from-decoded-pixels.md](decisions/0051-crop-m31-fallbacks-from-decoded-pixels.md)
- M34.1 OCR text evidence preservation 决策：[decisions/0052-preserve-ocr-text-evidence-before-materialization-decision.md](decisions/0052-preserve-ocr-text-evidence-before-materialization-decision.md)
- M34.2 context-aware UI text editability 决策：[decisions/0053-context-aware-ui-text-editability-with-generic-geometry.md](decisions/0053-context-aware-ui-text-editability-with-generic-geometry.md)
- M34.3 text-symbol leakage cleanup 决策：[decisions/0057-clean-text-symbol-leakage-with-projection-gap-before-materialization.md](decisions/0057-clean-text-symbol-leakage-with-projection-gap-before-materialization.md)
- M36 text foreground color sampling 决策：[decisions/0054-sample-text-foreground-color-from-source-pixels.md](decisions/0054-sample-text-foreground-color-from-source-pixels.md)
- M37 hierarchy readiness 决策：[decisions/0055-audit-hierarchy-readiness-before-nested-dsl-output.md](decisions/0055-audit-hierarchy-readiness-before-nested-dsl-output.md)
- M38 hierarchy materialization 决策：[decisions/0058-materialize-safe-hierarchy-containers-after-readiness-audit.md](decisions/0058-materialize-safe-hierarchy-containers-after-readiness-audit.md)
- M30.6 accepted image materialization 决策：[decisions/0059-materialize-low-text-overlap-accepted-images-before-hierarchy.md](decisions/0059-materialize-low-text-overlap-accepted-images-before-hierarchy.md)
- M30.7 raster pixel deduplication 决策：[decisions/0060-deduplicate-raster-pixels-after-media-materialization.md](decisions/0060-deduplicate-raster-pixels-after-media-materialization.md)
- M36.1 contrast-weighted foreground sampling 决策：[decisions/0056-weight-text-foreground-sampling-by-contrast-not-count.md](decisions/0056-weight-text-foreground-sampling-by-contrast-not-count.md)
- M39 content-chrome boundary classification 决策：[decisions/0061-content-chrome-boundary-classification.md](decisions/0061-content-chrome-boundary-classification.md)
- M40 nested hierarchy materialization 决策：[decisions/0062-nested-hierarchy-materialization.md](decisions/0062-nested-hierarchy-materialization.md)
- M39.1 unit structure readiness audit 决策：[decisions/0063-audit-unit-structure-readiness-before-unit-promotion.md](decisions/0063-audit-unit-structure-readiness-before-unit-promotion.md)
- M39.1.1/M39.2/M40/M41 阶段顺序决策：[decisions/0064-gate-unit-candidates-before-promotion-and-componentization.md](decisions/0064-gate-unit-candidates-before-promotion-and-componentization.md)
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
- Agent guidelines 中文参考快照：[reference/agent-guidelines.zh-CN.md](reference/agent-guidelines.zh-CN.md)
- 全链路第一性原理本地核对：[reference/full-chain-first-principles-local-audit.md](reference/full-chain-first-principles-local-audit.md)
- 历史草稿：[reference/legacy/index.md](reference/legacy/index.md)
- Pre-M29 归档清单：[reference/legacy/pre-m29-archive-inventory.md](reference/legacy/pre-m29-archive-inventory.md)
