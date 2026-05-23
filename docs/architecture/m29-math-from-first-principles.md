# M29 数学推演：从一个矩形框开始

这份文档给只学过初中数学、但能理解工程问题的人读。它不替代 [M29 实验链路数学合同](m29-experimental-mathematical-contract.md)。那份合同回答“代码现在怎么算”；本文回答“为什么要这么算”。

全文只用最基础的东西：坐标、加减乘除、面积、比例。目的不是证明 M29 已经数学完备，而是把当前 M29 的正确抽象讲清楚：

```text
先看像素和 OCR 证据；
再判断这些证据归谁所有；
再判断对象之间的几何关系；
再收集弱结构线索；
最后才决定哪些东西能画进 M29 Direct 实验 DSL。
```

本文里的内容分三类：

```text
当前代码已经实现：本地 M29 实验链路里已经有的合同或行为。
当前只是启发式阈值：工程上可用，但不是数学定理。
未来可以升级：方向合理，但现在没有实现。
```

## 1. 为什么从矩形开始

截图上的按钮、文字、图片、图标，到了程序里第一步都要变成一个框。这个框叫 `bbox`。

公式：

```text
B = [x, y, w, h]
```

大白话：

```text
x = 左边离画布左边多远
y = 上边离画布上边多远
w = 这个框有多宽
h = 这个框有多高
```

小数字例子：

```text
B = [10, 20, 100, 40]
```

意思是：

```text
左边 x = 10
上边 y = 20
宽 w = 100
高 h = 40
```

右边界和下边界只是加法：

```text
x2 = x + w = 10 + 100 = 110
y2 = y + h = 20 + 40 = 60
```

面积只是宽乘高：

```text
area = w * h = 100 * 40 = 4000
```

中心点也只是加一半：

```text
cx = x + w / 2 = 10 + 100 / 2 = 60
cy = y + h / 2 = 20 + 40 / 2 = 40
```

当前代码已经实现：

```text
bbox_x2
bbox_y2
bbox_area
center_x
center_y
```

这些基础函数看起来简单，但它们是后面所有关系判断的地基。地基如果漂，后面谈组件、布局、优化器都没有意义。

## 2. 两个矩形怎么比较

先从一维数轴看。两个线段是否重叠，只要看：

```text
左边最大的点 < 右边最小的点
```

例如：

```text
A 的 x 范围：10 到 60
B 的 x 范围：40 到 100

左边最大的点 = 40
右边最小的点 = 60
40 < 60，所以 x 方向重叠 20
```

二维矩形只是把这个逻辑在 x 和 y 两个方向各做一次。

公式：

```text
重叠宽度 = min(A右边, B右边) - max(A左边, B左边)
重叠高度 = min(A下边, B下边) - max(A上边, B上边)
重叠面积 = 重叠宽度 * 重叠高度
```

如果宽度或高度小于等于 0，就没有真正相交。

小数字例子：

```text
A = [10, 10, 50, 30]  => x:10..60, y:10..40
B = [40, 20, 60, 20]  => x:40..100, y:20..40
```

x 方向：

```text
min(60,100) - max(10,40) = 60 - 40 = 20
```

y 方向：

```text
min(40,40) - max(10,20) = 40 - 20 = 20
```

重叠面积：

```text
20 * 20 = 400
```

这能推导出几种基础关系。

完全包含：

```text
A contains B
```

大白话：

```text
B 整个都在 A 里面。
```

相交：

```text
A overlaps B
```

大白话：

```text
两个框有一部分压在一起，但谁也没有完整包住谁。
```

不相交：

```text
A disjoint B
```

大白话：

```text
两个框完全分开。
```

判断重复时，只看“差几个像素”很粗糙。更好的办法是看两个框的重叠面积占合并面积的比例，这就是 IoU。

公式：

```text
IoU = 重叠面积 / (A面积 + B面积 - 重叠面积)
```

小数字例子：

