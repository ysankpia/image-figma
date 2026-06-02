# 108 PSD-like Surface-First Control False-Positive Repair

- 状态：completed
- 创建日期：2026-06-03
- 完成日期：2026-06-03
- 当前修订：surface-first 修复规划
- 负责人：Codex

## Summary

本阶段修复 106B/C/D 后暴露的控制面误检：

```text
图表刻度 / 数据卡片 / 电子证件卡片内部文字
-> 被 OCR-anchored 或 model-assisted control path materialize 成 ShapeLayer 色块
```

最新取证结论：

```text
旧 3000 行 V1 oracle 在同三张图上也复现同类误检
当前 clean service 不是唯一根因
第一版 108 dirty patch 只减少少量 shape，没有切断错误链路
V2 vector-surface 实验更接近正确抽象：先找真实 surface，再做 role 分类
```

因此本阶段不继续在旧 OCR-padding gate 上堆阈值。正确修复是把 control 路径改成：

```text
OCR/model hint
-> local pixel surface extraction
-> source surface ownership gate
-> role classification: control_surface | container_surface | chart_or_media_internal | audit_only
-> only confirmed control_surface can suppress control-owned raster
-> ShapeLayer / RasterLayer / TextLayer
```

第一性原则不变：

```text
PNG 像素 = 物理真相
OCR = 文字真相
model_evidence = 语义提示和局部搜索窗口
最终 DSL = ownership planner 的结果
```

核心边界：

```text
模型不能直接决定 ownership
OCR 文本不能直接外扩硬造 control bbox
稳定填充色不能单独证明独立控件
ShapeLayer 必须来自真实像素 surface / source owner
```

## Problem Statement

当前错误链路是：

```text
OCR block
-> 枚举 padding bbox
-> 从文字附近采样 fill
-> 通过 fill / texture / ring gate
-> 生成 ocr_anchored_control_surface
-> suppress control-owned raster
```

这里的根本错误是：候选 bbox 是从 OCR 外扩猜出来的，而不是从真实像素对象边界长出来的。后续 gate 再严格，也只是在验证一个猜出来的框，不是在验证真实 layer owner。

三个典型失败：

```text
case_0036_764d3a58e5:
  图表刻度和蓝色折线/块相邻，fill 被图表色污染，刻度区域变成蓝色 rounded Shape。

case_0002_085b0ade97:
  深色数据卡片和页面背景差异极小，局部卡片/数据区被误当普通 control。

case_0058_b048f93bd2:
  同一电子证件卡片内多行 OCR 分别触发单控件候选，生成一堆重叠蓝/绿/橙 Shape。
```

## Historical Evidence

### V1 Is Not The Fix

已用旧脚本跑同三张图：

```text
services/backend-python/tools/psd_like_layer_decomposition_experiment.py
```

输出：

```text
/Users/luhui/Downloads/psdlike_108_v1_oracle_targeted
```

结论：

```text
case_0036: 旧 V1 也生成多个蓝色 ocr_anchored_control_surface
case_0002: 旧 V1 也把深色数据卡片/背景区域升成 control shape
case_0058: 旧 V1 也把证件卡片切成多块 ocr_anchored_control_surface
```

因此 108 不是“把 clean service 对齐旧 V1”即可解决。旧 V1 当时 100/103 的目标主要是修按钮漏召回，不是彻底解决 control false positive。

### V2 Gives The Right Direction

V2 实验路线：

```text
PNG
-> OCR text mask
-> vector surface extraction
-> rounded rect fitting
-> shape ownership planner
-> raster fallback
```

关键不同：

```text
V1/current: OCR bbox -> padding boxes -> control candidate
V2: OCR text seed -> local fill connected component -> real surface bbox -> role
```

已跑同三张图：

```text
/Users/luhui/Downloads/psdlike_108_v2_vector_targeted
```

观察：

```text
case_0058:
  V2 将证件卡片块识别成 container_surface，而不是每行文字一个 control。

case_0036:
  V2 对图表/蓝色大区更多走 container_surface，而不是每个 tick 都切成按钮。

case_0002:
  V2 仍不完美，但暴露了正确层次：先找真实 surface，再分类 control/container。
```

V2 不能直接替换当前主线，但可以迁移它的核心思想：

```text
surface-first source ownership gate
role split
raster fallback does not cover vector-owned control background
```

## Current Dirty Patch Policy

当前工作区已有第一版 108 dirty patch：

```text
services/psdlike-python/app/core/controls.py
services/psdlike-python/app/core/model_control.py
services/psdlike-python/app/core/pipeline.py
services/psdlike-python/tests/test_core_pipeline.py
services/psdlike-python/tools/batch_eval.py
```

它包含：

```text
ControlProfile
OCR text role risk
ring evidence
boundary closure
tighter dedupe
targeted --case-id support
```

