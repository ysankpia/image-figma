# 084 Go M29 AxisProjectionGroup v0 与 Layout Solver 前置结构计划

## Summary

083 已经把 Go M29 VisualTree 的结构权限收紧：`same_row` / `same_column` 只保留为 layout hint，`canContainForeground` 成为结构 parent gate，`row_group` 只能表达局部单行。084 在这个基础上补一个 containment 之后的局部投影归组层：

```text
EvidenceToken
-> RelationGraph
-> VisualGroup
-> ContainmentTree
-> AxisProjectionGroup v0
-> VisualTree
```

目标不是追求更少的 `bodyChildren`，而是在同一个可信 parent scope 内，把明显属于同一局部投影结构的 sibling 收成 `axis_projection_group`。它只表达几何结构，不表达 Button / Card / Nav / List / Grid 等语义。

## Key Changes

实现一个独立的 `AxisProjectionGroup` pass，接入顺序固定在 containment 之后：

```text
initial contains tree
-> applyVisualGroups(row_group / band_group / raster_parts_group)
-> applyContainmentTree
-> applyAxisProjectionGroups
-> refreshTreeLayouts
-> diagnostics
```

`axis_projection_group` 合同：

```text
Type: Layer
meta.synthetic: true
meta.groupKind: axis_projection_group
bbox: children union bbox
layout: absolute；children 继续使用 parent-relative layout
node types: Body / Layer / Text / Image
```

候选只来自同一个当前 parent 的 direct children。允许 `Text`、非 thin-line 的 `Image`、以及已有 `row_group` 参与；禁止 `Body`、physical background Layer、`band_group`、`raster_parts_group`、thin-line fragment、`canContainForeground=false` 的 raster parent，以及任何明显支配候选面积的大背景/raster。

v0 算法只做局部投影：

```text
按 y-center 分 row buckets。
每个 row bucket 至少 2 个有效成员，或 1 个已有 row_group。
至少 2 个 row buckets 才能形成 axis_projection_group。
总有效成员至少 4 个。
行间距必须局部连续，不能跨大空白。
至少 2 条 x-lane 在至少 2 行中重复，或 row span 左右边界高度一致。
group bbox 必须等于 children union。
Body 直下不能生成接近整页的大 band；可信非 Body scope 可更宽松。
不允许纯线段集合。
不允许两个以上大 raster/image 成员。
```

`same_row` / `same_column` / `adjacent_*` 只能作为 debug/support relation 引用。没有几何投影通过时，relation 不能单独生成 group。

## Test Plan

Go 单测：

```bash
go test ./services/backend-go/...
```

必须覆盖：

```text
多行 2x2 / 3x3 文本或图文矩阵生成 axis_projection_group。
单行 3 个局部节点仍生成 row_group，不生成 axis_projection_group。
已有多个 row_group 在同一 parent 下可以被 axis_projection_group 包住。
same_row / same_column relation 单独存在但几何不对时不能生成 axis_projection_group。
大 banner：两个大 raster + 多行 text 不能生成 axis_projection_group。
长页面 same_column 链不能跨大空白生成 axis_projection_group。
1-2px 线段集合不能生成 axis_projection_group。
canContainForeground=false 的 raster 不能因为 axis projection 变成 parent/background Layer。
Text 数量不减少，Text 不变 Image。
VisualTree 节点类型仍只包含 Body / Layer / Text / Image。
synthetic group bbox 等于 children union。
parent-relative layout 不回退。
```

小样本验证：

```bash
rm -rf services/backend-go/tmp/batch-smoke-containment-limit2
go run ./services/backend-go/cmd/m29batch \
  --input-dir '/Users/luhui/Downloads/m29' \
  --out services/backend-go/tmp/batch-smoke-containment-limit2 \
  --ocr-provider baidu_ppocrv5 \
  --limit 2
```

验收只看结构合同，不看 `bodyChildren` 是否变少：

```text
2 completed, 0 failed
case ...-1 Text == 66
case ...-10 Text == 60
非法节点类型 0
case ...-1 不出现整块 hero/banner axis_projection_group
case ...-1 不出现 thin-line axis_projection_group
case ...-10 token_0063 仍是 Image，不成为 Layer/background parent
visual_tree_preview_sheet.png 可审计
```

最终检查：

```bash
git diff --check
git status --short --branch
```

## Assumptions

```text
继续在 feat/final-m29-visual-compiler 分支。
084 只修 Go M29 实验链路，不碰 Python 正式 /api/upload-preview。
不接 DSL、Renderer、Figma plugin。
不引入 Codia runtime schema。
不引入 Button/Card/Search/Carousel/Nav/Tab/List/Icon/Vector/Component。
不使用文件名、文案、品牌、颜色主题、固定坐标、task id 特化。
```