```text
A 面积 = 100
B 面积 = 100
重叠面积 = 90

合并面积 = 100 + 100 - 90 = 110
IoU = 90 / 110 = 0.818
```

大白话：

```text
IoU 越接近 1，两个框越像同一个东西。
IoU 越接近 0，两个框越不像同一个东西。
```

当前代码已经实现：

```text
bbox_intersects
bbox_contains
bbox_iou
bbox_gap_distance
```

当前只是启发式阈值：

```text
M29.2 去重使用 IoU >= 0.88
M29.4 cluster 去重使用 bbox IoU >= 0.92
```

这些数是工程合同，不是自然定律。它们的价值在于全链路统一，而不是每个文件自己猜一个数字。

## 3. 为什么只看像素差不够

同样是 5px，含义完全不同。

小数字例子：

```text
小图标宽 10px，偏 5px。
偏差占 50%。

大卡片宽 500px，偏 5px。
偏差只占 1%。
```

所以几何判断不能只看绝对像素，还要看比例。

两个框的包含比例：

```text
A 在 B 里的比例 = A 和 B 的重叠面积 / A 自己的面积
B 在 A 里的比例 = A 和 B 的重叠面积 / B 自己的面积
```

小数字例子：

```text
A 是文字框，面积 100。
B 是图片框，面积 1000。
A 和 B 重叠了 95。
```

那么：

```text
A 在 B 里的比例 = 95 / 100 = 95%
B 在 A 里的比例 = 95 / 1000 = 9.5%
```

大白话：

```text
文字 A 基本都在图片 B 里。
但图片 B 只有一小部分被文字 A 覆盖。
```

所以这不是 `near_equal`。这是 `A contained_by B`。

当前代码已经实现：

```text
near_equal if A在B里 >= 90% and B在A里 >= 90%
contains if B在A里 >= 95%
contained_by if A在B里 >= 95%
overlaps if 重叠面积 > 0
disjoint otherwise
```

为什么 `contains` 和 `contained_by` 不能混：

```text
图片 contains 文字
文字 contained_by 图片
```

这是同一个空间事实的两个方向。方向如果丢了，后面 cleanup 会搞错：到底是擦图片里的文字，还是擦文字里的图片？

## 4. 为什么先判 pixel owner，不先猜组件

很多错误来自一个坏习惯：看到形状像什么，就立刻把它画成什么。

小例子：

```text
一个头像是圆的。
它的 bbox 很圆，mask 也像圆。
```

如果只看形状，会得出：

```text
geometry fit = circle
```

但头像里面有很多颜色、纹理、边缘。它不应该被画成一个纯色圆。它应该保留成 raster 图片或 icon。

所以 M29 必须分三层问题：

```text
geometry fit: 这个 mask 像什么？
pixel ownership: 这些像素应该归谁？
replay decision: 能不能画成可编辑节点？
```

大白话：

```text
像圆，不等于能画成圆。
像文字，不等于文字一定可编辑。
像卡片，不等于已经恢复出组件。
```

当前 M29.2 的 owner 主要有：

```text
editable_text
preserve_raster
raster_icon
shape_geometry
fallback_only
diagnostic_only
```

解释：

```text
editable_text:
  OCR 文字可靠，背景相对稳定，可以画成可编辑文字。

preserve_raster:
  应该保留成图片，里面可能有复杂纹理、艺术字或展示图。

raster_icon:
  小型复杂前景，适合裁成图片 icon，不适合画成纯色 shape。

shape_geometry:
  低纹理、低颜色数、边缘简单，适合画成 Figma shape。

fallback_only:
  只留在 fallback 里，不单独 materialize。

diagnostic_only:
  只做诊断，不输出可见节点。
```

当前代码已经实现：

```text
M29.2 source object 会写 visualKind、pixelOwner、replayDecision、confidence、reasons、risks。
```

核心边界：

```text
visualKind 是“看起来像什么”。
pixelOwner 是“像素归谁”。
replayDecision 是“能不能重放出去”。
```

这三个东西不能合并成一个标签。

## 5. 为什么 shape replay 要防守