验证事实：

```text
py_compile passed
pytest passed
targeted batch hard gates passed
但 case_0036 / case_0058 视觉误检仍存在
```

处理原则：

```text
不得提交为完成态
可保留其中可泛化的底层工具函数
必须重构为 surface-first gate 的从属证据
不允许继续把 OCR-padding candidate 作为 visible owner source
```

## Correct Architecture

新的 control path：

```text
load image / OCR / model evidence
-> physical raster / shape / surface candidates
-> OCR/model local hints
-> local text-surface extraction
-> source surface ownership gate
-> role classifier
-> control-specific raster suppression
-> media/text ownership
-> layer_stack / DSL / reports
```

核心数据对象建议：

```text
LocalSurfaceCandidate:
  id
  bbox
  fill
  fillCoverage
  closeCoverage
  texture
  edgeDensity
  cornerRadiusEvidence
  containedTextIds
  seedTextId?
  sourceHintIds
  extractionReason
  scores

SurfaceRoleDecision:
  surfaceId
  role = control_surface | container_surface | chart_or_media_internal | audit_only
  decision = accepted | rejected | metadata_only
  reason
  sourceRefs
```

第一版仍只输出现有可见 layer kinds：

```text
TextLayer
RasterLayer
ShapeLayer
ReferenceImage
GroupLayer
```

不新增 Button/Card/Chart 等结构层。role 只进入 scores / semanticTags / diagnostics / ownership decisions。

## Implementation Plan

### Step 0: Preserve Evidence And Baseline

保留以下目录作为本阶段证据：

```text
/Users/luhui/Downloads/psdlike_108_v1_oracle_targeted
/Users/luhui/Downloads/psdlike_108_v2_vector_targeted
/Users/luhui/Downloads/psdlike_108_control_hardening_targeted
```

在最终 validation evidence 中记录：

```text
旧 V1 也复现误检
第一版 108 dirty patch 未解决目标视觉问题
V2 surface-first 对 case_0058/0036 的 role split 更接近正确方向
```

### Step 1: Add Local Surface Extraction In Clean Service

在 `services/psdlike-python/app/core/controls.py` 增加 surface-first primitive，参考 V2 但重写为当前服务代码，不 import 旧 backend：

```text
candidate_window_for_text(block, canvas)
estimate_surface_fill_near_text(rgb, text_mask, block)
extract_local_surface_from_text_seed(...)
dedupe_local_surfaces(...)
```

关键规则：

```text
seed 来自 OCR block 或 model-assisted window 内的 OCR block
fill 从文字左右/上下邻近非文字像素取样
在局部窗口里找与 fill 接近且连通的 surface component
最终 bbox 来自 connected component / physical support，不来自 arbitrary padding
```

硬边界：

```text
如果没有 connected physical surface，不生成 visible ShapeLayer
如果 component 是整页/大图/高纹理区域，拒绝或 audit-only
如果 surface bbox 只是 OCR bbox padding 猜测，不允许成为 owner
```

### Step 2: Classify Surface Role

新增 role classifier：

```text
classify_local_surface_role(surface, ocr_blocks, model_context, canvas_profile)
```

第一版 role：

```text
control_surface:
  独立有限控件，如按钮、输入框、chip、底栏单项、tab 单项

container_surface:
  卡片、证件、图表容器、列表项、数据面板等

chart_or_media_internal:
  图表刻度、图像/海报/地图/封面内部文字相关 surface

audit_only:
  证据不足，不改变 visible ownership
```

role 判定只使用：

```text
surface bbox
surface fill/texture/boundary evidence
contained OCR 几何关系
OCR 字符类别
model class/confidence/bbox 作为 hint
relative geometry / canvas-normalized area
local surrounding contrast
```

禁止使用：

```text
case id
路径
文件名
品牌
具体文案
固定坐标
固定 bbox
固定屏幕尺寸
```

### Step 3: Add Parent-Containment Negative Gate

这是 case_0058 / case_0002 的关键。

通用规则：

```text
如果候选 surface 是一个更大同色/近色 surface 的内部切片，
且自身没有独立闭合边界，
且 contained OCR 与更大 surface 的 OCR 关系更像卡片/容器，
则不能作为 control_surface。
```

输出：

```text
role = container_surface 或 audit_only
reason = parent_surface_slice_not_control
```

这个 gate 解决的问题：

```text
电子证件卡片内多行文字分别切出小 control
深色数据卡片上单个标题/数值附近切出伪按钮
同色大卡片内部 label 被误判为独立控件
```

### Step 4: Add Chart/Data Context Negative Gate

这是 case_0036 的关键。

规则：

