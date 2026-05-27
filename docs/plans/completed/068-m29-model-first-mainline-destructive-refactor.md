# 068 M29 Model-First Mainline Destructive Refactor

- 状态：completed
- 创建日期：2026-05-27
- 完成日期：2026-05-27
- 负责人：Codex

## Goal

把 `/api/upload-preview` 默认主链切成 model-first interactive runtime。模型负责发现可疑 UI 对象，OCR 负责文字内容和文字 bbox，M29 负责 source ownership、relation、replay、cleanup 授权和 materializer 执行。

本计划破坏性移除默认交互链路里的旧视觉补救循环：

```text
M29.6 media internal decomposition
-> transparent asset report
-> evidence contract
-> internal source promotion
-> promoted M29.3/M29.4/M29.5 rerun
-> bridge fate trace
```

这些旧 package 可以暂时留在仓库中作为 compat tests 或历史参考，但不能再决定默认 upload-preview 结果。

## Runtime Contract

默认 runtime：

```text
UPLOAD_PREVIEW_RUNTIME_MODE=interactive
```

执行顺序：

```text
POST /api/upload-preview
-> OCR
-> M29 perception model report
-> raw M29 visual primitive fallback
-> M29.2 source ownership
-> perception source compiler
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> ownership conservation
-> hierarchy / sibling / layout / auto-layout reports
-> plan-driven materializer
-> perception fate trace
-> asset publish
-> design.dsl.json
-> GET /api/tasks/{taskId}/dsl
```

`diagnostic` 和 `full` 都不恢复旧 M29.6 loop。它们只在 materialization 之后补充：

```text
design token report
B-stage quality report
DSL visual comparison report/images
```

## Boundaries

不改 public API、DSL schema、Renderer protocol、Figma plugin protocol。

不允许：

```text
model output -> materializer directly
model output -> DSL directly
perception fate trace -> source ownership/replay/cleanup
Renderer/plugin patch source ownership
filename/path/task-id/text/brand/theme/fixed-coordinate/fixed-bbox special cases
```

必须保持：

```text
model proposals -> M29.2 source ownership compiler
M29.5 replay plan -> only visible replay and cleanup authority
materializer -> executor only
perception fate trace -> read-only diagnostic index
```

## Implementation Stages

### Stage A: Runtime Mode Contract

Add `UPLOAD_PREVIEW_RUNTIME_MODE` with values:

```text
interactive
diagnostic
full
```

Invalid or empty values fall back to `interactive`. `UPLOAD_PREVIEW_PROFILE` remains artifact/debug profile only.

### Stage B: Interactive Mainline Slimming

Remove the old visual discovery rescue loop from default pipeline imports and calls. `interactive` emits only model-first/source-chain artifacts needed for Figma preview and debugging.

Required interactive artifacts:

```text
ocr/ocr.json
m29/nodes.json
m29_2/source_ui_physical_graph.json
m29_perception_model/perception_model_report.json
m29_perception_source_compiler/perception_source_compiler_report.json
m29_perception_source_compiler/source_ui_physical_graph.perception.json
m29_3/region_relation_graph_report.json
m29_4/stable_design_cluster_report.json
m29_5/replay_plan.json
m29_ownership_conservation/ownership_conservation_report.json
m29_hierarchy_candidates/hierarchy_candidate_report.json
m29_sibling_groups/sibling_group_candidate_report.json
m29_layout_energy/layout_energy_report.json
m29_auto_layout_permission/auto_layout_permission_report.json
materialized_design/materialization_report.json
materialized_design/design.dsl.json
m29_perception_fate_trace/perception_fate_trace_report.json
stage_timings.json
```

### Stage C: Diagnostic Reports

`diagnostic` and `full` add post-materialization diagnostics without mutating final DSL:

```text
m29_design_tokens/design_token_report.json
m29_b_stage_quality/b_stage_quality_report.json
m29_dsl_visual_comparison/dsl_visual_comparison_report.json
m29_dsl_visual_comparison/dsl_render.png
m29_dsl_visual_comparison/source_diff.png
m29_dsl_visual_comparison/source_gate_diff.png
```

### Stage D: Documentation And Regression Matrix

Update `AGENTS.md`, current mainline map, env vars, testing strategy, and M29 contract matrix so future work debugs through perception fate first and does not wire legacy bridge fate back into default runtime.

### Stage E: Validation

Targeted tests:

```bash
cd backend
uv run pytest tests/test_config_env.py tests/test_upload_preview_pipeline.py tests/test_upload_preview_batch_validation_script.py -q
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_perception_fate_trace.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
```

Real sample validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300
```

Final hygiene:

```bash
git diff --check
git status --short --branch
```

## Acceptance

- Default upload-preview no longer emits M29.6, transparent asset, evidence contract, internal source promotion, bridge fate, or promoted rerun artifacts.
- Default upload-preview still emits final DSL, M29.5 replay plan, materialization report, perception model/compiler reports, perception fate trace, and stage timings.
- Diagnostic/full mode emits design token, B-stage quality, and visual comparison artifacts but does not alter final DSL.
- Batch validation no longer requires legacy visual discovery artifacts in interactive mode.
- Docs and regression matrix describe model-first as active runtime truth.
- No sample-specific hacks or public contract changes.

## Completion Evidence

Targeted tests:

```bash
cd backend
uv run pytest tests/test_config_env.py tests/test_upload_preview_pipeline.py tests/test_upload_preview_batch_validation_script.py -q
# 29 passed

uv run pytest tests/test_perception_source_compiler.py tests/test_m29_perception_fate_trace.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
# 94 passed
```

Real sample interactive validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300
```

Result:

```text
inputCount=16
completedTaskCount=16
failedTaskCount=0
backendCrashCount=0
missingArtifactCount=0
assetFetchFailedCount=0
totalPerceptionCandidateCount=931
totalCompiledSourceObjectCount=138
totalMaterializedVisibleNodeCount=1930
```

Diagnostic smoke:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --runtime-mode diagnostic \
  --max-files 1 \
  --poll-timeout 300
```

Result:

```text
completedTaskCount=1
missingArtifactCount=0
totalDesignTokenCandidateCount=139
averageDslVisualNormalizedMeanAbsError=0.039744
```