Figma shape 最适合表达简单东西：

```text
纯色背景
分割线
按钮底板
低纹理卡片背景
```

它不适合表达：

```text
头像
复杂图标
渐变图片
带纹理的商品图
多色贴纸
```

所以 shape replay 要防守。

当前 safe shape 的直觉：

```text
颜色少
纹理低
边缘不复杂
不压住文字
```

当前代码里的门禁可以用大白话理解成：

```text
如果 textOverlap 太高，别画 shape，可能会盖住文字。
如果 colorCount 太高，别画 shape，它不是简单纯色。
如果 textureScore 太高，别画 shape，它可能是图片或复杂材质。
如果 edgeScore 太高，别画 shape，它边缘太复杂。
```

小数字例子：

```text
按钮背景：
  colorCount = 3
  textureScore = 0.02
  edgeScore = 0.05
  textOverlap = 0
  => 可以考虑 shape_geometry

头像：
  colorCount = 80
  textureScore = 0.30
  edgeScore = 0.45
  textOverlap = 0
  => 不该 shape_geometry，更像 raster_icon 或 image
```

当前代码已经实现：

```text
safeShape 由 textOverlap、colorCount、textureScore、edgeScore 控制。
```

当前只是启发式阈值：

```text
colorCount <= 12
textureScore <= 0.14
edgeScore < 0.28
textOverlap < 0.45
```

这些阈值能表达工程意图，但不能说已经证明了准确率。它们要靠回归样本继续校准。

## 6. 为什么 low-contrast support 要证明闭合

有些输入框或搜索框背景很浅，和页面背景差不多。肉眼能看出来，程序不一定容易看出来。

这类区域叫低对比 support。它的问题不是“识别搜索框语义”，而是：

```text
有没有一个真实存在的、闭合的、低纹理支撑区域？
```

为什么要看外环？

小例子：

```text
一个输入框内部颜色是 245,245,245。
外面页面背景是 255,255,255。
差值虽然小，但四周都有边界证据。
```

这说明它可能是一个闭合 support。

但如果 bbox 贴着画布边缘：

```text
上边没有外部像素。
左边没有外部像素。
```

那程序无法证明它是一个闭合框。它也可能只是页面顶部的一整条背景带。

所以当前代码要求：

```text
bbox 四周都能采到外环像素。
```

大白话：

```text
没有外部像素，就不能证明边界存在。
不能证明边界存在，就不能把它当成可重放 shape。
```

当前代码已经实现：

```text
low_contrast_support 要有完整外环、稳定填充、内外颜色差、OCR text 和同线 foreground evidence。
```

当前只是启发式阈值：

```text
texture、colorCount、edge delta、宽高比例、面积比例等门槛。
```

这些门槛的目标是防止把整条 open band 错画成输入框。

## 7. 为什么需要统一 region relation

如果每个文件都自己写一套“差不多挨着”“差不多包含”，系统一定会乱。

比如同一对框：

```text
文件 A 认为它们 near。
文件 B 认为它们 disjoint。
文件 C 认为它们是重复。
```

后果就是 M29.2、M29.4、M29.5 和 cleanup 互相打架。

所以需要一个统一关系内核：

```text
relation(A, B) -> {
  primarySetRelation,
  secondaryGeometryRelations,
  metrics
}
```

`primarySetRelation` 是集合关系：

```text
near_equal
contains
contained_by
overlaps
disjoint
```

大白话：

```text
两个框到底是几乎一样、谁包住谁、部分相交，还是完全分开。
```

`secondaryGeometryRelations` 是几何辅助关系：

```text
near
left_of
right_of
above
below
aligned_left
aligned_center_x
aligned_right
aligned_top
aligned_center_y
aligned_bottom
same_width
same_height
same_size
```

大白话：

```text
两个框是不是靠近、谁在谁左边、是否对齐、尺寸是否相似。
```

`metrics` 是可审计数字：

```text
intersectionArea
leftInRightRatio
rightInLeftRatio
gapDistance
nearThreshold
alignmentThreshold
```

