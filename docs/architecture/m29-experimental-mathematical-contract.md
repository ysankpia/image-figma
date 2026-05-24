# M29 数学合同

本文档描述 M29 plan-driven 主链当前真正实现的数学合同。它不是愿景稿，也不是把模型输出包装成架构事实。若需要从初中数学起步理解这些公式为什么存在，先读 [M29 数学推演：从一个矩形框开始](m29-math-from-first-principles.md)。

核心结论很简单：外部模型说“东修一块、西修一块的根因是底层数学合同没定清楚”，这个判断有一半是对的。对的部分是：本链路确实需要把 bbox、pixel owner、set relation、cluster 和 replay action 定成显式合同，否则阈值会到处漂。不对的部分是：本地代码现在并没有全局二次规划、响应式组件编译、React/Tailwind 生成、Auto Layout 或 Figma Component/Instance。M29 当前是一个像素拓扑、ownership、replay plan 和 plan-driven materialization 主链。

## 0. 非目标

当前 M29 数学合同不承诺：

- 不从截图生成响应式前端代码。
- 不把双栏、瀑布流、卡片、导航栏编译成组件。
- 不求解全局布局优化问题。
- 不创建 Figma Component/Instance。
- 不绕过 M29.5 plan 去改变 `/api/tasks/{taskId}/dsl`。
- 不把 M29.4 cluster role hint 当成真实层级或组件。

这点必须先钉死。否则所有讨论都会滑到错误抽象层：把“物理证据可重放”误当成“语义组件已恢复”。

## 1. 源对象链

当前主链的事实来源按顺序是：

```text
source PNG pixels P
OCR boxes T
raw M29 primitive graph G29
M29.2 source UI physical graph O292
M29.3.1 pairwise relation graph R2931
M29.4 stable design cluster report C294
M29.5 replay plan Q295
M29 plan-driven DSL D29
```

对应代码入口：

```text
backend/app/visual_primitive_graph.py
backend/app/source_ui_physical_graph.py
backend/app/region_relation_kernel.py
backend/app/region_relation_graph_report.py
backend/app/stable_design_cluster.py
backend/app/m29_replay_plan.py
backend/app/m29_plan_materializer.py
```

真正 materialize 可见节点的是 M29 plan-driven materializer。M29.3.1、M29.4、M29.5 都是 report 或 plan，不直接写 DSL visible node。

## 2. 坐标与基本几何

所有 region 使用页坐标 bbox：

```text
B = [x, y, w, h],  w > 0, h > 0
x2(B) = x + w
y2(B) = y + h
area(B) = max(0, w) * max(0, h)
cx(B) = x + w / 2
cy(B) = y + h / 2
```

两个 bbox 的相交宽高：

```text
iw(A,B) = max(0, min(x2(A), x2(B)) - max(x(A), x(B)))
ih(A,B) = max(0, min(y2(A), y2(B)) - max(y(A), y(B)))
I(A,B) = iw(A,B) * ih(A,B)
```

是否有严格相交：

```text
intersects(A,B) :=
  min(x2(A), x2(B)) > max(x(A), x(B))
  and
  min(y2(A), y2(B)) > max(y(A), y(B))
```

完全包含：

```text
contains(A,B) :=
  x(A) <= x(B)
  and y(A) <= y(B)
  and x2(A) >= x2(B)
  and y2(A) >= y2(B)
```

IoU：

```text
IoU(A,B) = I(A,B) / max(1, area(A) + area(B) - I(A,B))
```

bbox gap 使用 Chebyshev 风格的轴向最大间隙：

```text
x_gap(A,B) = max(0, max(x(A), x(B)) - min(x2(A), x2(B)))
y_gap(A,B) = max(0, max(y(A), y(B)) - min(y2(A), y2(B)))
gap(A,B) = max(x_gap(A,B), y_gap(A,B))
```

这个几何层是后续所有 ownership、relation、dedupe 和 cleanup 的共同地基。

## 3. Raw M29 Primitive Graph

raw M29 的目标不是识别 UI 组件，而是从像素和 OCR 中提出 primitive：

```text
type(node) in {text, shape, image, symbol, unknown}
layerHint(node) in {background, container, content, overlay, unknown}
```

每个 primitive 带局部像素指标：