```text
OCR role 属于 numeric_metric / currency_or_percent / date_or_time / short_symbol
并且附近存在 >=3 个同类 OCR block
并且 x/y 对齐稳定或间距近似等差
并且 local surface 缺少独立闭合边界
=> role = chart_or_media_internal 或 audit_only
=> reason = chart_tick_like_surface_not_control
```

注意：

```text
纯数字真实按钮不能被 regex 直接杀掉
如果数字按钮有真实 connected surface + 独立闭合边界 + control 尺寸/padding，仍可 accepted
```

### Step 5: Rewire OCR-Anchored Control Path

替换旧核心：

```text
旧:
  control_surface_search_boxes(block.bbox)
  -> score_ocr_anchored_control_surface(padding box)

新:
  extract_local_surface_from_text_seed(block)
  -> classify_local_surface_role(surface)
  -> only control_surface becomes ShapeLayer reason=ocr_anchored_control_surface
```

保留旧 padding search 只能作为 fallback/audit：

```text
如果没有 physical surface，只记录 rejected/audit reason
不直接 materialize ShapeLayer
```

新增 diagnostics：

```text
localSurfaceCandidateCount
localSurfaceAcceptedControlCount
localSurfaceContainerCount
localSurfaceChartInternalCount
localSurfaceAuditOnlyCount
localSurfaceRejectedReasons
```

### Step 6: Rewire Model-Assisted Control Path

`model_control.py` 只提供窗口和 class hint：

```text
TextButton/EditText/... model bbox
-> local search window
-> extract local surface inside window
-> classify role with same gates
```

固定边界：

```text
high confidence 只能扩大窗口
不能跳过 source surface ownership gate
不能把 model bbox 直接变 ShapeLayer
```

输出 reason：

```text
model_assisted_control_surface
```

但必须带：

```text
sourceRefs = ["model_evidence:det_x", "ocr:text_y", "pixel:local_surface_gate"]
```

### Step 7: Restrict Raster Suppression To Confirmed Controls

修改 `suppress_control_owned_rasters()` 的输入语义：

```text
只有 role/controlSurface=confirmed_control_surface 的 Shape 才能 suppress raster
container_surface 不 suppress control-owned raster
chart_or_media_internal 不 suppress raster
audit_only 不 suppress raster
```

原因：

```text
错误 control 一旦 suppress raster，会把图表线、图片块、卡片纹理一起删掉。
控制面误检的破坏力主要来自后续 suppress，而不是 ShapeLayer 数量本身。
```

### Step 8: Keep Existing Hardening As Secondary Evidence

当前 dirty patch 中这些可以保留，但变成 secondary gates：

```text
ControlProfile
OCR text role risk
ring evidence / boundary closure
multi-text unrelated gate
cross-source dedupe
batch_eval --case-id
```

但它们不能替代 source surface gate。

执行顺序：

```text
surface extraction
-> role classification
-> boundary / text role / multi-text / dedupe as supporting gates
```

不要再走：

```text
OCR padding box
-> ring support enough
-> visible owner
```

## Pipeline Ordering

目标顺序：

```text
1. existing physical raster/shape/surface candidates
2. local OCR-seeded surface extraction
3. OCR anchored surface role classification
4. model-assisted control surface extraction/classification
5. merge confirmed control ShapeLayer candidates
6. suppress control-owned raster only for confirmed controls
7. model media refinement
8. suppress text-owned raster fragments
9. assign confirmed media-owned text blocks
10. layer_stack / DSL
11. semantic evidence audit
```

这样控制面先于 media，但只有 confirmed control 才能影响 media/raster ownership。

## Tests

### Unit Tests

必须覆盖：

```text
chart numeric tick near blue graphic line does not create control ShapeLayer
numeric real button with connected closed surface remains ShapeLayer
large dark data card does not become ordinary control ShapeLayer
small dark button on dark card with independent boundary remains ShapeLayer
certificate/card multi-row text creates container/audit, not many overlapping controls
same visual button from raster promotion + OCR anchor dedupes to one ShapeLayer
adjacent chip/tab controls are not incorrectly merged
model-assisted TextButton inherits surface-first gates
high-confidence model bbox cannot create ShapeLayer without physical surface
container_surface cannot suppress raster
```

### Targeted Validation

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_108_surface_first_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0002_085b0ade97 \
  --case-id case_0058_b048f93bd2
```

验收：

```text
case_0036:
  图表刻度区域不再出现蓝色 control rounded blocks。

case_0002:
  深色大数据卡片/近背景区域不再作为普通 control Shape。

case_0058:
  证件卡片不再被多行 OCR 切成多块重叠 control Shape。
```

还要检查：

```text
missingAssetCount = 0
shapeAssetCount = 0
fullPageVisibleRaster = 0
container/audit role 不触发 control raster suppression
```

### 86-Case Regression

No-model：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --out /Users/luhui/Downloads/psdlike_108_surface_first_nomodel_eval_all \
  --limit 0
```

