# ADR: Treat M29 As Pixel Topology And Ownership Graph

- 状态：accepted
- 日期：2026-05-23

## Context

M29 Direct Replay 和后续 M29.2 讨论暴露了一个更底层的架构边界：项目不能继续把 M29 理解成 UI component detector。

错误抽象是：

```text
识别 SearchBar / Card / TabBar / Banner
```

这会把系统带向样图特化。每出现一个黑条、搜索框、轮播图、商品卡、底栏，就会新增一个命名规则，最后得到的是一堆脆弱 detector，而不是通用截图到设计稿系统。

M29 的事实输入不是设计师的原始 Figma 文件，而是一张已经压扁的 PNG。PNG 是一个像素全集；原始图层、组件名、Auto Layout 和设计语义已经丢失。恢复过程的第一步必须是建立可审计的像素集合、集合关系和最终像素归属，而不是命名业务 UI 对象。

## Decision

M29 被定义为从扁平 PNG 到可编辑设计稿之前的像素拓扑与归属层。

M29 的核心合同是：

```text
source PNG + OCR boxes
-> visual primitive graph
-> relation graph
-> pixel ownership decision
-> replay-safe evidence
```

M29 输出的基本单位不是 UI component，而是一个可追溯的像素集合：

```text
node:
  bbox / mask / metrics / sourceEvidence

edge:
  disjoint
  overlaps
  contains
  contained_by
  near_equal
  near
  aligned
  repeated
  protects
  conflicts

ownership:
  editable_text
  raster_media
  raster_icon
  shape_geometry
  fallback_only
  diagnostic_only
```

每两个重要区域优先用集合关系描述：

```text
A ∩ B = ∅                      # disjoint
A ∩ B != ∅, A !⊂ B, B !⊂ A     # overlaps
A ⊂ B                          # contained_by
B ⊂ A                          # contains
A ≈ B                          # near_equal / same evidence from different sources
A and B are spatially related   # near / aligned / repeated
```

DSL replay 只能消费已经完成 ownership 裁决的对象。未裁决对象只能进入 diagnostic/report/overlay，不能直接成为可见 Figma layer。

## Pixel Ownership Invariant

M29 direct path 必须遵守一个硬不变量：

```text
同一块 source foreground evidence pixel / replay foreground pixel 只能有一个 replay owner。
```

这不是说 Figma layer 的 bbox 不能重叠。背景 shape 和 child text/image/icon 可以在 Figma 中空间重叠，因为它们表达的是不同 source evidence：背景像素归 shape，文字笔画像素归 text。

真正禁止的是同一块源图前景证据被多个可见 replay layer 重复表达。

例子：

```text
T = OCR text bbox
R = copied raster image asset bbox
```

如果 `T ⊂ R` 且 `T` 被裁决为 `editable_text`，那么 copied `R` asset 中对应的 `T` 局部像素必须被清掉，否则同一文字会同时存在于 editable text 和 raster image 中，形成重影。

如果 `T ⊂ R` 但 `T` 被裁决为 `raster_media` / `preserve_raster_text`，那么不能生成 editable text，也不能擦除 `R`。艺术字、商品图内部装饰字、banner 内部标题等都只能通过 ownership 证据决定，不允许靠元素名硬编码。

## Consequences

M29 后续阶段必须优先增强：

```text
像素集合分解
集合关系图
owner 唯一性裁决
replay safety
```

而不是优先增强：

```text
SearchBar detector
ProductCard detector
BottomNav detector
Banner detector
```

允许后续阶段从 relation graph 自然产生弱 `roleHint`，例如：

```text
edge_bar
repeated_item
media_text_group
icon_label_pair
content_block
```

但这些 role hint 不能作为 M29 truth source，也不能绕过 pixel ownership 和 replay safety。

M39/M40 类后处理不能修正 M29 源头 ownership 错误。商品图重影、文字不可编辑、icon 碎片化、fallback 重复像素这类问题都必须优先回到 M29/M29 direct 的像素拓扑和归属层解决。

## Boundaries

- 不在 M29 写固定坐标、固定文本、固定业务页面或固定 UI 类名规则。
- 不让 OCR、模型、UIC、Figma MCP 或单个 primitive 直接成为 DSL 真值。
- 不把模型输出直接 replay；模型最多提出 candidate region，最终仍由 relation graph 和 ownership gate 裁决。
- 不把 M29 relation graph 等同于 Figma hierarchy、component 或 Auto Layout。
- 不因为当前样图有黑条、搜索框、轮播图、商品图而增加单点 detector。

## Follow-Up Path

后续路线按这个顺序推进：

```text
M29.3.0 Region Relation Kernel
-> M29.2.1 Pixel Ownership Consistency
-> M29.3.1 Region Relation Graph Report
-> M29.4 Stable Design Cluster
-> M29.5 Replay Engine V2
-> M29 default path decision
```

M29.3.0 是无状态几何 kernel，只负责描述两个区域的 primary set relation 和 secondary geometry relations。M29.2.1 消费这个 kernel 消除 copied raster asset、editable text 和 fallback 之间的重复 ownership。M29.3.1 才把所有 source regions 的关系输出成 graph/report。组件化、Auto Layout 和语义命名必须在这些阶段之后。

组件化的底层定义见 [0069-base-componentization-on-set-relation-graph-isomorphism.md](0069-base-componentization-on-set-relation-graph-isomorphism.md)。组件化不是 raw pixel dedupe，而是在已裁决 ownership 的集合关系图上寻找 repeated near-isomorphic cluster graph，再抽象出 template、slots、instances 和 overrides。