```text
metrics = {
  colorCount,
  textureScore,
  edgeScore,
  fillRatio,
  aspectRatio,
  brightness,
  meanRgb
}
```

主要默认阈值：

```text
minComponentArea = 16
maxComponentAreaRatio = 0.25
minShapeArea = 64
shapeTextureThreshold = 0.12
shapeColorThreshold = 10
minImageArea = 1200
imageColorThreshold = 32
imageTextureThreshold = 0.18
imageAcceptThreshold = 0.78
symbolTextureThreshold = 0.20
symbolColorThreshold = 24
```

这些阈值仍是启发式。它们不是全局最优解；只是 raw evidence gate。

## 4. Low-Contrast Support Gate

`low_contrast_support` 解决的是“低对比支撑区域看不见”的物理问题，不是 SearchBar 语义 detector。

给定 OCR text bbox `T` 和 foreground evidence 集合 `F`，先找同线 evidence：

```text
lineEvidence(T,F) = {
  f in F |
  not intersects(f,T)
  and verticalOverlap(f,T) >= 0.25
  and gap(f,T) <= max(96, h(T) * 16)
  and w(f) <= max(48, round(w(T)*0.45), h(T)*2)
  and h(f) <= max(24, round(h(T)*1.2))
}
```

其中：

```text
verticalOverlap(A,B) =
  max(0, min(y2(A), y2(B)) - max(y(A), y(B))) / max(1, min(h(A), h(B)))
```

候选 support `S` 必须包含 text，并由 text 与同线 evidence 的 union 扩张而来：

```text
U = union(T, lineEvidence(T,F))
S = expand(U, padX, padY)
contains(S,T) must be true
```

尺寸门禁：

```text
w(S) >= max(48, w(T)+24)
h(S) >= max(18, h(T)+12)
w(S) <= round(imageWidth * 0.90)
h(S) <= min(max(max(18,h(T)+12), h(T)+44), 96)
```

得分前先过有限支撑 gate：

```text
areaRatio(S) = area(S) / (imageWidth * imageHeight)
0 < areaRatio(S) <= 0.08
w(S) <= imageWidth * 0.90
h(S) <= max(110, imageHeight * 0.08)
texture(S) <= 0.075
colorCount(S) <= 10
```

外环必须完整，否则不能证明这是闭合 support：

```text
supportBoundaryDeltas(S) exists iff
  x(S)-3 >= 0
  and y(S)-3 >= 0
  and x2(S)+3 <= imageWidth
  and y2(S)+3 <= imageHeight
```

内外环颜色差：

```text
d_side = L1(meanRgb(inner(S)), meanRgb(outerSide(S)))
min(d_top,d_bottom,d_left,d_right) >= 6
avg(d_top,d_bottom,d_left,d_right) <= 80
```

候选必须包含同线非文字 foreground evidence：

```text
supportEvidence(S,T,F) = {
  f in F |
  contains(S,f)
  and area(f) < area(S) * 0.65
  and not intersects(f,T)
  and verticalOverlap(f,T) >= 0.25
}
|supportEvidence(S,T,F)| > 0
```

横向 support 比例：

```text
w(S) / h(S) >= 2.0
```

最终分数：

```text
score(S) =
  avgBoundaryDelta
  + |supportEvidence(S,T,F)| * 4
  + min(w(S)/h(S), 10) * 0.2
  - texture(S) * 30
  - colorCount(S) * 0.1
  - areaRatio(S) * 20
```

取最高分；同分取面积更小者。这里的第一性原则是：没有完整外环，就没有“有限闭合支撑区域”的证据，不能把贴边 open band replay 成 shape。

## 5. Shape Geometry Fit

shape geometry fit 回答“mask 像什么”，不回答“能不能安全重放”。

对 connected component，定义局部 occupancy：

```text
occupancy(region) = nonzeroMaskPixels(region) / area(region)
```

中心、角、边指标：

```text
center = occupancy(centerBox)
cornerMissing = count(cornerOccupancy <= 0.45) / 4
edge = edgeOccupancy(mask, thickness)
ratio = w / h
ellipseFill = pi / 4
ellipseError = abs(fillRatio - ellipseFill)
```

矩形：

```text
rect if isRectLike(component)
  and center >= 0.90
  and cornerMissing <= 0.25
```

圆或椭圆：

