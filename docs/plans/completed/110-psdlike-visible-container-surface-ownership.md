# 110 PSD-like Visible Container Surface Ownership

- 状态：completed
- 创建日期：2026-06-03
- 负责人：Codex

## Summary

修复 108/109 后暴露的非 control 容器 surface 可见 ownership 缺口：

```text
OCR/model local surface 已经找到卡片/证件/列表项等 container_surface
但 container_surface 只作为 metadata_only
于是粗粒度 low_texture_solid_region shape 抢走 visible ownership
最终多张独立卡片被一整块父级色块覆盖
```

本阶段只改 `services/psdlike-python` 的 local surface/container materialization 和 shape suppression，不改 renderer/plugin/Go/API/DSL schema。

目标链路：

```text
PNG pixels + OCR seeds
-> local connected surface extraction
-> role classification
-> control_surface becomes confirmed control ShapeLayer
-> finite container_surface becomes ordinary ShapeLayer
-> parent blob shape covered by child container surfaces is suppressed
-> TextLayer stays above shapes
```

## Non-goals

```text
不把 container_surface 变成 control_surface
不新增 CardLayer / ContainerLayer / ButtonLayer
不按 case id、路径、图片名、文案、品牌、固定坐标、固定 bbox、固定屏幕尺寸做规则
不跑 86-case，除非用户另行要求
```

## Key Changes

### Visible Container Surface

将合格的 `container_surface` materialize 为普通 `ShapeLayer`：

```text
reason = local_container_surface
surfaceRoleContainer = 1
confirmedControlSurface = 0
```

硬 gate：

```text
finite local surface
not chart_or_media_internal
not page/background major region
surface area <= page_area * 0.08
fill/close coverage stable
texture/edge/entropy not image-like
contained OCR count >= 2
```

### Parent Blob Suppression

如果一个普通 shape 覆盖多个独立 container child surfaces，则父 shape 不应作为 visible foreground owner：

```text
parent reason in low_texture_solid_region
child reason = local_container_surface
child count >= 2
children contained in parent
children sibling-aligned with visible gutters
children total area explains meaningful parent area
parent not background_surface_band / inferred_background_plate / control_surface
```

输出 rejection evidence：

```text
kind = container_parent_shape_suppressed
reason = container_children_own_surface
childSurfaceIds = [...]
```

## Test Plan

Backend:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

Targeted validation:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_110_container_surface_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_110_container_surface_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0037_7aa443d6c7 \
  --case-id case_0058_b048f93bd2
```

Acceptance:

```text
failed cases = 0
DSL valid = true for all 3
missingAssetCount = 0
shapeAssetCount = 0
fullPageVisibleRaster = 0
tinyRasterFragments = 0
case_0058 electronic certificate area is not one broad green ShapeLayer
case_0058 certificate cards materialize as separate non-control ShapeLayer surfaces
case_0036 withdraw button ownership/text alignment does not regress
case_0037 text style does not regress
```

## Validation Evidence

Backend checks:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

Result:

```text
41 passed, 1 warning
```

Targeted validation:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_110_container_surface_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_110_container_surface_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0037_7aa443d6c7 \
  --case-id case_0058_b048f93bd2
```

Result:

```text
cases = 3
failed cases = 0
DSL valid = true for all 3
missingAssetCount = 0 for all 3
shapeAssetCount = 0 for all 3
fullPageVisibleRaster = 0 for all 3
tinyRasterFragments = 0 for all 3
```

Targeted diagnostics:

```text
case_0036_764d3a58e5:
  containerSurfaceShapeLayerCount = 0
  controlSurfaceShapeLayerCount = 4
  modelAssistedMediaRasterCount = 0
  textOwnerBboxRecenteredCount = 3
  withdraw button ownership from 109 did not regress.

case_0037_7aa443d6c7:
  containerSurfaceShapeLayerCount = 0
  hard gates passed.

case_0058_b048f93bd2:
  containerSurfaceShapeLayerCount = 6
  containerParentShapeSuppressedCount = 2
  electronic certificate row has four visible local_container_surface card shapes:
    x49 y989 w221 h135
    x303 y989 w245 h135
    x560 y989 w245 h135
    x817 y989 w104 h135
  broad parent blob x32 y920 w888 h216 suppressed as container_children_own_surface.
```

Artifacts inspected:

```text
/Users/luhui/Downloads/psdlike_110_container_surface_targeted/case_0058_b048f93bd2/draft_preview.png
/Users/luhui/Downloads/psdlike_110_container_surface_targeted/case_0058_b048f93bd2/overlay.png
/Users/luhui/Downloads/psdlike_110_container_surface_targeted/case_0036_764d3a58e5/draft_preview.png
```