小例子 1：文字在图片上。

```text
文字 T 面积 100。
图片 I 面积 1000。
重叠 98。

T 在 I 里 = 98%
I 在 T 里 = 9.8%
=> T contained_by I
```

小例子 2：两个重复框。

```text
A 面积 100。
B 面积 102。
重叠 95。

A 在 B 里 = 95%
B 在 A 里 = 93%
=> near_equal
```

小例子 3：两个卡片左右排列。

```text
A 的右边界 <= B 的左边界
两者中心 y 很接近
两者宽高相似
=> left_of + aligned_center_y + same_size
```

当前代码已经实现：

```text
backend/app/region_relation_kernel.py 是纯 bbox relation utility。
```

边界：

```text
region relation 不懂 OCR。
region relation 不懂 Figma。
region relation 不懂组件。
它只负责 bbox 数学。
```

## 8. 为什么 cluster 只是弱证据

看到几个框排成一行，只能说明：

```text
这些框有行排列迹象。
```

不能直接说明：

```text
这是一个 Card 组件。
这是一个瀑布流。
这是一个 TabBar。
这是一个 Auto Layout。
```

因为组件需要更多证据：

```text
结构是否重复
角色是否一致
内容槽位是否一致
父子关系是否稳定
重放后是否能编辑
```

当前 M29.4 能给出的只是弱结构提示：

```text
row_like
column_like
background_anchor_like
repeated_item_like
```

大白话：

```text
row_like:
  看起来像一行。

column_like:
  看起来像一列。

background_anchor_like:
  看起来像有背景或锚点关系。

repeated_item_like:
  看起来有重复尺寸或重复结构。
```

当前代码事实：

```text
M29.4 是 report-only。
它不改 DSL。
它不创建 asset。
它不创建 visible node。
它不创建 Figma Component/Instance。
```

必须明确的一点：

```text
media_text_group_like 目前不是实际产出路径。
```

代码类型里有这个名字，但当前 `role_hint_for_pattern()` 不会产出它。不能因为模型或文档里出现这个词，就说系统已经识别了图文卡片组件。

## 9. 为什么 replay plan 是最后一道闸门

识别出来，不等于能画出去。

中间还要回答几个问题：

```text
是不是重复证据？
应该排在哪个层级？
节点数量会不会爆？
能不能擦 fallback？
能不能擦 copied image asset？
风险有没有记录？
```

这就是 M29.5 replay plan 的角色。

去重：

```text
如果两个 source object near_equal，
保留 replay priority 更高的那个。
```

大白话：

```text
同一块像素不要画两遍。
```

层级：

```text
shape -> image -> icon -> text
```

大白话：

```text
背景先画。
图片再画。
小图标再画。
文字最后画。
```

如果顺序反了，图片会盖住文字。

节点预算：

```text
maxVisibleNodes = 260
```

大白话：

```text
不要因为检测出太多碎片，把 Figma 画布变成不可用的一堆小节点。
```

cleanup 授权：

```text
text_replay 可以擦 fallback。
text_replay 只有在 relation/plan 允许时，才能擦 copied image asset 里的同一块文字像素。
```

大白话：

```text
不是看到文字就乱擦图。
只有证明这个文字属于那个图片内部，才允许擦图片副本。
```

当前代码已经实现：

```text
M29.5 不创建 visible node。
M29.5 只输出 plan。
M29 Direct Replay 消费 plan 后才 materialize flat DSL nodes。
```

## 10. 为什么现在不能直接上全局优化

全局优化听起来很高级，但它有一个前提：

```text
输入对象必须基本正确。
```

如果输入对象是错的：

```text
头像被当成 shape。
文字被当成图片。
图标被丢进 diagnostic_only。
relation 把 contained_by 判断反了。
cleanup 擦错 copied image asset。
```

那么优化器不会救它。优化器只会把错误排得更整齐。

核心句：

```text
如果输入对象是错的，优化器只会把错误排得更整齐。
```