```text
ellipseLike if
  area(component) >= 64
  and area(component) < 10000
  and 0.45 <= fillRatio <= 0.90
  and 0.35 <= ratio <= 2.80
  and center >= 0.75
  and cornerMissing >= 0.50
  and ellipseError <= 0.20
```

圆：

```text
circle if ellipseLike and 0.85 <= ratio <= 1.18
radius = round(min(w,h)/2)
```

椭圆：

```text
ellipse if ellipseLike and not circle
```

confidence：

```text
high if ellipseError <= 0.12 and cornerMissing >= 0.75
medium otherwise
```

对 `low_contrast_support`，geometry fit 使用忽略 text/evidence 后的 fill occupancy：

```text
roundedOrPill if
  center >= 0.82
  and edge >= 0.72
  and cornerMissing >= 0.75

pill if estimatedRadius >= round(min(w,h)/2 * 0.75)
rounded_rect if estimatedRadius > 0

rect if
  center >= 0.82
  and min(cornerOccupancy) >= 0.62
```

radius 只有在以下条件成立时进入 replay：

```text
geometry.confidence != low
and geometry.kind in {rounded_rect, pill, circle, ellipse}
and geometry.params.radius is numeric
```

## 6. M29.2 Source Pixel Ownership

M29.2 把 raw M29 与 OCR 转成 source object：

```text
object = {
  visualKind,
  pixelOwner,
  replayDecision,
  confidence,
  sourceEvidence,
  reasons,
  risks
}
```

关键 owner 集：

```text
pixelOwner in {
  editable_text,
  preserve_raster,
  raster_icon,
  shape_geometry,
  fallback_only,
  diagnostic_only
}
```

### 6.1 Media

raw image 或大面积高纹理区域进入 raster：

```text
media(node) if
  type(node) = image
  or (
    area(bbox) >= 1200
    and colorCount(bbox) >= 24
    and textureScore(bbox) >= 0.16
  )
```

输出：

```text
visualKind = media_region
pixelOwner = preserve_raster
replayDecision = image_replay
confidence = high if raw type=image else medium
```

### 6.2 OCR Text

低置信或空文本不可编辑：

```text
if text = empty or ocrConfidence < 0.60:
  pixelOwner = preserve_raster
  replayDecision = preserve_in_parent_raster
```

大 display text 在 media 内部时也保留在 raster：

```text
mediaOverlap(T) >= 0.82
and (
  h(T) >= 40
  or (w(T) >= round(imageWidth * 0.22)
      and h(T) >= round(40 * 0.75))
)
=> preserve_in_parent_raster
```

否则作为 UI editable text：

```text
pixelOwner = editable_text
replayDecision = text_replay
confidence = high if localBackgroundConfidence >= 0.45 else medium
```

local background confidence：

```text
bg = sampleOuterBBoxRingRgb(T)
mean = meanRgb(T)
distance = |mean.r-bg.r| + |mean.g-bg.g| + |mean.b-bg.b|
localBackgroundConfidence =
  clamp(1 - distance/765 - textureScore(T)*0.35, 0, 1)
```

### 6.3 Icon / Raster Foreground

symbol 候选进入 icon clustering 的必要条件：

```text
type(node) = symbol
and area(bbox) <= 12000
and overlap(bbox, media) < 0.80 for all media
and overlap(bbox, ocr) < 0.45 for all OCR boxes
```

相邻 symbol cluster：

```text
sameCluster(a,b) if gap(union(cluster), bbox(b)) <= 8
```

输出：

```text
pixelOwner = raster_icon
replayDecision = icon_replay
confidence = high if clusterSize > 1 else medium
```

小型复杂 foreground shape 不允许误入 pure vector shape：

```text
smallForeground(B) :=
  area(B) <= 12000 and max(w(B), h(B)) <= 128

complexForeground(metrics) :=
  colorCount > 24
  or textureScore > 0.18
  or edgeScore >= 0.30

if subtype in {badge_background, small_ellipse, icon_button_background, small_rounded_rect}
  and smallForeground(B)
  and textOverlap < 0.20
  and complexForeground(metrics):
    pixelOwner = raster_icon
    replayDecision = icon_replay
```

blocked foreground 可恢复为 raster icon 的条件：

