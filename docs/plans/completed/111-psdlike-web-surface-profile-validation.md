# 111 PSD-like Web Surface Profile Validation

- 状态：completed
- 创建日期：2026-06-03
- 负责人：Codex

## Summary

108/109/110 已经把移动端 targeted 问题收口到 surface-first ownership：

```text
OCR/model hint
-> local connected pixel surface
-> role classification
-> confirmed control/container surface materialization
```

本阶段修复 Web 端适配缺口。当前代码已有 `ControlProfile` 和 `web_like` 阈值，但 profile 尚未完整贯穿：

```text
control_surface_search_boxes 仍是固定移动端 padding 枚举
local surface window expansion 仍是固定文本倍数
visible container surface 面积上限仍固定 page_area * 0.08
model control search window 仍固定 0.08 page ratio 和固定 padding
Web table/list row negative gate 尚缺
```

目标不是新开一套 Web 分支，而是让同一套 surface-first gate 基于画布自动调整：

```text
canvas aspect/area
-> ControlProfile
-> OCR local surface extraction/search
-> model assisted search
-> control/container role gate
-> mobile targeted cases remain stable
```

## Non-goals

```text
不改 renderer/plugin/Go/API/DSL schema
不新增 WebButton/Card/Table visible layer kind
不按 case id、路径、图片名、品牌、固定坐标、固定 bbox、固定屏幕尺寸、可见文案 literal 做规则
不跑 86-case，除非用户另行要求
不声称 Web 全量生产可用；本阶段只把算法 profile 缺口补齐并加合成验证
```

## Key Changes

### Profile Propagation

扩展现有 `ControlProfile`，继续由 `build_control_profile(width, height)` 自动推导：

```text
mobile:
  max_control_area = min(24000, max(6000, page_area * 0.04))
  max_control_aspect = 14
  min_height = 14
  max_container_area_ratio = 0.08

web_like:
  max_control_area = min(48000, max(6000, page_area * 0.04))
  max_control_aspect = 36
  min_height = 12
  max_container_area_ratio = 0.14
```

### Web-Aware Local Surface Search

`local_surface_window_for_text()` 和 `control_surface_search_boxes()` 接收 `profile`：

```text
mobile 保持当前保守扩展
web_like 允许更宽的横向 padding，但 window 仍受 canvas/profile 面积限制
```

模型路径仍只提供 search window 和 class hint，不绕过 local surface gate。

### Web Container Gate

`is_visible_container_surface()` 改为 profile-aware：

```text
mobile 保持 110 的 8% 上限
web_like 允许更大 dashboard card/panel surface
仍要求有限 surface、稳定 fill、低纹理、闭合/不触边、contained OCR 合理
```

### Table/List Row Negative Gate

Web 常见表格/列表行不能因为多文本和低纹理被 materialize 成大 container surface：

```text
多行同高、同 x/span、y 间距稳定
surface 是横向 row band
缺少独立卡片 gutter/闭合边界
-> role audit_only/container metadata only，不作为 visible local_container_surface
```

## Test Plan

Backend:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

Synthetic Web fixtures:

```text
wide Web search input should become one confirmed control surface
adjacent toolbar/chip controls should stay distinct
dashboard cards may materialize as container surfaces
table/list rows should not become large local_container_surface shapes
model-assisted high-confidence control still requires physical surface
```

Mobile targeted regression:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_111_web_profile_mobile_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_111_web_profile_mobile_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0037_7aa443d6c7 \
  --case-id case_0058_b048f93bd2
```

Hard gates:

```text
failed cases = 0
DSL valid = true for all targeted cases
missingAssetCount = 0
shapeAssetCount = 0
fullPageVisibleRaster = 0
tinyRasterFragments = 0
108/109/110 targeted defects do not regress
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
45 passed, 1 warning
```

Synthetic Web regression coverage added:

```text
wide Web search input materializes as one confirmed control surface with fill + stroke
dashboard metric cards materialize as local_container_surface
table/list rows do not materialize as large local_container_surface shapes
mobile and web ControlProfile thresholds remain distinct
existing sibling card/container and adjacent chip controls still pass
```

Targeted mobile regression:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_111_web_profile_mobile_targeted
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_111_web_profile_mobile_targeted \
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
  controlProfileKind = mobile
  controlSurfaceShapeLayerCount = 4
  containerSurfaceShapeLayerCount = 0
  modelAssistedMediaRasterCount = 0
  textOwnerBboxRecenteredCount = 3

case_0037_7aa443d6c7:
  controlProfileKind = mobile
  controlSurfaceShapeLayerCount = 0
  containerSurfaceShapeLayerCount = 0
  modelAssistedMediaRasterCount = 1

case_0058_b048f93bd2:
  controlProfileKind = mobile
  controlSurfaceShapeLayerCount = 4
  containerSurfaceShapeLayerCount = 6
  containerParentShapeSuppressedCount = 2
  textOwnerBboxRecenteredCount = 4
```

Real Web validation:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
rm -rf /Users/luhui/Downloads/psdlike_111_web_dorm_eval_ocr
PSDLIKE_OCR_CACHE_DIR=/Users/luhui/Downloads/psdlike_111_web_dorm_ocr_cache \
uv run python tools/batch_eval.py \
  --input-dir /Users/luhui/Downloads/宿舍管理系统 \
  --out /Users/luhui/Downloads/psdlike_111_web_dorm_eval_ocr \
  --limit 0 \
  --require-ocr
```

Result:

```text
cases = 7
failed cases = 0
failure types = {}
DSL valid = true for all 7
controlProfileKind = web_like for all 7
OCR provider = baidu_ppocrv5
OCR text counts = 63-169 per case
missingAssetCount = 0 for all 7
shapeAssetCount = 0 for all 7
fullPageVisibleRaster = 0 for all 7
tinyRasterFragments = 0 for all 7
rawTextOverlapRaster = 0 for all 7
rasterTextKnockoutCount = 0 for all 7
```

Real Web artifact inspection:

```text
/Users/luhui/Downloads/psdlike_111_web_dorm_eval_ocr/source_vs_draft_contact_sheet.png
/Users/luhui/Downloads/psdlike_111_web_dorm_eval_ocr/overlay_contact_sheet.png
/Users/luhui/Downloads/psdlike_111_web_dorm_eval_ocr/case_0001_19fb293381/draft_preview.png
/Users/luhui/Downloads/psdlike_111_web_dorm_eval_ocr/case_0003_6f3991f1b1/draft_preview.png
/Users/luhui/Downloads/psdlike_111_web_dorm_eval_ocr/case_0006_d4a2739c7a/draft_preview.png
```

Inspection notes:

```text
Web table/list pages did not materialize repeated rows as broad container surfaces.
Web card/dashboard pages produced web_like control/container counts without full-page backing or asset explosion.
Visual quality is usable for first Web targeted validation, but exact 1:1 typography/card styling remains future quality work.
```

Anti-specialization check:

```text
Production changes use canvas aspect/area, OCR geometry, connected surface support, stroke pixels, table/list row repetition geometry, and generic merge priority.
No production rule uses case id, image path/name, brand, literal visible text, fixed bbox, fixed coordinate, or fixed screen size.
```