未来可以升级的数学方向：

```text
layout energy:
  用一个分数比较 row、column、grid、masonry 哪个解释更好。

graph isomorphism:
  判断两个子图是不是同一种重复结构。

pixel ownership conservation:
  让每个源像素都有明确 owner，避免重复拥有或错误擦除。
```

但这些现在不是 M29 Direct 的当前事实。当前 M29 正确顺序是：

```text
先稳 source object。
再稳 pixelOwner。
再稳 region relation。
再稳 replay plan。
最后才谈 layout 和 component。
```

## 11. 一个完整小例子

假设页面上有两个图文卡片和一个小图标：

```text
图片框 A  = [10, 10, 100, 80]
图片框 B  = [130, 10, 100, 80]
文本框 T1 = [20, 95, 80, 20]
文本框 T2 = [140, 95, 80, 20]
小图标 I = [15, 15, 10, 10]
```

先算面积：

```text
area(A) = 100 * 80 = 8000
area(B) = 100 * 80 = 8000
area(T1) = 80 * 20 = 1600
area(I) = 10 * 10 = 100
```

再看 A 和 B：

```text
A 的 x 范围：10..110
B 的 x 范围：130..230
它们不相交。
A 在 B 左边。
它们 y 范围相同，中心 y 相同。
宽高相同。
```

关系可以表达为：

```text
primarySetRelation = disjoint
secondaryGeometryRelations 包含 left_of、aligned_center_y、same_size
```

大白话：

```text
这两个图片框看起来像一行里的两个同尺寸项目。
```

再看 T1 和 A：

```text
T1 = [20, 95, 80, 20]
A = [10, 10, 100, 80]
```

A 的 y 范围是 `10..90`，T1 的 y 范围是 `95..115`。它们没有相交，T1 在 A 下方，距离 5px。

大白话：

```text
T1 很可能是 A 的标题或说明文字。
```

但当前 M29 不能因为这个就直接创建 Card 组件。它只能说：

```text
有几何关系证据。
可能支持后续 cluster。
不等于已经恢复出组件。
```

再看小图标 I 和 A：

```text
I = [15, 15, 10, 10]
A = [10, 10, 100, 80]
```

I 完整在 A 里：

```text
I 在 A 里的比例 = 100 / 100 = 100%
A 在 I 里的比例 = 100 / 8000 = 1.25%
```

所以：

```text
I contained_by A
A contains I
```

但 I 应该怎么 replay，不能只看它在 A 里面。还要看 pixel owner：

```text
如果 I 是简单纯色圆点：
  可能 shape_geometry。

如果 I 是复杂多色图标：
  应该 raster_icon。

如果 I 是图片内部装饰：
  可能 preserve_raster。
```

最后看整个双栏：

```text
A 和 B same_size、aligned_center_y。
T1 和 T2 same_size、aligned_center_y。
A/T1 与 B/T2 有重复结构迹象。
```

这能支持 M29.4 的弱结构报告：

```text
row_like
repeated_item_like
background_anchor_like
```

但还不能输出：

```text
React Card component
Tailwind grid
Figma Component
Auto Layout
响应式 Masonry
```

原因很简单：

```text
几何相似只是证据。
组件是更强的语义承诺。
```

M29 当前要做的是把证据链守住，不是提前承诺语义。

## 12. 读这份文档应该带走什么

第一，M29 的起点不是组件，而是 bbox。

第二，bbox 之间的关系可以用面积、比例和方向讲清楚。

第三，`geometry fit`、`pixelOwner`、`replayDecision` 是三个不同问题，不能合并。

第四，shape replay 必须防守。复杂像素宁可保留 raster，也不要错画成纯色 shape。

第五，M29.4 cluster 是弱证据，不是组件系统。

第六，M29.5 replay plan 是 materialization 前的最后闸门。

第七，全局优化和组件化必须等 source truth 稳定后再做。

如果只记一句话：

```text
先证明这些像素是谁的，再谈它们组成了什么。
```