```text
recoverableReasons intersects {
  symbol_color_too_high,
  symbol_texture_too_high,
  symbol_edge_too_high,
  weak_symbol_metrics
}
and hardBlockReasons not intersects {
  text_overlap,
  inside_image_primitive,
  image_internal_texture,
  protective_shape_overlap,
  large_container_fragment,
  line_like,
  symbol_area_too_small,
  symbol_area_too_large
}
and smallForeground(B)
and textOverlap < 0.20
and mediaContainment < 0.80
=> raster_icon + icon_replay
```

### 6.4 Shape Replay Safety

shape replay safe 是物理可表达性，不是 geometry fit：

```text
safeShape(B) iff
  textOverlap(B) < 0.45
  and colorCount(B) <= 12
  and textureScore(B) <= 0.14
  and edgeScore(B) < 0.28
```

如果不安全：

```text
pixelOwner = diagnostic_only
replayDecision = skip
```

如果安全：

```text
pixelOwner = shape_geometry
replayDecision = shape_replay
```

这里是当前最重要的原则之一：

```text
geometry fit: 这个 mask 像圆、椭圆、矩形还是线
ownership: 这个像素集合能不能由 Figma vector shape 安全表达
```

两者不是一个问题。把小头像、小图标或复杂纹理 foreground 当成 shape，就是错抽象。

### 6.5 Dedupe

M29.2 用 IoU 去重：

```text
duplicate(A,B) iff IoU(A,B) >= 0.88
```

优先级：

```text
text_replay = 5
image_replay = 4
icon_replay = 3
shape_replay = 2
preserve_in_parent_raster = 1
skip = 0
```

排序：

```text
sortKey(object) = (-priority, y, x, -area)
```

最后按 `(y, x, area)` 重新命名为 `m292_object_NNNN`。

## 7. Region Relation Kernel

M29.3.0 是纯 bbox 数学 utility，不依赖 OCR、pipeline、storage、DSL 或 Figma。

先定义：

```text
AinB = I(A,B) / area(A)
BinA = I(A,B) / area(B)
```

primary set relation 判定顺序：

```text
near_equal if AinB >= 0.90 and BinA >= 0.90
contains if BinA >= 0.95
contained_by if AinB >= 0.95
overlaps if I(A,B) > 0
disjoint otherwise
```

near threshold：

```text
short(A) = max(min(w(A), h(A)), 8)
nearThreshold(A,B) =
  min(24, max(6, round(0.08 * min(short(A), short(B)))))
```

alignment threshold：

```text
long(A) = max(w(A), h(A))
alignmentThreshold(A,B) =
  min(12, max(2, round(0.04 * min(long(A), long(B)))))
```

secondary geometry relations：

```text
near if gap(A,B) <= nearThreshold(A,B)
left_of if x2(A) <= x(B)
right_of if x2(B) <= x(A)
above if y2(A) <= y(B)
below if y2(B) <= y(A)
aligned_left if |x(A)-x(B)| <= alignmentThreshold
aligned_center_x if |cx(A)-cx(B)| <= alignmentThreshold
aligned_right if |x2(A)-x2(B)| <= alignmentThreshold
aligned_top if |y(A)-y(B)| <= alignmentThreshold
aligned_center_y if |cy(A)-cy(B)| <= alignmentThreshold
aligned_bottom if |y2(A)-y2(B)| <= alignmentThreshold
```

尺寸相似：

```text
similar(a,b) :=
  |a-b| <= 2
  or |a-b| / max(1, max(a,b)) <= 0.08

same_width if similar(w(A), w(B))
same_height if similar(h(A), h(B))
same_size if same_width and same_height
```

这个 kernel 的价值是把 `relation(A,B)` 从一个过载字符串拆成：

```text
primarySetRelation + secondaryGeometryRelations + metrics
```

否则后续 cleanup、cluster 和 replay 会继续在不同文件里各写一套“差不多”的关系判断。

## 8. M29.3.1 Pairwise Relation Graph

M29.3.1 读取 M29.2 source objects，构造完整无向 pairwise graph：

```text
V = {sourceObject_i}
E = {(i,j) | 1 <= i < j <= |V|}
|E| = |V|(|V|-1)/2
edge(i,j) = regionRelation(bbox_i, bbox_j)
```

输出是 report：

```text
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
```

这一步不是 grouping，也不是 componentization。它只是把关系语言统一输出。

## 9. M29.4 Stable Design Cluster

