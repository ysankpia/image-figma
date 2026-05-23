# M29 Text Support Background Source Contract

- 状态：completed
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

修复 `#日本旅行`、`#北京探店` 这类标签文字背后的浅色 pill/background 丢失问题。

正确的源对象不是“一个 hashtag 文本”，而是：

```text
T = text bbox
S = text support background bbox
```

这阶段目标是让 raw M29 先把 `S` 固定成 source-level support shape，再由 M29.2、M29.0.5、M30 和 M29 Direct 消费这个源头证据。不能在 M30 或 Renderer 里按 `#`、中文内容、粉色、padding 去伪造背景。

## Scope

包含：

- raw M29 新增 `text_support_background` detector。
- detector 只使用 bbox、面积比例、外环采样、颜色数、纹理、边界差异和 media overlap 证据。
- M29.0.2/M29.0.3/M29.0.7/M29.0.5 透传 support shape 的 source subtype/reasons。
- M29.2 将 `text_support_background` 归入 replay-safe `control_background`。
- M30 只允许 source-proven support shape 绕过普通 text-overlap 风险。
- M29 Direct simple shape replay whitelist 消费 `text_support_background` 的 raw geometry/radius/fill。
- 增加 raw/source ownership/materialization/direct replay 回归测试。

不包含：

- 不新增 hashtag detector。
- 不用 `#日本旅行`、`#北京探店`、中文语义或固定粉色作为判断条件。
- 不全局放宽 `safe_shape_text_overlap_max`。
- 不新增组件化、Auto Layout、全局优化、Figma Component/Instance。
- 不从 text bbox 扩 padding 伪造 pill。

## Contract

`text_support_background` 必须满足：

```text
textContained = area(T ∩ S) / area(T) >= 0.90
1.15 <= area(S) / area(T) <= 4.00
S.width / S.height >= 1.8
texture(S) <= low_contrast_support texture gate
colorCount(S) <= low_contrast_support color gate
four outer ring samples exist
min boundary delta >= low_contrast_support min edge delta
candidate does not overlap accepted media/image region
```

输出 raw M29 node：

```text
type = shape
subtype = text_support_background
source = text_support_background_detector
reasons includes:
  text_support_background_region
  stable_local_fill
  contains_text_evidence
  finite_outer_ring
style.fill = sampled support fill
geometry = fit_low_contrast_support_geometry(...)
```

M29.2 owner：

```text
visualKind = control_background
pixelOwner = shape_geometry
replayDecision = shape_replay
```

M30 materialization：

```text
source-proven text_support_background / low_contrast_support:
  can materialize below text despite text overlap

ordinary shape_candidate with contains_text/text_overlay_shape:
  still skipped as unsafe_text_overlap
```

## Acceptance

- 浅色 rounded pill + 红色 tag text + 无侧边 icon/foreground 时，raw M29 输出 `text_support_background`。
- 输出 geometry 是 `pill` 或 `rounded_rect`，且 fill 来自 support 像素采样。
- 纯页面文字不创建 `text_support_background`。
- 纹理卡片/media 上的文字不创建 `text_support_background`。
- 候选区域主要落在已接受 media/image 内时，不创建 `text_support_background`。
- 贴边 open band 因缺少完整外环不成为 replay-safe support。
- M29.0.2 到 M29.0.5 保留 support shape lineage，不被 text-noise ownership gate 吃掉。
- M30 物化 source-proven support shape，且 shape 在 text 下方。
- 普通 text-overlap shape 仍然被 `unsafe_text_overlap` 拦下。
- M29 Direct 使用 raw geometry fit 的 radius，不从 bbox 半高猜 radius。

## Validation

```bash
cd backend
uv run pytest tests/test_visual_primitive_graph.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_evidence_grounded_dsl_materialization.py tests/test_m29_direct_replay.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_m30_upload_pipeline.py -q
uv run pytest tests/test_text_masked_media_audit.py tests/test_visual_evidence_normalization.py tests/test_text_visual_ownership_gate.py tests/test_text_aware_visual_object_refinement.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

第一性原则：背景丢失不是样式问题，是 source owner 丢失问题。能在 raw/source 层证明的 support，必须带着 subtype、reasons、geometry 和 fill 穿过后续链路；不能让 M30 猜一个新背景。
