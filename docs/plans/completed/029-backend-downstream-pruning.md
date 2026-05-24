# M29 Backend Downstream Pruning

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Summary

本阶段把 backend runtime 从旧下游结构化实验链路中收窄出来，只保留当前可运行、可验证的 M29 证据链和 legacy M30 `/dsl` 出口。

当前保留链路：

```text
upload / OCR / png_tools / storage
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 Direct compare variant
```

同时保留当前 `/api/tasks/{taskId}/dsl` 仍依赖的 legacy bridge：

```text
M29.1
-> M29.0.2 / M29.0.3 / M29.0.7 / M29.0.4 / M29.0.5
-> M30 evidence-grounded materialization
```

## Changes

- 从 `m30_upload_pipeline.py` 移除 M31/M37/M38/M39/M39.1 downstream stages、path fields、imports 和 stage calls。
- 从 runtime config 删除 M31/M38/M39/M39.1/ONNX 相关环境变量。
- 从 task routes 删除 downstream diagnostic endpoints：
  ```text
  GET /api/tasks/{taskId}/m31-reconstruction
  GET /api/tasks/{taskId}/m39-boundary-classification
  GET /api/tasks/{taskId}/m39-1-unit-structure-readiness
  ```
- 删除 downstream/ONNX 模块和测试：
  ```text
  reconstruction_ui_tree.py
  hierarchy_readiness.py
  hierarchy_materialization.py
  content_chrome_classification.py
  unit_structure_readiness.py
  onnx_box_proposer.py
  ```
- 删除不服务当前 M29.5 evidence chain 或 legacy `/dsl` 生存能力的旧 audit 模块、脚本和测试：
  ```text
  pre_ocr_symbol_lineage_audit.py
  member_boundary_quality_audit.py
  residual_mixed_boundary_review.py
  ```
- 保留 `mixed_symbol_text_conflict_audit.py`，因为 M30 materialization 仍使用其中的 contract-term guard。
- 将原 active 的 `039-1-1-unit-candidate-quality-gate.md` 移入 deferred，因为 M39.1 已不再是当前 runtime。
- 更新 AGENTS、architecture、engineering、reference 和 backend README，使它们不再把 M31-M39/M39.1/ONNX 描述为当前 backend 主链。

## Non-Goals

- 不删除 raw M29、M29.2、M29.3、M29.4、M29.5 或 M29 Direct。
- 不删除 `GET /api/tasks/{taskId}/m29-direct-dsl`。
- 不把 `/api/tasks/{taskId}/dsl` 改为 M29.5 plan-driven。
- 不删除 M29.0.2/M29.0.3/M29.0.4/M29.0.5/M29.0.7，因为当前 legacy M30 materialization 仍依赖它们。
- 不删除 `mixed_symbol_text_conflict_audit.py`。
- 不触碰未跟踪的 `docs/architecture/m29-to-codia-math-contract-v0.1.md`。
- 不清理 `backend/storage/` 历史生成产物。

## Validation

计划验证命令：

```bash
cd backend
uv run pytest \
  tests/test_visual_primitive_graph.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_region_relation_kernel.py \
  tests/test_region_relation_graph_report.py \
  tests/test_stable_design_cluster.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_direct_replay.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_routes_tasks.py \
  tests/test_config_env.py \
  tests/test_png_tools.py \
  tests/test_upload_flow.py \
  -q
cd ..
```

静态清理检查：

```bash
rg -n "M31_UPLOAD|M38_HIERARCHY|M39_|m31-reconstruction|m39-boundary-classification|m39-1-unit-structure-readiness" backend/app backend/tests
```

```bash
rg -n "reconstruction_ui_tree|hierarchy_readiness|hierarchy_materialization|content_chrome_classification|unit_structure_readiness|onnx_box_proposer|pre_ocr_symbol_lineage_audit|member_boundary_quality_audit|residual_mixed_boundary_review" backend/app backend/tests backend/scripts
```

```bash
git diff --check
git status --short --branch
```

## Result

当前 backend runtime 不再运行或暴露 M31/M37/M38/M39/M39.1 downstream experiments。后续若要重新做结构化、分组、组件化或 Codia adapter，必须从 M29 source truth 和 M29.5 replay plan 的合同边界重新规划，不能复活旧 downstream 链路作为主线。

验证结果：

```text
181 passed in 30.74s
```

静态清理检查无命中，`git diff --check` 通过。
