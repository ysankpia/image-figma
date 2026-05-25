# Bug: 底部 tab 图标在 composite media 内停留为 diagnostic

- 状态：open
- 创建日期：2026-05-25
- 影响范围：raw M29 blocked evidence、M29.2 source ownership、M29.5 replay plan、真实上传样本底部导航可编辑质量

## Summary

用户通过插件上传最新样本后，底部 tab 的文字已经被 OCR 识别并进入 `text_replay`，但对应图标没有成为可拖动/可编辑图层。artifact 显示图标不是完全没检测到，而是在 raw M29 中以 `blocked` evidence 出现，进入 M29.2 后仍被保留为 `diagnostic_only / skip`。

这不是字体识别问题，也不是 Renderer/Figma plugin 问题。问题发生在 source evidence 到 source ownership / promotion permission 的转换处：底部整条 tab bar 被保守保留为 `media_region / preserve_raster` 后，内部小图标要么以 raw M29 `blocked` fragments 出现，要么只存在于 M29.6 pixel/internal candidate 证据里。当前链路在多个地方直接用局部 gate 做最终裁决，缺少统一的 evidence consistency gate。

## Reproduction

当前复现 task：

```text
taskId = task_ba7fda4a90e9
source = backend/storage/uploads/task_ba7fda4a90e9/original.png
```

查看 artifact：

```bash
jq '[.sourceObjects[] | select(.bbox[1] > 1540 or (.bbox[1]+.bbox[3]) > 1540) | {id,bbox,visualKind,pixelOwner,replayDecision,reasons,risks,sourceEvidence}]' \
  backend/storage/upload_previews/task_ba7fda4a90e9/m29_2/source_ui_physical_graph.json
```

关键事实：

```json
{
  "id": "m292_object_0094",
  "bbox": [0, 1541, 941, 100],
  "visualKind": "media_region",
  "pixelOwner": "preserve_raster",
  "replayDecision": "image_replay",
  "risks": ["contains_internal_text", "low_confidence_media_region"]
}
```

底部 tab 文字正常：

```json
{
  "text": "首页 / 市场 / 交易 / 资产 / 我的",
  "finalReplayAction": "text_replay"
}
```

底部 tab 图标被 blocked 后停留为 diagnostic：

```json
{
  "bbox": [82, 1562, 42, 45],
  "visualKind": "unknown",
  "pixelOwner": "diagnostic_only",
  "replayDecision": "skip",
  "reasons": ["blocked_primitive"],
  "risks": ["symbol_color_too_high", "symbol_texture_too_high", "weak_symbol_metrics"],
  "sourceEvidence": {
    "blockedIds": ["blocked_029"],
    "mediaContainmentRatio": 1.0,
    "textOverlapRatio": 0.0
  }
}
```

## Root Cause

第一性原理链路：

```text
real goal:
  底部 tab 图标应作为独立 visible icon layer，可拖动，可与 OCR label 分离。

source truth:
  source PNG pixels + raw M29 connected components + OCR label boxes。

information-loss point:
  raw M29 blocked foreground -> M29.2 source ownership。

owning layer:
  M29.2 blocked foreground recovery for already-detected blocked fragments。
  M29.6 + transparent asset + M29 evidence contract + internal source promotion for raw-M29-missed internal icons。

do-not-do:
  不在 materializer / Renderer / plugin 下游补图标。
  不按“首页/市场/交易/资产/我的”文案、固定 y 坐标、文件名、颜色或 app 类型特化。
```

当前失败有两类：

```text
1. 已检测到 blocked fragments，但 M29.2 单 fragment/local gate 只问“这个碎片自己能不能 replay”。
2. raw M29 没给出完整 icon candidate，只能由 M29.6/pixel foreground evidence 补 internal candidate。
```

旧 `is_recoverable_blocked_foreground` 只允许：

```text
small foreground
recoverable blocked reasons
textOverlap < 0.20
mediaContainment < 0.80
```

这对“图标在照片/轮播/复杂 media 内”的保守策略是合理的，但对“低置信 composite media 其实是 UI control strip/tab bar”的情况过严。底部 tab 图标完全包含在 `m292_object_0094` 内，因此 `mediaContainmentRatio = 1.0`，被误挡。

正确问题不是：

```text
confidence 高不高？
```

而是：

```text
这个 fragment 或 internal candidate 是否被多种独立证据证明为一个 UI icon？
```

通用公式：

```text
IconEvidenceScore(c, M, T, G) =
  a * FragmentForegroundScore(c)
+ b * SizeCompactnessScore(c)
+ c * TextAnchorScore(c, T)
+ d * SameMediaContainmentScore(c, M)
+ e * RepetitionScore(G)
+ f * RelationGraphSupport(c, M)
+ g * TransparentAssetScore(c)
- h * TextOverlapPenalty(c, T)
- i * TextureFragmentPenalty(c)
- j * CleanupRisk(c, M)
- k * RepairCostPenalty(c)
```

决策：

```text
EvidenceScore 高 + alpha/cleanup 风险低 -> allow_visible_replay
EvidenceScore 中或缺少执行安全证据 -> report_only
EvidenceScore 低或负证据强 -> reject
```

## Fix Plan

采用无新增依赖的通用修复：

1. 保留原有恢复公式，继续禁止 text overlap、大区域、line-like、inside true image primitive 等高风险碎片。
2. M29.2 新增受限 fragment-group evidence：如果 blocked foreground 被 low-confidence composite media 包含，但它是小前景、无文字重叠，并且能和 media 内部 OCR label 建立邻近锚点关系，则恢复为 `raster_icon / icon_replay`。
3. 该锚点关系只使用几何和 OCR bbox：
   - icon center 与 label center 水平接近；
   - icon 在 label 上方或同一 control cell 内；
   - 垂直距离在 bbox 尺寸推导出的有限范围；
   - media 内存在多个 OCR label 时可形成 control-strip evidence。
4. 新增 `M29EvidenceContractReport`，把 M29.6 internal icon candidate、transparent asset alpha gate、parent media containment、text anchor/repetition 和负证据合成 `allow_visible_replay | report_only | reject`。
5. `internal_source_promotion` 只能消费 `allow_visible_replay` 的 evidence contract，不能继续直接消费局部 confidence + alpha allow。
6. M29.5 和 materializer 仍只消费 M29.2/promoted M29.2 source object 和 M29.5 cleanupTargets，不发明 owner 或 cleanup 权限。

不做：

```text
不新增 OpenCV/Pillow/SAM/ONNX 依赖
不改 DSL/API/Renderer/plugin protocol
不使用固定坐标、固定文案、文件名、主题色或行业特化
```

## Regression Guard

需要新增测试：

- low-confidence composite media 内部的小复杂 foreground，如果几何上锚定到 OCR label，应恢复为 `raster_icon / icon_replay`。
- M29.6 internal icon 只有在 evidence contract 为 `allow_visible_replay` 时才能 promotion。
- transparent asset reject / high text overlap / hero risk / missing execution support 不能 promotion。
- 与 OCR 文字重叠的 blocked foreground 仍为 diagnostic。
- 大面积 blocked foreground 仍不恢复。
- 没有 OCR label/control-strip evidence 的 media-contained blocked foreground 仍不恢复。

## Validation Evidence

待修复后补充：

```bash
cd backend
uv run pytest tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
```
