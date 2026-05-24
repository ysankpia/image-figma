# M29 Raw Components No-Behavior Split

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Goal

把 raw M29 primitive graph 的 mask/component 中间证据层迁入 `backend/app/visual_primitive/components.py`，继续降低 `backend/app/visual_primitive_graph.py` 的职责密度。

本阶段只做无行为变化拆分，不改 raw M29 输出 JSON、不改 primitive ID、不改 foreground/background 采样阈值、不改 connected component 遍历、不改 mask data、不改 bbox/metrics 计算、不改 upload pipeline。

## Changes

- 新增 `backend/app/visual_primitive/components.py`。
- 迁移 component evidence helpers：
  ```text
  build_text_exclusion_mask
  build_global_foreground_mask
  estimate_global_background
  connected_components
  build_image_protection_mask
  build_remaining_foreground_mask
  add_internal_contrast_pixels
  is_protective_shape
  ```
- `is_protective_shape` 跟随 component layer 迁移，避免 `components.py` 反向 import `visual_primitive_graph.py`。
- `backend/app/visual_primitive_graph.py` 继续保留 orchestration、support detector、primitive detector、artifact 和 validation 逻辑，并通过 import 继续 re-export 旧调用方依赖的 component 符号。
- 更新 `docs/engineering/current-mainline-code-map.md` 和 completed plan index。

## Non-Goals

- 不拆 support detector 的 detect/find/score 函数。
- 不拆 primitive detector、blocked reason、image/symbol scoring。
- 不拆 relations、artifact writers、preview sheet、validation、meta。
- 不引入新 threshold、theme rule、bbox 特判或 fallback 规则。

## Acceptance

- `tests/test_visual_primitive_graph.py` 通过。
- raw M29 component/mask 依赖的主链测试通过。
- 后端全量测试通过。
- 前端/plugin test、typecheck、build 通过。
- `visual_primitive/components.py` 低于约 350 行。
- `visual_primitive_graph.py` 不再定义 components 函数，只 re-export。
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
rg -n "^def (build_text_exclusion_mask|build_global_foreground_mask|estimate_global_background|connected_components|build_image_protection_mask|build_remaining_foreground_mask|add_internal_contrast_pixels|is_protective_shape)\\b" backend/app/visual_primitive_graph.py
```