M29.4 只消费 M29.3.1 relation graph，输出 weak structural evidence。它不改变 DSL、不创建 asset、不创建组件。

edge motif：

```text
repeated_size_subgraph if
  (same_size or (same_width and same_height)) and near

containment_anchor_subgraph if
  primary in {contains, contained_by}

directed_row_subgraph if
  (left_of or right_of)
  and (aligned_center_y or aligned_top or aligned_bottom)

directed_column_subgraph if
  (above or below)
  and (aligned_center_x or aligned_left or aligned_right)

stable_local_relation_subgraph if
  near_equal or overlaps or near
```

当前代码里，media 和 text 的 near/overlap pair 会被映射为：

```text
containment_anchor_subgraph + background_anchor_like
```

注意：类型定义里有 `media_text_group_like`，但当前 `role_hint_for_pattern()` 不会产出它。这是代码事实，不应在文档或模型回答里把它说成已经有“图文卡片组件”。

cluster candidate 由每种 motif 的 connected components 产生：

```text
component_m = connectedComponents(V, E_motif)
accept candidate if 2 <= |members| <= 12 and internalEdges not empty
```

稳定分：

```text
possibleEdges(k) = k(k-1)/2
edgeDensity = min(1, internalEdges / possibleEdges)
confidenceScore = avg(confidenceValue(member))
primarySignal = count(edge.primarySetRelation != disjoint) / internalEdges
```

confidence value：

```text
high = 1.0
medium = 0.65
low = 0.25
unknown = 0.4
```

repeatability：

```text
ownerRepeat = maxCount(pixelOwner) / k
sizeSignature(B) = round(w/8)*8 + "x" + round(h/8)*8
sizeRepeat = maxCount(sizeSignature) / k
repeatedEdgeRatio =
  min(1, (count(same_size) + min(count(same_width), count(same_height))) / internalEdges)

repeatability =
  min(1, ownerRepeat*0.35 + sizeRepeat*0.35 + repeatedEdgeRatio*0.30)
```

pattern stability：

```text
repeated_size:
  min(1, 0.62 + repeatability*0.22 + edgeDensity*0.08 + confidenceScore*0.08)

containment_anchor:
  min(1, 0.68 + primarySignal*0.15 + confidenceScore*0.12 + edgeDensity*0.05)

directed_row or directed_column:
  min(1, 0.58 + edgeDensity*0.12 + confidenceScore*0.16 + primarySignal*0.08)

stable_local:
  min(1, 0.80 + confidenceScore*0.08 + primarySignal*0.06 + edgeDensity*0.06)
```

通过门槛：

```text
stabilityScore >= 0.55
```

cluster dedupe：

```text
duplicateCluster(A,B) iff
  pattern(A) = pattern(B)
  and IoU(bbox(A), bbox(B)) >= 0.92
  and memberOverlap(A,B) >= 0.85
```

M29.4 的正确定位：

```text
weak structural report
not component
not layout tree
not auto layout
not renderer input
```

## 10. M29.5 Replay Plan

M29.5 是正式 materialization 前的 quality gate。它仍然不创建可见节点。

action mapping：

```text
if replayDecision=text_replay and pixelOwner=editable_text and confidence!=low:
  finalReplayAction = text_replay

if replayDecision=image_replay and pixelOwner=preserve_raster and confidence!=low:
  finalReplayAction = image_replay

if replayDecision=icon_replay and pixelOwner=raster_icon and confidence!=low:
  finalReplayAction = icon_replay

if replayDecision=shape_replay and pixelOwner=shape_geometry and confidence!=low:
  finalReplayAction = shape_replay

if replayDecision=preserve_in_parent_raster:
  finalReplayAction = preserve_in_parent_raster

if pixelOwner=fallback_only:
  finalReplayAction = fallback_only

else:
  finalReplayAction = diagnostic_only
```

target role：

```text
text_replay -> m29_text
image_replay -> m29_image
icon_replay -> m29_symbol
shape_replay -> m29_shape
```

near-equal duplicate suppression：

```text
if primarySetRelation(A,B) = near_equal:
  suppress lower replayPriority
```

priority：

