# M29 Shape Geometry Fit Before Radius Replay

- 状态：completed
- 创建日期：2026-05-24
- 负责人：未指定

## Goal

修掉 M29 Direct 里把 `bbox` 当成 shape 的错误抽象。

正确链路是：

```text
candidate region / bbox
-> shape geometry fit
-> replay-safe shape style
```

`bbox` 只是外接矩形。圆角、胶囊、圆形、椭圆和线条必须由像素占用、角部缺失、边缘填充和 mask 拟合证明，不能由 `height / 2` 直接猜。

## Scope

包含：

- raw M29 shape node 增加 `geometry` metadata。
- connected component shape 用已有 mask 拟合 `rect / circle / ellipse / line / unknown`。
- `low_contrast_support` 用局部 fill occupancy 拟合 `rect / rounded_rect / pill / unknown`。
- M29 Direct shape replay 只在 `geometry.kind` 支持 radius 且 confidence 不是 `low` 时写 DSL `style.radius`。
- 移除 `low_contrast_support` 的 bbox-derived half-height radius。

不包含：

- 不做 SearchBar、StatusBar、Avatar、TabBar 语义规则。
- 不做 OCR-symbol leakage cleanup。
- 不处理头像和底部 tab 小型纹理 ownership。
- 不做复杂 vector tracing、贝塞尔或多边形拟合。
- 不改主线 `/api/tasks/{taskId}/dsl`、Renderer、插件 UI 或 API route。

## Shape Contract

raw M29 shape node 可以带：

```json
{
  "geometry": {
    "kind": "rect|rounded_rect|pill|circle|ellipse|line|unknown",
    "confidence": "high|medium|low",
    "params": { "radius": 32 },
    "metrics": {
      "fitError": 0.0,
      "centerFillRatio": 0.0,
      "cornerMissingRatio": 0.0,
      "edgeFillRatio": 0.0
    },
    "evidence": ["mask_fit", "corner_occupancy", "stable_fill"]
  }
}
```

`style.radius` 只能来自 `geometry.params.radius`。没有 geometry evidence 时，shape replay 只能输出 fill，不能凭 bbox 猜 radius。

## Acceptance

- 顶部 chrome/status-like band 即使被检测成 `low_contrast_support`，也不能因为 bbox 半高被 replay 成大圆角条。
- 真实 rounded support 通过角部 occupancy 证明后，仍能输出圆角 shape。
- 普通 rect support 输出 `geometry.kind=rect`，不带 radius。
- circle / ellipse connected component 输出对应 geometry。
- 不规则或弱证据形状输出 `unknown`，不带 radius。
- M29.2 fallback path 和 M29.5 plan path 对 shape radius 的消费一致。

## Validation

```bash
cd backend
uv run pytest tests/test_visual_primitive_graph.py tests/test_m29_direct_replay.py tests/test_source_ui_physical_graph.py -q
uv run pytest tests/test_m29_replay_plan.py tests/test_region_relation_kernel.py tests/test_region_relation_graph_report.py tests/test_stable_design_cluster.py -q
uv run pytest tests/test_m30_upload_pipeline.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

- `low_contrast_support` 只提出候选区域，不再是真正 shape geometry truth。
- 这不是更复杂的特化规则，而是把缺失的数学层补回来：像素集合先拟合几何，再进入 replay。
