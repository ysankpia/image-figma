# Bug: 有限控件背景被保守保留为 media raster

- 状态：resolved
- 创建日期：2026-05-25
- 解决日期：2026-05-26
- 影响范围：raw M29 visual primitive graph、M29.2 source ownership、M29.5 cleanup authorization、525 真实样本可编辑质量

## Summary

`/Users/luhui/Downloads/525测试` 的 6 张真实样本已经能稳定完成 upload-preview，且最近批量验证中 ownership conflict 为 0。但部分有限 UI 控件仍被保守识别为 `media_region / preserve_raster`，导致控件背景不能作为可拖拽 shape/image 层出现；控件上的 OCR 文本虽然能变成 editable text，但父 raster 仍可能承担了本该属于控件背景的像素 ownership。

典型表现是短文本的宽按钮、结算按钮、胶囊按钮、卡片内圆形加号控件等：

```text
control background -> preserve_raster media
control text       -> editable_text
result             -> Figma 中文字可编辑，但按钮背景仍像图片块
```

这不是字体识别问题，也不是需要 Pillow/OpenCV/SAM 依赖的问题。根因在上游 source evidence 和 ownership 分类：有限控件背景的几何证据不够强时，M29.2 会把 low-confidence image-like unknown 提升成 media。

## Reproduction

复现方式：

1. 运行 525 批量验证：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

2. 查看最近 ledger：

```text
backend/tmp/validation/upload_preview_batch_20260525_205941/upload_preview_batch_validation.json
```

3. 查看茶饮点单样本 `task_930455a25909`：

```text
m29_2/source_ui_physical_graph.json
m29_5/replay_plan.json
materialized_design/materialization_report.json
m29_dsl_visual_comparison/source_diff.png
```

4. 观察底部结算类按钮附近的 source object：

```json
{
  "bbox": [662, 1479, 206, 66],
  "visualKind": "media_region",
  "pixelOwner": "preserve_raster",
  "replayDecision": "image_replay",
  "reasons": ["large_image_like_region"],
  "risks": ["contains_internal_text"]
}
```

5. 同一区域的 OCR 文本已经是 editable text：

```json
{
  "bbox": [718, 1493, 95, 38],
  "visualKind": "editable_ui_text",
  "pixelOwner": "editable_text",
  "replayDecision": "text_replay"
}
```

## Root Cause

根因有两个：

1. `text_support_background` 的 raw M29 搜索窗口偏窄。它能找到贴近文字的小 badge/tag 背景，但对“文字短、按钮宽、左右 padding 大”的有限控件，候选窗口可能停留在按钮内部，无法碰到外环边界，因此 `finite_outer_ring` 证据失败。
2. M29.2 在 `unknown / image_like_low_confidence` 上仍会按颜色数、纹理和面积把它提升成 `media_region`。当 raw M29 同时存在覆盖同一区域的大面积 control-shape 证据时，media classification 没有让位给 control background ownership。

第一性原理判断：

```text
source truth:
  source PNG pixels + OCR bbox + raw M29 shape/unknown evidence

owning layer:
  raw M29 support detection + M29.2 source ownership

do not fix in:
  materializer / Renderer / Figma plugin
```

## Fix

当前采用无新增依赖的修复路线：

1. 扩展 `text_support_background` 的水平 padding 搜索，让它能覆盖短文本宽按钮，但仍要求稳定 fill、有限外环和边界色差。
2. 在 M29.2 media classification 中，如果 `image_like_low_confidence` unknown 被 control/background shape 大面积覆盖，则不再抢占为 `media_region`。
3. 对没有 raw shape 但满足有限控件公式的 `unknown / image_like_low_confidence`，用 OCR containment、finite bbox、低纹理/低边缘复杂度、fill ratio 和 source PNG 非文本像素采样生成 `control_background / shape_geometry / shape_replay`。
4. M29.5 只对最终会 materialize 的 parent media 保留 copied-image cleanup target；如果 parent media 被 visible overlap suppression 裁掉，则同时裁掉指向该 media 的 copied cleanup target。
5. Materializer 只消费 M29.5 `cleanupTargets`，并且只使用 M29.2 source evidence 中的 `shapeFillOverride` / `shapeRadiusOverride` 做 shape replay style，不发明 owner 或 cleanup 权限。