Model-visible：

```bash
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_108_surface_first_model_visible_eval_all \
  --limit 0
```

硬门：

```text
86/86 pass
DSL valid = 100%
missingAssetCount = 0
shapeAssetCount = 0
fullPageVisibleRaster = 0
tinyRasterFragments = 0
YOLO TextLayer creation = 0
YOLO direct asset crop = 0
```

质量门：

```text
controlSurfaceShapeLayerCount 可以下降，因为本阶段是在清误检
real CTA/search/chip/tab/input controls 不能系统性消失
rawTextOverlapRasterTotal <= current r3 baseline 32
rasterTextKnockoutCountTotal <= current r3 baseline 52
visualMaeAverage 不系统性变差
modelControlAcceptedCount 下降时必须解释哪些是误检被移除
```

### Visual Artifact Review

必须人工看：

```text
draft_preview.png
preview.html
overlay.png
semantic_evidence_report.md
model_ownership_decisions.v1.json
ownership_report.v1.json
```

不能只看 summary pass/fail。

## Diagnostics And Reports

新增/扩展：

```text
localSurfaceCandidateCount
localSurfaceAcceptedControlCount
localSurfaceContainerCount
localSurfaceChartInternalCount
localSurfaceAuditOnlyCount
localSurfaceRejectedReasons

controlProfileKind
controlMaxArea
controlMaxAspect
controlBoundaryClosureRejectedCount
controlParentSurfaceSliceRejectedCount
controlChartInternalRejectedCount
controlDuplicateShapeSuppressedCount
```

per-decision evidence 示例：

```json
{
  "kind": "local_surface_role_decision",
  "surfaceId": "surface_0042",
  "role": "container_surface",
  "decision": "metadata_only",
  "reason": "parent_surface_slice_not_control",
  "bbox": {"x": 303, "y": 989, "width": 245, "height": 135},
  "sourceRefs": ["ocr:text_0052", "pixel:local_surface_gate"]
}
```

## Acceptance

本阶段完成必须满足：

```text
三张 targeted case 视觉问题解决
86-case no-model hard gates pass
86-case model-visible hard gates pass
真实按钮/输入框/chip/tab 不系统性漏召回
模型路径不能绕过 surface-first gate
所有 accepted/rejected control decisions 可审计
无样本特化
```

不要求：

```text
所有 container/card 都完美 vectorize
rawTextOverlapRaster = 0
rasterTextKnockoutCount = 0
Auto Layout / componentization
新增 Button/Card visible layer kind
```

## Validation Evidence

提交前验证：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

结果：

```text
30 passed, 1 warning
```

Targeted surface-first validation：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_108_surface_first_targeted \
  --case-id case_0036_764d3a58e5 \
  --case-id case_0002_085b0ade97 \
  --case-id case_0058_b048f93bd2
```

结果：

```text
failed cases: 0
DSL valid: true for all 3
missingAssetCount: 0 for all 3
shapeAssetCount: 0 for all 3
fullPageVisibleRaster: 0 for all 3
tinyRasterFragments: 0 for all 3
```

人工检查：

```text
case_0036_764d3a58e5:
  图表刻度区域不再出现蓝色 control rounded blocks。

case_0002_085b0ade97:
  深色大数据卡片不再作为普通 control Shape。

case_0058_b048f93bd2:
  证件卡片不再被多行 OCR 切成多块重叠 control Shape。
```

备注：

```text
86-case model-visible regression 曾启动到 case_0036 左右，随后按用户指令停止。
本阶段提交门以 targeted false-positive 修复、静态检查和单测为准。
后续文字样式/按钮文本 fit 问题另开阶段处理。
```

## Non-Goals

```text
不改 renderer
不改 Figma plugin
不改 services/backend-go
不改 services/psdlike-go
不把旧 V1 oracle 重新作为产品路径
不新增 YOLO/ONNX/ultralytics 运行依赖
不引入 Button/Card/Chart 结构层
不做 Auto Layout 或组件化
```

## Anti-Specialization Rules

禁止：

```text
case id
file path
image name
visible text literal
brand
fixed coordinate
fixed bbox
fixed screen size
theme-specific color constants
```

允许：

```text
OCR bbox/confidence/text character class
OCR 几何排布
model class/confidence/bbox as hint
pixel color/edge/texture
connected component
IoU/IoA
relative geometry
canvas-normalized area
local surrounding contrast
parent/child surface containment
```

## Recommended Commit Shape

如果实现中需要先整理第一版 dirty patch：

```text
test: add targeted psdlike case evaluation support
feat: add psdlike surface-first control gates
```

最终阶段提交建议：

```text
feat: repair psdlike control false positives with surface gates
```
