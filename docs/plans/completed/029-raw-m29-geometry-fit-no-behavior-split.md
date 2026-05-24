# M29 Raw Geometry Fit No-Behavior Split

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Goal

把 raw M29 primitive graph 的 shape geometry fit 层迁入 `backend/app/visual_primitive/geometry.py`，继续降低 `backend/app/visual_primitive_graph.py` 的职责密度。

本阶段只做无行为变化拆分，不改 raw M29 输出 JSON、不改 primitive ID、不改 detector 阈值、不改 bbox/mask/metrics 算法、不改 asset path、不改 upload pipeline。

## Changes

- 新增 `backend/app/visual_primitive/geometry.py`。
- 迁移 shape geometry fit 和本地 geometry helper：
  ```text
  is_line_like
  is_rect_like
  fit_connected_component_geometry
  fit_low_contrast_support_geometry
  shape_geometry
  geometry_radius
  local_mask_occupancy
  local_mask_edge_occupancy
  support_fill_occupancy
  estimate_support_radius_from_occupancy
  clamp_local_bbox
  local_bbox_contains
  local_intersection_bbox
  rect_subtype
  shape_layer_hint
  ```
- 迁移 `support_region_metrics`，作为 geometry/support 共用的 metric helper，避免 `geometry.py` 反向 import `visual_primitive_graph.py`。
- `backend/app/visual_primitive_graph.py` 继续保留 detector orchestration、support detector、primitive detector、artifact 和 validation 逻辑，并通过 import 继续 re-export 旧调用方依赖的 geometry 符号。
- 更新 `docs/engineering/current-mainline-code-map.md` 和 completed plan index。

## Non-Goals

- 不拆 support detector 的 detect/find/score 函数。
- 不拆 text/shape/image/symbol primitive detectors。
- 不拆 connected components、artifact writers、validation。
- 不调整 tests 的行为断言，不引入新 threshold、theme rule、bbox 特判或 fallback 规则。

## Acceptance

- `tests/test_visual_primitive_graph.py` 通过。
- raw M29 geometry 依赖的主链测试通过。
- 后端全量测试通过。
- 前端/plugin test、typecheck、build 通过。
- `visual_primitive/geometry.py` 低于约 350 行。
- `visual_primitive_graph.py` 不再定义 geometry fit 函数，只 re-export。
- 无旧 M30 upload product surface 残留。

## Validation

阶段回归命令：

```bash
cd backend
uv run pytest tests/test_visual_primitive_graph.py -q
uv run pytest \
  tests/test_source_ui_physical_graph.py \
  tests/test_m29_replay_plan.py \
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
rg -n "^def (is_line_like|is_rect_like|fit_connected_component_geometry|fit_low_contrast_support_geometry|shape_geometry|geometry_radius|local_mask_occupancy|local_mask_edge_occupancy|support_fill_occupancy|estimate_support_radius_from_occupancy|clamp_local_bbox|local_bbox_contains|local_intersection_bbox|rect_subtype|shape_layer_hint)\\b" backend/app/visual_primitive_graph.py
```