```text
ownerRank(editable_text) = 50
ownerRank(preserve_raster) = 40
ownerRank(raster_icon) = 35
ownerRank(shape_geometry) = 30
ownerRank(fallback_only) = 10
ownerRank(diagnostic_only) = 0

confidenceRank(high)=3
confidenceRank(medium)=2
confidenceRank(low)=1

replayPriority = (ownerRank, confidenceRank)
```

text cleanup targets：

```text
text_replay always adds:
  target = fallback

text_replay adds copied_image_asset target if:
  other.replayDecision = image_replay
  and other.pixelOwner = preserve_raster
  and textContainedByMedia(text, other, edge)
```

text contained by media：

```text
true if primarySetRelation = near_equal
true if edge(left=text,right=media).primary = contained_by
true if edge(left=media,right=text).primary = contains
false otherwise
```

visible node budget：

```text
maxVisibleNodes = 260
```

visible plan sorting：

```text
shape_replay = 0
image_replay = 1
icon_replay = 2
text_replay = 3
confidence high = 0, medium = 1, low = 2
sortKey = (actionRank, confidenceRank, sourceObjectId)
```

over budget：

```text
finalReplayAction = suppress_duplicate
reason += node_budget_suppressed
risk += node_budget_exceeded
```

最终 plan sort：

```text
shape, image, icon, text, preserve, fallback_only, diagnostic_only, suppress_duplicate
```

这个排序就是 plan-driven materialization 的物理 z-order 基础：

```text
shape/support/background -> image -> icon -> text
```

## 11. M29 Plan-Driven Materialization

M29 plan-driven materializer 是正式 DSL producer。它要求 M29.5 plan 存在：

```text
if M29.5 plan exists and M29.2 objects exist:
  replay M29.5 plan
else:
  fail materialization
```

它从 deterministic fallback DSL 开始，然后追加 plan-approved 节点：

```text
base = deterministic full-image fallback
children += accepted replay nodes
```

文本节点：

```text
type = text
role = m29_text
layout = bbox
content.text = OCR text
style.color = sampledForeground(P, bbox)
style.fontSize = estimated from bbox
```

图片与 icon：

```text
type = image
role = m29_image or m29_symbol
asset = existing raw asset if available and forceCrop=false
     else crop(P, bbox)
layout = bbox
imageFill.mode = fit
```

shape：

```text
type = shape
role = m29_shape
fill = sampled source fill
radius = raw geometry radius only if permitted by geometry contract
layout = bbox
```

copied image asset text cleanup：

```text
for each text replay T and copied image I:
  cleanup only if plan has copied_image_asset target from T to I

  localBBox = mapPageBBoxToAssetPixels(T.bbox, I.bbox, assetSize)
  fill localBBox with sampleOuterBBoxRingRgb(assetPixels, localBBox)
```

fallback cleanup：

```text
if eraseReplayedBboxesFromFallback:
  for each replayed visible node N:
    only if plan has fallback cleanup target for N.sourceObjectId
    bbox = clamp(N.bbox, fallbackSize)
    fill bbox in fallback with sampleOuterBBoxRingRgb(sourcePixels, bbox)
```

`preserve_in_parent_raster` 不生成 visible node，所以不会被 fallback cleanup 擦掉。这是正确的：不可安全编辑的文字仍留在父 raster/fallback 里。

## 12. 外部模型说法的判定

### 对的部分

它抓住了一个真问题：如果没有统一数学合同，工程会退化成局部阈值修补。M29 之前容易混在一起的对象至少有四种：

```text
geometry fit
pixel ownership
set relation
layout/component inference
```

这四个问题不能共享一个粗糙标签。比如“这是圆形”不等于“可以用矢量圆重放”；“两个 bbox near”不等于“它们属于一个组件”；“双栏排列”不等于“当前系统能输出响应式 Masonry”。

### 错的部分

外部模型把未来架构当成当前实现了。当前代码没有：

```text
global optimization
quadratic programming
Cassowary/Kiwi constraints
responsive CSS grid/flex compilation
React/Tailwind generation
component schema extraction
Figma Component/Instance materialization
Auto Layout
```

M29.4 只是 structural cluster report；M29.5 只是 replay plan；M29 plan-driven materializer 只是 flat DSL replay producer。把这些说成组件化或响应式编译，是事实错误。

### 该怎么吸收它的建议

全局优化不是现在就塞进 M29 materializer 的补丁。正确顺序是：

