# Claude Code M29 Model-First Review Prompt

Use this prompt with Claude Code to run a fresh read-only code audit of the current `image-figma` repository. The output should be written into repository documentation, not kept only in chat.

```text
你是 Claude Code。请对当前仓库做一次只读代码审核，不要直接修改 runtime 代码，除非我后续明确要求你开始修复。

仓库路径：

/Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma

核心目标：

用第一性原理重新审核当前 M29 model-first 主链，确认从图片上传到 Figma DSL 输出的 source truth、ownership、replay、cleanup、materializer 边界是否正确。重点不是找漂亮建议，而是找真实代码事实、架构错位、隐性特化、旧链路残留和会导致“识别到了但 Figma 里不可选”的断点。

必须先阅读这些文件：

1. AGENTS.md
2. CLAUDE.md
3. docs/index.md
4. docs/engineering/current-mainline-code-map.md
5. docs/engineering/m29-contract-regression-matrix.md
6. docs/engineering/testing-strategy.md
7. docs/plans/completed/068-m29-model-first-mainline-destructive-refactor.md
8. docs/bugs/index.md
9. docs/bugs/resolved/020-multi-item-navigation-container-becomes-raster-owner.md
10. docs/code-reviews/m29-first-principles-source-chain-audit/README.md
11. docs/code-reviews-gemini/README.md

当前有效主链必须以代码和文档共同核实。预期主链是：

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

旧链路不是 active mainline：

M29.6 -> transparent asset -> evidence contract -> internal source promotion -> promoted rerun

这些旧模块如果存在，只能作为 legacy / diagnostic / archival reference。请检查它们是否被默认 upload-preview runtime 路径重新接回。如果接回，这是 P0。

审计原则：

1. 只相信当前代码、当前文档、当前测试、当前 artifact。不要依赖聊天历史。
2. 不要把旧 ADR、旧 active plan、legacy draft 当成当前 runtime truth。
3. 不要按文件名、任务 id、文案、品牌、主题色、固定坐标、固定 bbox 判断对错。
4. 不要建议在 Renderer、Figma plugin、materializer 里补 source owner。
5. source ownership 缺陷只能回到 raw M29、M29.2 或 perception_source_compiler 修。
6. M29.5 replay plan 是 visible replay、dedupe、cleanup authorization 的唯一权限来源。
7. materializer 只能执行 M29.5，不得发明 owner、cleanup、button、icon、tab、marker。
8. perception model report 是候选发现，不是 source truth；perception source compiler 才是进入 M29.2 ownership 的桥。
9. perception fate trace 是只读诊断，不得参与决策。
10. C-stage 结构报告只能围绕已 replay 节点生成透明 controlled groups，不能创建新的可见 owner。

请按第一性原理审核这些问题：

1. 当前 `backend/app/upload_preview/pipeline.py` 是否真的执行 model-first interactive 主链？
2. `UPLOAD_PREVIEW_RUNTIME_MODE`、`UPLOAD_PREVIEW_PROFILE`、`M29_PERCEPTION_MODEL_ENABLED` 的职责是否清楚？是否存在 profile 和 runtime mode 混用？
3. perception model report 是否保持 report-only？有没有直接创建 DSL、asset、cleanup 或 replay authorization？
4. `perception_source_compiler` 是否只把模型候选编译成 M29.2 source objects？有没有越权 materialize？
5. raw M29 和 M29.2 是否仍存在低置信 media/container 吞掉内部 foreground 的路径？
6. 是否还有类似 bottom tab、toolbar、action row、多 item 容器被整条 raster owner 压住内部 icon/text 的风险？
7. M29.5 dedupe / overlap suppression 是否会误删真实相邻小图标、tab marker、status dot、table marker？
8. cleanup targets 是否只来自 M29.5？cleanup 风险失败时，是否会错误取消 visible replay？
9. ownership conservation、hierarchy、sibling、layout energy、auto-layout permission、perception fate trace 是否仍是 report/permission/diagnostic surface，没有反向污染 source truth？
10. materializer 是否严格消费 M29.5 plan？是否存在根据颜色、角色名、bbox、asset url、文件名自行补节点或擦图的逻辑？
11. public API、DSL schema、Renderer protocol、Figma plugin protocol 是否保持稳定？
12. 近期 bug 020 的修复是否泛化合理？有没有误杀普通复杂按钮或单个大控件的风险？
13. docs 和代码是否一致？哪些 active plans 已经过期但仍可能误导后续 agent？
14. 测试是否覆盖当前真实主链？有没有测试还在默认保护 legacy M29.6 / promotion loop？

重点代码入口：

backend/app/config.py
backend/app/routes/upload_preview.py
backend/app/upload_preview/pipeline.py
backend/app/perception_model_report/
backend/app/perception_source_compiler/
backend/app/source_ui_physical_graph/
backend/app/region_relation_graph_report/
backend/app/stable_design_cluster/
backend/app/m29_replay_plan/
backend/app/ownership_conservation/
backend/app/hierarchy_candidate_report/
backend/app/sibling_group_candidate_report/
backend/app/layout_energy_report/
backend/app/auto_layout_permission_report/
backend/app/plan_materializer/
backend/app/m29_perception_fate_trace/
packages/dsl-schema/
packages/image-to-figma-renderer/
figma-plugin/
backend/tests/

参考但不要让它们覆盖当前 truth：

docs/code-reviews/m29-first-principles-source-chain-audit/
docs/code-reviews-gemini/
docs/plans/active/
docs/plans/archive/
docs/reference/legacy/
backend/app/media_internal_decomposition/
backend/app/transparent_asset_report/
backend/app/internal_source_promotion/

输出位置：

请创建或更新以下目录，不要把正式审核结论写到 Gemini 目录，也不要覆盖既有 Codex 审计目录：

docs/code-reviews-claude/m29-model-first-mainline-audit/

请输出这些文件：

README.md
00-current-runtime-chain.md
01-source-ownership-and-perception-compiler.md
02-replay-cleanup-materializer-boundaries.md
03-report-and-diagnostic-surfaces.md
04-legacy-path-and-stale-doc-inventory.md
05-specialization-and-heuristic-risk-ledger.md
06-test-coverage-and-real-sample-validation-gaps.md
07-prioritized-findings-and-fix-plan.md

每个 finding 必须分级：

P0 = active runtime 架构越权，可能破坏 source truth / public contract / cleanup authorization。
P1 = source-chain correctness defect，会导致真实 UI 对象识别到了但不可选、被 suppress、被大图吞掉或被错误 cleanup。
P2 = evidence quality / test coverage gap，当前可用但容易回归或泛化不足。
P3 = docs / legacy / cleanup debt，不直接破坏 runtime 但会误导后续维护。

每条 finding 必须包含：

- Severity
- Fact: 代码路径、函数名、测试名、artifact 路径或文档路径。必须可核查。
- Inference: 从事实推出的问题。
- Risk: 会造成什么用户可见失败。
- Recommendation: 应该在哪一层修，不能建议下游补丁。
- Regression Guard: 应加或应运行的测试。

强制输出规则：

1. 不要只输出泛泛总结。
2. 不要用“可能”“应该”替代代码事实；不确定的地方标成 Risk 或 Open Question。
3. 不要建议恢复 legacy M29.6 -> transparent -> evidence -> promotion -> rerun 作为默认主链。
4. 不要建议把 materializer / Renderer / plugin 变成 source owner 修复层。
5. 不要建议按单张图、固定 bbox、颜色、品牌、文案、文件名修。
6. 如果发现没有问题，也要说明你检查过哪些代码路径和测试。
7. 最后必须给出一个按顺序执行的 fix plan；如果没有 P0/P1，就给出 cleanup / test hardening plan。

建议运行的只读/轻量命令：

git status --short --branch
git log --oneline -5
git diff --check
rg -n "media_internal_decomposition|transparent_asset|internal_source_promotion|bridge_fate" backend/app backend/tests docs
rg -n "materializer|cleanupTargets|sourceObjectId|replayDecision|pixelOwner|perception_fate" backend/app backend/tests
cd backend && uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py -q

如果你要做真实样本验证，先只读现有 artifact；不要删除 storage，不要重启后端，不要改数据库。需要新上传或长批量时，先在报告里说明目的和命令，不要自动执行。

验收标准：

1. `docs/code-reviews-claude/m29-model-first-mainline-audit/` 下的报告完整。
2. 报告能回答：当前 model-first 主链是否干净；旧视觉发现链是否还影响默认结果；source ownership、M29.5、materializer 是否越权；为何 bottom tab/按钮/icon 这类问题应该在哪层修。
3. 每个高优 finding 都能落到具体代码事实。
4. 不产生 runtime 行为改动。
```