不做：

```text
不按颜色、文案、文件名、样本 bbox 特化
不新增 Pillow/OpenCV/SAM/ONNX 依赖
不改 DSL/API/Renderer/plugin protocol
```

## Regression Guard

已新增或确认的回归保护：

- raw M29：短文本宽胶囊按钮能生成 `text_support_background` shape。
- M29.2：低置信 unknown 与 control-shape 大面积重叠时，control-shape 获得 `shape_geometry` ownership，unknown 不再变成 media。
- M29.2：低置信 unknown 具有有限控件证据时直接成为 `control_background / shape_replay`。
- M29.5：shape inside media 只在 parent media 最终 materialized 时声明 copied image cleanup target。
- materializer：shape cleanup 只能由 M29.5 target 触发；无 target 时不能擦 copied media。
- 真实样本：525 全量 batch 仍完成，ownership conflict 仍为 0。

## Validation Evidence

2026-05-26 16:02 CST 再次验证：

```bash
cd backend
uv run pytest tests/test_source_ui_physical_graph.py tests/test_visual_primitive_graph.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q

uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

结果：

```text
targeted tests: 92 passed in 17.31s
ledger: backend/tmp/validation/upload_preview_batch_20260526_080221/upload_preview_batch_validation.json
inputCount = 6
supportedInputCount = 6
completedTaskCount = 6
supportedFailedCount = 0
degradedRecordCount = 0
backendCrashCount = 0
missingArtifactCount = 0
assetFetchFailedCount = 0
totalVisibleReplayClaimCount = 381
totalVisibleOwnershipOverlapConflicts = 0
ownershipConflictTypeCounts = {}
```

茶饮点单样本当前验证：

```text
source = /Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_52_19.png
taskId = task_e9899b456736
M29.2 object = m292_object_0108
bbox = [662, 1479, 206, 66]
visualKind = control_background
pixelOwner = shape_geometry
replayDecision = shape_replay
reason = low_confidence_unknown_control_background
shapeFillOverride = #456441
shapeRadiusOverride = 33
M29.5 action = shape_replay
DSL node = m29_shape_0004
DSL fill = #456441
DSL radius = 33
```

M29.5 cleanup 验证：

```text
Only fallback cleanup target remains for this control.
The copied image cleanup target is suppressed because the parent media was not
materialized. No invalid copied cleanup conflict is introduced.
```

2026-05-25 22:31 CST 已验证：

```bash
cd backend
uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_transparent_asset_report.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  tests/test_ownership_conservation.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_visual_primitive_graph.py \
  -q

uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
git diff --check
```

结果：

```text
125 passed in 15.91s
ledger: backend/tmp/validation/upload_preview_batch_20260525_222638/upload_preview_batch_validation.json
inputCount = 6
completedTaskCount = 6
failedTaskCount = 0
missingArtifactCount = 0
totalVisibleReplayClaimCount = 370
totalVisibleOwnershipOverlapConflicts = 0
ownershipConflictTypeCounts = {}
```

茶饮样本验证：

```text
taskId = task_e3bad3f1eefe
source = /Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_52_19.png
M29.2 object = m292_object_0108
bbox = [662, 1479, 206, 66]
visualKind = control_background
pixelOwner = shape_geometry
replayDecision = shape_replay
reason = low_confidence_unknown_control_background
shapeFillOverride = #456441
shapeRadiusOverride = 33
M29.5 action = shape_replay
```

同一区域的父 media `m292_object_0064` 被 M29.5 visible overlap suppression，未生成 copied image asset；因此指向该 media 的 copied cleanup target 被裁掉，只保留 fallback cleanup。DSL 中按钮背景已经作为独立 `m29_shape` 出现，文本仍是 `text_replay`。

## Prevention Notes

同类问题必须在 source evidence / ownership 层处理。有限控件背景的判断可以使用：

```text
OCR containment
finite bbox
stable local fill
outer-ring boundary delta
raw shape overlap
low-confidence media demotion
```

不得使用：

```text
literal text
theme color
app category
file name
task id
fixed coordinate
single screenshot layout
```
