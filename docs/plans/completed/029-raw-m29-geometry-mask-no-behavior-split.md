# M29 Raw Geometry/Mask No-Behavior Split

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Goal

把 raw M29 primitive graph 的低风险基础层从 `backend/app/visual_primitive_graph.py` 拆到 `backend/app/visual_primitive/` package，为后续拆 support detectors、geometry fit、primitive detectors 和 artifact writers 建立稳定地基。

本阶段只做无行为变化拆分，不改 raw M29 输出 JSON、不改 primitive ID、不改 bbox/metrics/mask 计算、不改 detector 阈值、不改 asset path、不改 upload pipeline。

## Changes

- 新增 `backend/app/visual_primitive/` package。
- 拆出基础模块：
  ```text
  types.py: M29 raw primitive dataclasses, Literal contracts, constants
  bbox.py: bbox math, containment, intersection, union, padding, clamp
  mask.py: binary mask construction, union/subtract, bbox overlap, validation, mask PNG export
  metrics.py: region metrics, metric serialization, color helpers, numeric clamp
  pixels.py: pixel crop, region/ring sampling, debug rectangle drawing
  ```
- `backend/app/visual_primitive_graph.py` 继续保留 `extract_m29_visual_primitive_graph`、detectors、support 背景、geometry fit、asset/debug、validation 等逻辑。
- `backend/app/visual_primitive_graph.py` 继续 re-export 外部调用方已经依赖的 M29 类型和基础函数，避免一次性修改 legacy imports。
- 更新 `docs/engineering/current-mainline-code-map.md`，标明基础层和 detector orchestration 的当前边界。

## Non-Goals

- 不拆 `extract_m29_visual_primitive_graph`。
- 不拆 `build_text_nodes`、`connected_components`、`detect_shapes`、`detect_low_contrast_support_regions`、`detect_text_support_background_regions`、`detect_images`、`detect_symbols`。
- 不拆 `build_containment_relations`、`export_node_assets`、`write_debug_overlays`、`validate_m29_document`。
- 不拆 `fit_connected_component_geometry` 或 `fit_low_contrast_support_geometry`。
- 不调整任何 detector 阈值、owner/replay/materialization 规则或 upload pipeline。

## Acceptance

- raw M29 focused tests 通过。
- current/legacy raw M29 dependency tests 通过。
- 后端全量测试通过。
- 前端/plugin test、typecheck、build 通过。
- `visual_primitive_graph.py` 行数明显下降。
- `backend/app/visual_primitive/*.py` 每个文件低于约 350 行。
- 无旧 M30 upload product surface 残留。

## Validation

阶段回归命令：

```bash
cd backend
uv run pytest tests/test_visual_primitive_graph.py -q
uv run pytest \
  tests/test_source_ui_physical_graph.py \
  tests/test_text_masked_media_audit.py \
  tests/test_symbol_fragment_grouping.py \
  tests/test_visual_evidence_normalization.py \
  tests/test_visual_object_candidate_audit.py \
  tests/test_text_aware_visual_object_refinement.py \
  tests/test_text_visual_ownership_gate.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  -q
uv run pytest -q
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
```

静态检查：

```bash
wc -l backend/app/visual_primitive/*.py backend/app/visual_primitive_graph.py
rg -n "upload-m30-preview|m30_upload_pipeline" backend/app backend/tests figma-plugin/src
```
