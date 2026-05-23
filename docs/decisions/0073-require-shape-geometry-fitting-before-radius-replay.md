# ADR: Require Shape Geometry Fitting Before Radius Replay

- 状态：accepted
- 日期：2026-05-24

## Context

M29 Direct 的低对比 support 修复让搜索框背景能进入左侧 compare 画布，但也暴露了一个更底层的问题：系统把候选区域的 `bbox` 当成了 shape 本身。

错误抽象是：

```text
candidate bbox
-> shape
-> radius = height / 2
```

`bbox` 只是像素集合的外接矩形，不是 shape geometry。一个 bbox 内部可能对应：

```text
rect
rounded_rect
pill
circle
ellipse
line
ring / outline
polygon-ish
irregular / unknown
```

这些对象不能只靠 `width`、`height` 和一条粗糙半高公式判断。搜索框、按钮、标签、头像、顶部 chrome band 都可能有相似 bbox，但它们的像素占用、角部缺失、边界曲率和填充模式不同。

当前问题的典型表现是：`low_contrast_support` 可以从像素里提出候选 bbox，但它没有证明这个候选是圆角矩形或 pill，就直接给出半高 radius。这样会把某些贴边稳定背景 band 或弱渲染区域错误 replay 成带大圆角的可见 shape。

## Decision

M29 后续必须把 shape replay 拆成两步：

```text
candidate region / bbox
-> shape geometry fit
-> replay-safe shape style
```

`shape_geometry` owner 不能只表示“有一个 bbox”。它必须逐步带上可审计的几何拟合结果：

```json
{
  "geometry": {
    "kind": "rect|rounded_rect|pill|circle|ellipse|line|unknown",
    "confidence": "high|medium|low",
    "params": {
      "radius": 0
    },
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

第一版 shape geometry fit 只需要覆盖最常见、可数学验证的物理形状：

```text
rect
rounded_rect / pill
circle / ellipse
line
unknown
```

判断应基于像素集合、local mask、occupancy map 或等价的区域采样，而不是 UI 语义名。

基本数学约束：

```text
rect:
  bbox 内 fill ratio 高，四角不缺失。

rounded_rect:
  中心横竖区域填充稳定；
  四角存在稳定缺失；
  四角缺失边界近似 quarter circle。

pill:
  rounded_rect 的特殊情况；
  radius 接近 min(width, height) / 2；
  左右或上下两端近似半圆。

circle:
  width ≈ height；
  fill area ≈ pi * r^2；
  边界到中心距离稳定。

ellipse:
  fill area ≈ pi * a * b；
  归一化边界近似 x^2/a^2 + y^2/b^2 = 1。

line:
  一维长条，短边很小，低纹理。

unknown:
  拟合误差高或证据不足。
```

`low_contrast_support` 只负责提出候选区域，不再被视为最终 shape geometry truth。只有 geometry fit 证明该候选是 `rounded_rect` 或 `pill` 时，M29 Direct 才能 replay `style.radius`。如果 fit 失败，候选应降级为 `rect`、`fallback_only` 或 `diagnostic_only`，而不是硬塞半高 radius。

## Consequences

- `bbox` 和 `shape geometry` 的边界被明确分开，避免把外接矩形当作设计对象。
- 圆角、胶囊、圆形、椭圆等样式参数必须来自像素几何证据，而不是从宽高直接猜。
- 顶部 chrome band、弱渲染 PC 区域、搜索框、按钮和头像不再靠业务名区分，而靠 mask/occupancy 的数学拟合区分。
- 这不是 SearchBar、Avatar、TabBar 或 Card detector；它是 M29 source-level physical geometry 的基础层。
- 旧的 `low_contrast_support` half-height radius 只是临时近似，不能作为 shape style 真值源。

## Follow-Up

新增后续阶段应命名为：

```text
M29 Shape Geometry Fit
```

该阶段应先做 raw M29 node `geometry` metadata，再接入 ownership/replay。实现前必须覆盖：

```text
rect vs rounded_rect
rounded_rect vs pill
circle vs ellipse
shape candidate vs page-edge/background band
unknown fallback
```

M29 Direct 的 shape radius replay 应消费 `geometry.params.radius`，而不是直接消费 bbox-derived radius。
