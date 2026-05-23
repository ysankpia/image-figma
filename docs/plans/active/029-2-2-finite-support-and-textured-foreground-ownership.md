# M29.2.2 Finite Support And Small Textured Foreground Ownership

- 状态：completed
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

修两个 M29 Direct 左侧实验路径里的 source ownership 错误：

```text
1. low_contrast_support 必须证明是有限闭合 support，才能进入 shape replay。
2. 小型多色/高纹理前景不能因为几何像圆/椭圆就进入 shape replay。
```

第一性原则是：`bbox` 和 `geometry fit` 都不是 replay owner。`geometry fit` 只说明像矩形、圆、椭圆或线；能不能用 Figma shape 重放，还必须证明这个像素集合是低纹理、低颜色数、fill 稳定、边界简单的矢量形状。否则小头像、小图标、复杂纹理 foreground 应该走 raster foreground/icon 或保留 fallback，而不是变成纯色色块。

## Scope

包含：

- raw M29 `low_contrast_support` 增加 finite support gate。
- M29.2 shape ownership 拆开 `geometry fit` 和 `shape replay safe`。
- M29.2 blocked ownership 把小型复杂 foreground 从 `diagnostic_only` 恢复为 `raster_icon + icon_replay` 的保守候选。
- M29.5/M29 Direct 继续按 `shape -> image -> icon -> text` 顺序消费 plan，不新增语义规则。

不包含：

- 不做 SearchBar、StatusBar、Avatar、TabBar 语义 detector。
- 不处理 OCR-symbol leakage。
- 不做组件化、Auto Layout、route、插件 UI 或主线 `/api/tasks/{taskId}/dsl` 变更。
- 不把低纹理 support 改成图片裁片。

## Contract

`low_contrast_support` 只有在 bbox 能采到完整外环、内外环存在可测差异、局部 fill 稳定且包含 OCR text 与同线 foreground evidence 时，才作为 replay-safe support shape 输出。贴画布边界的 open band 没有外部像素证据，默认不能当成有限闭合 support。

M29.2 shape replay safe 条件必须基于物理可表达性：

```text
geometry fit: 像什么
shape replay safe: 能不能用一个矢量 fill/radius 表达
```

小型 circle/ellipse/badge/background 如果颜色数、纹理或边缘复杂度超过阈值，不进入 `shape_geometry`。它可以作为 `raster_icon` 进入 `icon_replay`；如果证据不足，则保留 fallback/diagnostic，不能输出错误纯色 shape。

blocked primitive 如果因为 `symbol_color_too_high`、`symbol_texture_too_high`、`symbol_edge_too_high` 或 `weak_symbol_metrics` 被 raw M29 拦下，但 bbox 小、无 OCR overlap、无 media containment，应作为 raster foreground/icon 候选恢复。它仍然不是语义图标识别，只是承认“小型复杂前景可以被裁成 raster，而不是被丢掉”。

## Acceptance

- 顶部贴边低对比 open band 不再生成 replay-safe `low_contrast_support` shape。
- 非贴边、外环完整的搜索框/输入框 support 在 light/dark theme 下仍可生成。
- 小型高颜色数/高纹理/高边缘 circle 或 ellipse 不再进入 `shape_geometry`。
- 低纹理、低颜色数的真实 badge/background 仍可 `shape_replay`。
- blocked 小型复杂 foreground 可以进入 `raster_icon + icon_replay`，底部 icon 类对象不再默认不可选。
- M29.5 plan 和 M29 Direct 继续不生成 `diagnostic_only` 可见节点。

## Validation

```bash
cd backend
uv run pytest tests/test_visual_primitive_graph.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_direct_replay.py -q
uv run pytest tests/test_region_relation_kernel.py tests/test_region_relation_graph_report.py tests/test_stable_design_cluster.py -q
uv run pytest tests/test_m30_upload_pipeline.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

这阶段修的是 owner 合同，不是视觉语义。判断依据只允许来自边界闭合、外环采样、颜色数、纹理、边缘、OCR overlap、media containment 和 bbox 尺寸。