```text
1. 冻结 source object 和 pixel ownership 合同。
2. 冻结 region relation 合同。
3. 冻结 graph/cluster 的弱证据边界。
4. 冻结 replay plan 的可见节点和 cleanup 权限。
5. 只有当 source truth 稳定后，才定义 layout energy 或 component graph isomorphism。
```

否则优化器会优化错对象。它会把错误 owner、错误 OCR、错误裁片、错误 cluster 全部“优雅地”固化。

## 13. 当前薄弱点

第一，阈值仍多。`0.82`、`0.55`、`0.14`、`0.28`、`0.88` 这些数都有工程意义，但还不是一个统一的无量纲能量函数。

第二，M29.4 role hint 很弱。`row_like`、`column_like`、`background_anchor_like` 是结构提示，不是 layout tree。尤其 `media_text_group_like` 当前没有实际产出路径。

第三，没有全局 ownership conservation。理想情况下，每个源像素应满足：

```text
owner(pixel) in {fallback, text, image, icon, shape}
and high-confidence visible owners should not double-own the same pixel
```

当前通过 IoU、cleanup 和局部 owner gate 近似实现，还不是全局约束。

第四，没有 component graph isomorphism。真正组件化至少需要：

```text
subgraph A ~= subgraph B
under relation labels, owner labels, normalized geometry, content slots
```

M29.4 只做 motif connected component，不做同构匹配。

第五，没有 layout energy。若未来要判断 row/column/grid/masonry，应该先定义：

```text
E_row(C), E_col(C), E_grid(C), E_masonry(C)
layout(C) = argmin(E)
```

但这应作为 M29 之后的 component/layout 阶段，而不是混进 source ownership。

第六，语义命名仍有债。`control_background`、`card_background` 是方便 replay 的中间分类，不等于可靠识别了 Control 或 Card。

## 14. 下一步数学合同建议

如果继续推进，优先补这几层，而不是直接写组件编译器：

```text
Pixel Ownership Conservation:
  每个 replayed bbox 的擦除、保留、复制资产 cleanup 必须能解释像素归属。

Graph Isomorphism:
  定义 repeated unit 的节点标签、边标签、归一化 bbox 和 slot 匹配误差。

Layout Energy:
  在稳定 repeated unit 上定义 row/column/grid/masonry 的能量函数。

Materialization Permission:
  明确哪些 graph/layout 证据允许创建 group/container，哪些只能留 report。
```

一个合理的 layout energy 草案只能在 source truth 稳定后引入：

```text
E_row(C) =
  Var({cy_i})
  + lambda_overlap * sum overlapXViolation(i,j)
  + lambda_gap * Var({horizontalGap_i})

E_col(C) =
  Var({cx_i})
  + lambda_overlap * sum overlapYViolation(i,j)
  + lambda_gap * Var({verticalGap_i})

direction(C) = argmin(E_row(C), E_col(C))
```

注意这只是未来候选，不是当前代码事实。

## 15. 验证边界

当前合同对应的最小验证面：

```text
tests/test_visual_primitive_graph.py
tests/test_source_ui_physical_graph.py
tests/test_region_relation_kernel.py
tests/test_region_relation_graph_report.py
tests/test_stable_design_cluster.py
tests/test_m29_replay_plan.py
tests/test_m29_plan_materializer.py
tests/test_upload_preview_pipeline.py
```

如果未来引入全局优化或组件化，不能只看“生成数量变多”。验收指标必须包括：

```text
owner correctness
false positive replay rate
fallback erasure correctness
copied asset cleanup correctness
cluster stability
component isomorphism precision
user repair cost
mainline DSL non-regression
```

## 16. 总判断

M29 当前的正确抽象不是“AI 看懂页面并生成组件”，而是：

```text
从像素和 OCR 中提取物理证据；
给每个证据分配 replay owner；
用纯 bbox relation 解释对象关系；
用弱 cluster report 收集结构线索；
用 replay plan 控制哪些证据能进入正式 DSL；
最后由 M29 plan-driven materializer materialize flat replay nodes。
```

所以用户怀疑的方向是对的：如果不把这些数学合同写清楚，工程一定会继续局部修补。但下一步不是盲目上全局优化器，而是先把当前 M29 的 source truth、owner、relation、cluster、plan、materialization 边界钉死。本文档就是这个边界。
