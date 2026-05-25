# M29 之后：Codia 级图片转 Figma 可编辑设计稿数学合同 v0.1

> 目标：从 M29 已有的 bbox / owner / relation 开始，继续用基础几何、面积、比例、方差、距离、聚类和许可条件，推导达到 Codia 级图片转 Figma 可编辑设计稿所需的后续数学合同。

## 0. 说明与边界

这份文档不是在描述 Codia 内部一定如何实现，而是根据公开能力与我们当前 M29 链路，定义一套为了达到同级产品能力应当具备的后端数学合同。

公开资料显示，Codia 类产品能力包括：截图转可编辑设计、OCR、layer tree、结构化 JSON / SVG / Figma-compatible 输出、component detection、layout analysis、style extraction、PDF / PSD / Web / Image 等多源输入转统一设计结构。对应到我们的系统，核心不是直接从图片吐 Figma 节点，而是先建立一套可审计、可验证、可回放的 VisualStruct / EditableDesignIR。

M29 当前已经有：

```text
bbox geometry
pixel owner
region relation
weak cluster report
replay plan
flat direct replay
fallback cleanup
copied image cleanup
```

M29 当前还没有：

```text
global optimization
responsive layout
Auto Layout
Figma Component / Instance
component schema extraction
design token system
true design system binding
```

所以后续数学合同从这句话继续：

```text
先证明这些像素是谁的，再证明它们怎么组成层级、布局、组件和设计系统。
```

---

## 1. 总目标

输入：

```text
source image P
OCR boxes T
M29 source objects O = {o1, o2, ..., on}
region relation graph R
pixel owner / replay decision / confidence
```

输出：

```text
EditableDesignIR = {
  sourceObjects,
  ownershipMap,
  hierarchyTree,
  layoutModels,
  componentCandidates,
  designTokens,
  variants,
  vectorPaths,
  figmaMaterializationPlan,
  qualityReport
}
```

最终进入 Figma 插件前的路径：

```text
image pixels
  ↓
source object
  ↓
ownership
  ↓
relation graph
  ↓
hierarchy tree
  ↓
layout model
  ↓
component graph
  ↓
token system
  ↓
materialization permission
  ↓
Figma nodes
```

---

# 第 0 章：从 M29 已有地基开始

## 0.1 已有基础对象

M29 的基础对象是 bbox：

```text
B = [x, y, w, h]
x2(B) = x + w
y2(B) = y + h
area(B) = w * h
cx(B) = x + w / 2
cy(B) = y + h / 2
```

两个 bbox 的相交面积：

```text
iw(A,B) = max(0, min(x2(A),x2(B)) - max(x(A),x(B)))
ih(A,B) = max(0, min(y2(A),y2(B)) - max(y(A),y(B)))
I(A,B) = iw(A,B) * ih(A,B)
```

IoU：

```text
IoU(A,B) = I(A,B) / (area(A) + area(B) - I(A,B))
```

包含比例：

```text
AinB = I(A,B) / area(A)
BinA = I(A,B) / area(B)
```

bbox、相交、包含、IoU、gap 是后续 ownership、relation、dedupe、cleanup、layout、component 的共同地基。

## 0.2 已有 owner 合同

每个 source object 有：

```text
object = {
  bbox,
  visualKind,
  pixelOwner,
  replayDecision,
  confidence,
  sourceEvidence,
  reasons,
  risks
}
```

关键 owner：

```text
editable_text
preserve_raster
raster_icon
shape_geometry
fallback_only
diagnostic_only
```

当前最重要的原则：

```text
geometry fit ≠ pixel ownership ≠ replay decision
```

例子：

```text
头像可能像圆，但不应该变成 Figma ellipse。
复杂 icon 可能像 shape，但应该 raster_icon。
只有低纹理、低颜色数、低边缘复杂度区域才可能 shape_geometry。
```

## 0.3 后续总公式

所有高级能力可以看成一个总评分：

```text
DesignScore =
  a * OwnershipCorrectness
+ b * VisualFidelity
+ c * HierarchyCorrectness
+ d * LayoutCorrectness
+ e * ComponentCorrectness
+ f * TokenCorrectness
- g * FalseEditablePenalty
- h * CleanupPenalty
- k * UserRepairCost
```

大白话：

```text
不是生成越多越好。
是正确可编辑越多、错误可编辑越少、用户修复成本越低越好。
```

---

# 第 1 章：Pixel Ownership Conservation，像素归属守恒

如果不先补 ownership conservation，后面的组件和 Auto Layout 会把错误对象包装得更漂亮，所以必须先补。

## 1.1 问题

目标：

```text
每个源像素 p，最终都要能解释它属于谁。
```

定义源图像的像素集合：

```text
Ω = {所有像素 p}
p = (x, y)
```

定义 owner：

```text
Owner(p) ∈ {
  fallback,
  editable_text,
  image,
  raster_icon,
  shape,
  erased_by_cleanup,
  diagnostic,
  unknown
}
```

## 1.2 可见节点覆盖

每个 replay node `n` 有 bbox：

```text
B(n)
```

如果像素 p 在节点 n 的 bbox 里：

```text
p ∈ B(n)
```

那么这个节点声称覆盖这个像素。

定义可见节点集合：

```text
V = {n | n materialized as visible node}
```

像素 p 被多少个节点覆盖：

```text
coverCount(p) = count({n ∈ V | p ∈ B(n)})
```

理想情况下，高置信节点不要重复拥有同一个像素：

```text
if confidence(n) = high:
  coverCount_high(p) <= 1
```

但允许视觉叠加，比如：

```text
shape background + text
```

所以要分 owner 类型：

```text
backgroundOwner(p) ∈ {fallback, shape, image}
foregroundOwner(p) ∈ {editable_text, raster_icon, vector}
```

约束：

```text
count(backgroundOwner(p)) <= 1
count(foregroundOwner(p)) <= 1
```

大白话：

```text
一个像素可以有背景和前景。
但不能同时有两个背景，也不能同时有两个前景。
```

## 1.3 清理授权

如果文字 T 被重放成 editable_text，fallback 中对应区域可以被擦：

```text
CleanupAllowed(T, fallback) = true
```

如果文字 T 在图片 I 内部，需要证明 T 属于 I，才可以擦 copied image asset：

```text
CleanupAllowed(T, I) = true
iff
  relation(T,I).primary ∈ {contained_by, near_equal}
  and pixelOwner(I) = preserve_raster
  and pixelOwner(T) = editable_text
```

如果 T 是 `preserve_in_parent_raster`：

```text
CleanupAllowed(T, fallback) = false
CleanupAllowed(T, I) = false
```

## 1.4 小例子

图片 I：

```text
I = [0, 0, 300, 200]
```

文字 T：

```text
T = [50, 50, 100, 20]
```

相交面积：

```text
I(T,I) = area(T) = 100 * 20 = 2000
```

包含比例：

```text
T in I = 2000 / 2000 = 1
I in T = 2000 / 60000 = 0.033
```

所以：

```text
T contained_by I
```

如果 T 是 editable_text，I 是 preserve_raster：

```text
CleanupAllowed(T,I) = true
```

如果 T 是低置信 OCR：

```text
pixelOwner(T) = preserve_raster
CleanupAllowed(T,I) = false
```

## 1.5 边界

```text
Ownership conservation 不是语义识别。
它只管像素归属、重复拥有、擦除权限。
```

## 1.6 非目标

```text
不判断这是 Card、Button、Nav。
不判断响应式。
不创建 Component。
不优化布局。
```

## 1.7 验收指标

```text
owner correctness
background double-owner rate
foreground double-owner rate
wrong cleanup area
missed cleanup area
false editable area
```

公式：

```text
WrongOwnerRate =
  area({p | predictedOwner(p) ≠ expectedOwner(p)})
  / area(Ω)
```

```text
WrongCleanupRate =
  area({p | erased(p) and shouldPreserve(p)})
  / area({p | shouldPreserve(p)})
```

---

# 第 1A 章：Media Internal Pixel Decomposition，复合媒体内部像素分解

## 1A.1 问题

`preserve_raster` 不能永远等于“内部全部不可理解”。它在 M29.2 的第一职责是保住复杂视觉 fidelity，避免把照片、图表、玻璃拟态、渐变和纹理误画成简单 shape。但复合 UI 区域经常同时包含：

```text
raster background
internal OCR text
internal icon
internal separator
internal small visual mark
internal repeated UI item
```

如果一个大 media 被整体接受为：

```text
pixelOwner(M) = preserve_raster
replayDecision(M) = image_replay
```

下游就会得到稳定视觉，但内部普通 UI 图标、导航 item、卡片内 marker、表格里的小圆点和图标可能没有独立 source object。这个问题不是 carousel、nav、table、金融 App 或某个文案的特化问题，而是一个通用源对象缺口：

```text
CompositeMedia(M) contains recoverable internal foreground objects.
```

## 1A.2 复合媒体定义

给定 M29.2 source object `M`：

```text
B(M) = [x, y, w, h]
pixelOwner(M) = preserve_raster
replayDecision(M) = image_replay
```

定义内部 OCR 文本：

```text
TextInside(M) =
  { t in OCR |
    intersectionArea(B(t), B(M)) / area(B(t)) >= 0.95
  }
```

定义内部 raw primitive：

```text
RawInside(M) =
  { r in G29 |
    intersectionArea(B(r), B(M)) / area(B(r)) >= 0.95
  }
```

复合媒体判定：

```text
CompositeMedia(M) iff
  pixelOwner(M) = preserve_raster
  and replayDecision(M) = image_replay
  and (
    count(TextInside(M)) >= 1
    or count(RawInside(M)) >= 2
    or "contains_internal_text" in risks(M)
  )
```

这个定义只使用通用 source evidence：bbox containment、OCR、raw primitive、M29.2 owner/risk。它不能使用：

```text
file name
task id
fixed bbox
literal text content
industry/theme/color special case
```

## 1A.3 背景 owner 与内部前景 owner

复合媒体需要把 owner 拆成两层：

```text
backgroundOwner(p) ∈ {fallback, preserve_raster_background, shape}
foregroundOwner(p) ∈ {editable_text, raster_icon, internal_icon_candidate, internal_shape_candidate, diagnostic}
```

对于 `CompositeMedia(M)`，默认背景仍由原 media 拥有：

```text
if p ∈ B(M):
  backgroundOwner(p) = preserve_raster_background(M)
```

内部候选只允许声明前景，不允许夺走整个 media 背景：

```text
InternalForegroundClaim(c, M) only claims foregroundOwner(p)
for p in mask(c)
```

约束：

```text
count(backgroundOwner(p)) <= 1
count(foregroundOwner(p)) <= 1
```

也就是说：

```text
media 背景可以保留为 raster；
内部高置信 UI foreground 可以另行提出候选；
二者必须由 cleanup authorization 解释，不能静默双影。
```

## 1A.4 OCR 文字保护 Mask

内部图标检测必须先排除文字笔画。对每个内部 OCR 文本 `t`：

```text
B_pad(t) = [
  x(t) - px,
  y(t) - py,
  w(t) + 2px,
  h(t) + 2py
]
```

一般第一版：

```text
px = 2..4
py = 2..4
```

文字保护 mask：

```text
TextMask_M(p) = 1
iff exists t in TextInside(M), p ∈ B_pad(t)
```

后续内部 foreground 搜索：

```text
SearchMask_M(p) =
  1 iff p ∈ B(M) and TextMask_M(p) = 0
```

禁止规则：

```text
if overlapArea(B(c), TextMask_M) / area(B(c)) > τ_text_overlap:
  reject c as internal_icon_candidate
```

否则中文笔画、数字笔画、小字号标签会被 connected component 错当成 icon。

## 1A.5 局部背景模型

复合 media 内部常有渐变、光效、纹理和半透明层。不能用单一全局背景色：

```text
bg = average(edge pixels)
```

应当为每个像素估计局部背景：

```text
bg_M(p) =
  median({
    P(q) |
    q in Window(p, R),
    q not in TextMask_M,
    q not high_contrast
  })
```

工程第一版可以近似为：

```text
bg_M(p) = Blur(P restricted to B(M), R)
```

其中：

```text
R = 12..24 px
```

局部颜色差：

```text
ColorDiff(p) =
  |R(p) - R(bg_M(p))|
+ |G(p) - G(bg_M(p))|
+ |B(p) - B(bg_M(p))|
```

亮度与饱和度：

```text
L(p) = 0.299R(p) + 0.587G(p) + 0.114B(p)
S(p) = max(R,G,B) - min(R,G,B)
```

## 1A.6 相对前景分数

内部前景不是“亮色”，而是“相对局部背景异常”：

```text
ForegroundScore_M(p) =
  a * ColorDiff(p)
+ b * |S(p) - S(bg_M(p))|
+ c * |L(p) - L(bg_M(p))|
+ d * EdgeStrength(p)
- e * BackgroundTexturePenalty(p)
```

初始前景 mask：

```text
FG_M(p) = 1 iff
  p ∈ B(M)
  and TextMask_M(p) = 0
  and ForegroundScore_M(p) >= τ_fg
```

然后做连通域：

```text
C_M = connected_components(FG_M)
```

每个 component `c` 记录：

```text
B(c)
area(c)
fillRatio(c) = area(c) / area(B(c))
colorComplexity(c)
textureScore(c)
edgeScore(c)
```

## 1A.7 内部图标候选分数

UI icon / marker / small visual foreground 的判断不能只靠连通域面积。需要同时看尺寸、紧凑度、颜色一致性、文本锚点、重复排列和主视觉惩罚：

```text
IconScore(c, M) =
  a * SizeScore(c)
+ b * CompactnessScore(c)
+ c * ColorCoherenceScore(c)
+ d * TextAnchorScore(c, TextInside(M))
+ e * RepetitionScore(c, C_M)
+ f * LocalControlRegionScore(c)
- g * TextOverlapPenalty(c)
- h * HeroGraphicPenalty(c, M)
- i * TextureFragmentPenalty(c)
```

尺寸门：

```text
SizeScore(c) = 1
iff τ_min_area <= area(c) <= τ_max_internal_icon_area
```

紧凑度：

```text
Compactness(c) = area(c) / area(B(c))
```

颜色一致性可以用粗 bucket：

```text
bucket(P) = [R//16, G//16, B//16]
ColorComplexity(c) = uniqueBuckets(c) / max(1, area(c))
ColorCoherenceScore(c) = 1 / (1 + ColorComplexity(c))
```

## 1A.8 文本锚点与重复行验证

对于内部 label `t` 和候选 `c`：

```text
dx(c,t) = |cx(c) - cx(t)|
dy(c,t) = y(t) - y2(c)
```

当图标位于 label 上方时：

```text
dy(c,t) > 0
```

文本锚点分：

```text
TextAnchorScore(c) =
  max over t in TextInside(M) [
    exp(-dx(c,t)^2 / σx^2)
    * exp(-(dy(c,t)-μ_gap)^2 / σy^2)
  ]
```

对于重复 UI item 集合：

```text
Pairs = {(c_i, t_i)}
```

排序一致性：

```text
OrderScore =
  1 if order(cx(c_i)) = order(cx(t_i))
  else 0
```

间距稳定：

```text
GapStability =
  1 / (1 + Var({cx(c_{i+1}) - cx(c_i)}))
```

重复 action row 分数：

```text
RepeatedActionRowScore =
  a * MatchCoverage
+ b * OrderScore
+ c * GapStability
+ d * SameSizeScore
+ e * SameYBandScore
```

这套公式只要求“图标与 label 的几何锚定和重复排列”，不关心 label 写的是哪个字。

## 1A.9 主视觉与纹理碎片惩罚

复合 media 内常有大主视觉、光效、照片纹理和装饰线。它们可能形成连通域，但不应该被提升成 UI icon：

```text
HeroGraphicPenalty(c, M) =
  a * LargeAreaScore(c, M)
+ b * CenterMassScore(c, M)
+ c * TextureScore(c)
+ d * LongFragmentScore(c)
- e * TextAnchorScore(c)
```

其中：

```text
LargeAreaScore(c,M) = clamp(area(c) / area(M) / τ_large, 0, 1)
```

长条碎片惩罚：

```text
LongFragmentScore(c) =
  1 if max(w(c), h(c)) / max(1, min(w(c), h(c))) >= τ_aspect_long
  else 0
```

竖向分割线、横线、表格线如果要恢复，应走：

```text
internal_separator_candidate
```

不能假装成 icon。

## 1A.10 内部提升许可

内部候选不能直接创建 DSL visible node。第一版只能 report-only：

```text
InternalPromotionCandidate(c, M) iff
  CompositeMedia(M)
  and contained_ratio(B(c), B(M)) >= 0.95
  and TextMaskOverlap(c) <= τ_text_overlap
  and IconScore(c,M) >= τ_icon
  and HeroGraphicPenalty(c,M) <= τ_hero
```

候选角色：

```text
internal_icon_candidate
internal_shape_candidate
internal_separator_candidate
internal_ui_label
internal_decorative_candidate
rejected_internal_fragment
```

M29.6 report 必须记录：

```text
mediaSourceObjectId
candidateRawNodeIds
candidateBbox
candidateRole
scoreBreakdown
matchedTextSourceObjectIds
rejectedReason
confidence
```

## 1A.11 Transparent Asset Extraction

透明资产提取不是通用 Photoshop 抠图。它只服务已经有 source evidence 的小 UI asset：

```text
TransparentAssetAllowed(c) iff
  candidateRole(c) in {internal_icon_candidate, raster_icon}
  and confidence(c) in {high, medium}
  and BackgroundStability(c) >= τ_bg_stable
  and TextMaskOverlap(c) <= τ_text_overlap
  and area(c) <= τ_asset_area
```

输出仍是矩形 PNG，但透明度按 mask 给出：

```text
cropBBox = pad(B(c), p)
Alpha(p) =
  0   if ForegroundScore_M(p) <= τ_bg
  255 if ForegroundScore_M(p) >= τ_fg
  round(255 * (ForegroundScore_M(p)-τ_bg)/(τ_fg-τ_bg)) otherwise
```

输出：

```text
Out(p) = [R(p), G(p), B(p), Alpha(p)]
```

这就是“按形状抠”的工程表达：

```text
bbox crop + alpha mask
```

## 1A.12 Copied Media Cleanup 权限

如果内部候选后续被真正 materialized，原 copied media asset 里不能静默双影。cleanup 仍然必须单独授权：

```text
InternalCleanupAllowed(c, M) iff
  materialized(c) = true
  and contained_ratio(B(c), B(M)) >= 0.95
  and pixelOwner(M) = preserve_raster
  and localBackgroundConfidence(c) >= τ_bg_conf
  and cleanupRisk(c) <= medium
```

对 icon / asset：

```text
if Alpha(c,p) > 128:
  copiedMedia(p) = bg_M(p)
```

对 text：

```text
erase text mask or text bbox with bg_M(p)
```

第一版 M29.6 不执行 cleanup，只报告：

```text
cleanupWouldBeRequired = true
cleanupAllowed = false
reason = report_only
```

## 1A.13 非目标

```text
不按轮播图、底部导航、表格、金融页面、文案或固定 bbox 特化。
不从 M29.6 直接改 DSL。
不从 M29.6 直接改 M29.5 replay plan。
不全图无脑 connected components。
不把主视觉光效、照片纹理、艺术字碎片当 UI icon。
不引入通用人像/商品 remove-background 作为第一版主线。
```

## 1A.14 验收指标

```text
CompositeMediaRecall
InternalCandidatePrecision
TextGlyphFalseIconRate
HeroFragmentFalseIconRate
RepeatedItemMatchCoverage
TransparentAssetAllowPrecision
CleanupAuthorizationCompleteness
```

第一版验收是 report，不是视觉输出：

```text
reportOnly = true
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
```

---

# 第 2 章：Hierarchy Tree，层级树

Codia 级输出不是 flat nodes，而应当有 tree / childElements。Figma 里 Frame 也是 layout hierarchy 的容器。M29 当前 Direct Replay 是 flat DSL replay，不是 tree。后续第一件事就是从 flat objects 推层级。

## 2.1 输入输出

输入：

```text
O = {o1, o2, ..., on}
B_i = bbox(oi)
relation(i,j)
pixelOwner(oi)
confidence(oi)
```

输出：

```text
Tree = (V, parent)
parent(oi) ∈ O ∪ {root}
```

约束：

```text
每个节点最多一个父亲。
不能出现循环。
父节点 bbox 应该包含子节点 bbox 或解释它们的 group bbox。
```

## 2.2 直接包含分数

如果 A 要当 B 的父节点，第一条件是 A 基本包住 B：

```text
containScore(A,B) = I(A,B) / area(B)
```

如果：

```text
containScore(A,B) >= 0.95
```

说明 B 基本在 A 里面。

但仅仅包含不够，因为全页背景也包含所有元素。

## 2.3 父级紧密度

父级不能大得离谱。

```text
sizeRatio(A,B) = area(A) / area(B)
```

如果 A 是 B 的直接父级，`sizeRatio(A,B)` 应该大于 1，但不能太大。

定义过大惩罚：

```text
OversizePenalty(A,B) = max(0, sizeRatio(A,B) - K_parent)
```

其中 `K_parent` 是允许的最大直接父子面积倍数，比如 20、30、50，后续靠数据调。

大白话：

```text
按钮背景当按钮文字父级，可以。
整页背景当按钮文字直接父级，不好。
```

## 2.4 边距分数

如果 A 包住 B，计算 B 到 A 四边的距离：

```text
padL = x(B) - x(A)
padR = x2(A) - x2(B)
padT = y(B) - y(A)
padB = y2(A) - y2(B)
```

如果 A 是 B 的合理父级，padding 应该非负：

```text
padL, padR, padT, padB >= 0
```

边距平衡：

```text
HorizontalPadBalance(A,B)
=
|padL - padR| / max(1, padL + padR)
```

```text
VerticalPadBalance(A,B)
=
|padT - padB| / max(1, padT + padB)
```

如果是按钮文字，通常左右 padding 相对平衡：

```text
HorizontalPadBalance 小
```

如果是图片内角标，不一定平衡，所以不能强制，只能作为分数。

## 2.5 Owner 兼容性

父子关系还要看 owner 类型。

定义：

```text
ParentTypeScore(A,B) ∈ [0,1]
```

简单规则：

```text
shape_geometry parent of editable_text:
  high，像按钮、输入框、标签

preserve_raster parent of editable_text:
  medium，只能在 text contained by media 且 cleanup 授权时成立

fallback_only parent:
  low，不该当显式父级

diagnostic_only parent:
  zero

editable_text parent of image:
  zero
```

可以写成表：

```text
ParentTypeScore(A,B) =
  1.0  if A.shape_geometry and B.editable_text
  0.8  if A.shape_geometry and B.raster_icon
  0.7  if A.preserve_raster and B.editable_text and contained_by
  0.4  if A.preserve_raster and B.raster_icon
  0.0  if A.editable_text
```

## 2.6 父级总代价

把上面的分数合成：

```text
ParentCost(A,B) =
  λ1 * (1 - containScore(A,B))
+ λ2 * OversizePenalty(A,B)
+ λ3 * HorizontalPadBalance(A,B)
+ λ4 * VerticalPadBalance(A,B)
+ λ5 * (1 - ParentTypeScore(A,B))
+ λ6 * ZOrderPenalty(A,B)
```

其中：

```text
ZOrderPenalty(A,B) = 1 if A visually above B else 0
```

因为父级背景通常应该在子级下面。

最终：

```text
parent(B) = argmin_A ParentCost(A,B)
```

`argmin` 的意思：

```text
在所有候选 A 里，选分数最小的那个。
```

但要加门槛：

```text
parent(B) = A
only if
  containScore(A,B) >= τ_contain
  and ParentCost(A,B) <= τ_parent
```

否则：

```text
parent(B) = root
```

## 2.7 隐式 Group / Frame bbox

很多 UI 没有显式背景框，比如：

```text
icon + text
```

这时不能找一个包含它们的 source object，只能生成 group candidate。

给一组对象 G：

```text
G = {o1, o2, ..., ok}
```

定义组 bbox：

```text
B(G) = union(B1, B2, ..., Bk)
```

union 的意思：

```text
x(G)  = min(x_i)
y(G)  = min(y_i)
x2(G) = max(x2_i)
y2(G) = max(y2_i)
w(G)  = x2(G) - x(G)
h(G)  = y2(G) - y(G)
```

## 2.8 小例子

按钮背景 A：

```text
A = [10, 10, 100, 40]
```

按钮文字 B：

```text
B = [35, 20, 50, 16]
```

面积：

```text
area(A) = 100 * 40 = 4000
area(B) = 50 * 16 = 800
```

B 完全在 A 内：

```text
containScore(A,B) = 800 / 800 = 1
sizeRatio(A,B) = 4000 / 800 = 5
```

padding：

```text
padL = 35 - 10 = 25
padR = 110 - 85 = 25
padT = 20 - 10 = 10
padB = 50 - 36 = 14
```

左右平衡：

```text
HorizontalPadBalance = |25-25| / 50 = 0
```

如果 A 是 shape_geometry，B 是 editable_text：

```text
ParentTypeScore(A,B) = 1
```

所以：

```text
A 很适合当 B 的父级。
```

## 2.9 边界

```text
父子关系不是组件。
父子关系不是 Auto Layout。
父子关系只是 layer tree 的几何和 owner 解释。
```

## 2.10 非目标

```text
不因为 A 包含 B 就创建 Component。
不因为一组对象有 bbox 就认为是 Card。
不把全页背景当所有节点直接父级。
```

## 2.11 验收指标

```text
parent precision
parent recall
tree depth error
wrong container rate
root leakage rate
```

公式：

```text
ParentAccuracy =
  count(predictedParent(i) = expectedParent(i)) / n
```

```text
WrongDirectBackgroundParentRate =
  count(parent(i) = pageBackground but expectedParent(i) ≠ pageBackground) / n
```

---

# 第 3 章：Sibling Group，兄弟组与容器候选

层级树解决“谁包含谁”，但很多 UI 组不是由显式背景决定的，而是由相邻、对齐、间距、类型组合决定的。

例子：

```text
icon + label
avatar + name + subtitle
image + title + price
nav item list
```

## 3.1 组候选

定义一组对象：

```text
G = {o1, o2, ..., ok}
```

候选组需要：

```text
2 <= k <= K_group
```

M29.4 当前也用 connected components 生成 cluster candidate，但它是 weak structural evidence，不创建组件、不创建 DSL visible node。后续要做的是给 group materialization 加更强合同。

## 3.2 关系密度

一组 k 个节点，最多有：

```text
possibleEdges(G) = k(k-1)/2
```

有效关系边：

```text
validEdges(G) =
  count({(i,j) | relation(i,j) has near/aligned/same_size/contains})
```

关系密度：

```text
RelationDensity(G) =
  validEdges(G) / possibleEdges(G)
```

## 3.3 对齐分数

对齐关系：

```text
aligned_left
aligned_center_x
aligned_right
aligned_top
aligned_center_y
aligned_bottom
```

对齐分：

```text
AlignmentScore(G) =
  count(aligned relations in G) / possibleEdges(G)
```

## 3.4 间距规律

如果 G 更像横向排列，按 x 排序：

```text
o1, o2, ..., ok
```

横向 gap：

```text
gapX_i = x(o_{i+1}) - x2(o_i)
```

如果 G 更像纵向排列，按 y 排序：

```text
gapY_i = y(o_{i+1}) - y2(o_i)
```

方差：

```text
Var(gap) =
  average((gap_i - mean(gap))^2)
```

规律分：

```text
GapRegularity(G) = 1 / (1 + Var(gap))
```

大白话：

```text
间距越稳定，分数越接近 1。
间距越乱，分数越接近 0。
```

## 3.5 Owner 组合分

定义 owner 类型组合：

```text
OwnerPattern(G) = multiset({pixelOwner(o_i)})
```

典型组合：

```text
shape_geometry + editable_text
  => button/input/tag-like

raster_icon + editable_text
  => menu item / nav item-like

preserve_raster + editable_text
  => card/media block-like

shape_geometry + raster_icon + editable_text
  => input/search/control-like
```

组合分：

```text
OwnerPatternScore(G) ∈ [0,1]
```

## 3.6 组稳定分

```text
GroupScore(G) =
  a * RelationDensity(G)
+ b * AlignmentScore(G)
+ c * GapRegularity(G)
+ d * OwnerPatternScore(G)
+ e * ConfidenceMean(G)
- f * OverlapConflict(G)
```

其中：

```text
ConfidenceMean(G) =
  average(confidenceValue(o_i))
```

冲突：

```text
OverlapConflict(G) =
  sum(I(B_i,B_j) / min(area(B_i), area(B_j)))
  for unexpected overlaps
```

最终：

```text
GroupCandidate(G) = true
iff
  GroupScore(G) >= τ_group
```

## 3.7 小例子

icon：

```text
I = [10, 10, 16, 16]
owner = raster_icon
```

text：

```text
T = [34, 9, 80, 18]
owner = editable_text
```

它们：

```text
I left_of T
aligned_center_y = true
gap = 34 - 26 = 8
OwnerPattern = raster_icon + editable_text
```

那么：

```text
RelationDensity 高
AlignmentScore 高
GapRegularity 暂时不可算或默认中高
OwnerPatternScore 高
```

所以：

```text
GroupCandidate({I,T}) = true
```

但这只是 group，不是 component。

## 3.8 边界

```text
Group 是局部编辑方便性。
Component 是可复用结构。
Auto Layout 是布局规则。
三者不能混。
```

## 3.9 非目标

```text
不因为 group 成立就自动创建 Component。
不因为 group 横向排列就自动创建 Auto Layout。
不因为 image + text 就命名为 Card。
```

## 3.10 验收指标

```text
group precision
group recall
over-group rate
under-group rate
wrong nesting rate
```

公式：

```text
OverGroupRate =
  count(predicted group contains unrelated child)
  / count(predicted groups)
```

---

# 第 4 章：Layout Energy，布局能量

M29 已经提出未来要定义：

```text
E_row(C), E_col(C), E_grid(C), E_masonry(C)
layout(C) = argmin(E)
```

但它应该在 source truth 稳定后引入，而不是混进 source ownership。

## 4.1 输入输出

输入一个 group 或 container：

```text
C = {o1, o2, ..., ok}
```

输出：

```text
layoutType(C) ∈ {
  absolute,
  row,
  column,
  grid,
  masonry,
  overlay,
  free
}
```

选择方式：

```text
layoutType(C) =
  argmin {
    E_abs(C),
    E_row(C),
    E_col(C),
    E_grid(C),
    E_masonry(C),
    E_overlay(C)
  }
```

大白话：

```text
谁的解释成本最低，就选谁。
```

## 4.2 Row Energy，横向布局

一行的特征：

```text
y 中心差不多
从左到右
横向 gap 稳定
高度相近
重叠少
```

先按 x 排序：

```text
o1, o2, ..., ok
where x(o1) <= x(o2) <= ... <= x(ok)
```

中心 y：

```text
cy_i = y_i + h_i / 2
```

横向 gap：

```text
gapX_i = x_{i+1} - x2_i
```

高度：

```text
h_i
```

重叠惩罚：

```text
OverlapXPenalty(C) =
  sum(max(0, x2_i - x_{i+1}))
```

Row 能量：

```text
E_row(C) =
  λ1 * Var({cy_i})
+ λ2 * Var({gapX_i})
+ λ3 * Var({h_i})
+ λ4 * OverlapXPenalty(C)
+ λ5 * NegativeGapCount(C)
```

其中：

```text
NegativeGapCount(C) = count(gapX_i < 0)
```

## 4.3 Column Energy，纵向布局

一列的特征：

```text
x 中心差不多
从上到下
纵向 gap 稳定
宽度相近
重叠少
```

按 y 排序：

```text
o1, o2, ..., ok
where y(o1) <= y(o2) <= ... <= y(ok)
```

中心 x：

```text
cx_i = x_i + w_i / 2
```

纵向 gap：

```text
gapY_i = y_{i+1} - y2_i
```

Column 能量：

```text
E_col(C) =
  λ1 * Var({cx_i})
+ λ2 * Var({gapY_i})
+ λ3 * Var({w_i})
+ λ4 * OverlapYPenalty(C)
+ λ5 * NegativeGapCount(C)
```

## 4.4 Grid Energy，网格布局

网格的特征：

```text
多行多列
列 x 对齐
行 y 对齐
cell 尺寸相似
row gap 稳定
column gap 稳定
```

先把 x 中心聚成列：

```text
columns = cluster({cx_i})
```

把 y 中心聚成行：

```text
rows = cluster({cy_i})
```

每个对象属于一个格子：

```text
cell(i) = (row(i), col(i))
```

列对齐误差：

```text
ColumnAlignError =
  sum(|cx_i - mean(cx of col(i))|)
```

行对齐误差：

```text
RowAlignError =
  sum(|cy_i - mean(cy of row(i))|)
```

尺寸误差：

```text
CellSizeError = Var({w_i}) + Var({h_i})
```

列间距误差：

```text
ColGapError = Var({x(col_{j+1}) - x2(col_j)})
```

行间距误差：

```text
RowGapError = Var({y(row_{r+1}) - y2(row_r)})
```

缺格惩罚：

```text
MissingCellPenalty =
  expectedCellCount - actualCellCount
```

Grid 能量：

```text
E_grid(C) =
  μ1 * ColumnAlignError
+ μ2 * RowAlignError
+ μ3 * CellSizeError
+ μ4 * ColGapError
+ μ5 * RowGapError
+ μ6 * MissingCellPenalty
```

## 4.5 Masonry Energy，瀑布流布局

瀑布流的特征：

```text
列宽稳定
列 x 稳定
高度可变
每列内部从上到下排列
列之间高度可以不同
```

列聚类：

```text
columns = cluster({x_i or cx_i})
```

列宽稳定：

```text
WidthError = Var({w_i})
```

列 x 稳定：

```text
ColumnXError =
  sum(|x_i - mean(x of column(i))|)
```

列内纵向 gap：

```text
GapYWithinColumnError =
  sum over columns Var({gapY_i in that column})
```

瀑布流能量：

```text
E_masonry(C) =
  ν1 * WidthError
+ ν2 * ColumnXError
+ ν3 * GapYWithinColumnError
+ ν4 * OverlapYPenaltyWithinColumn
```

## 4.6 Overlay Energy，叠加布局

有些对象是重叠的，比如：

```text
badge on avatar
play icon on image
close button on modal
text overlay on image
```

定义覆盖比例：

```text
cover(A,B) = I(A,B) / min(area(A), area(B))
```

Overlay 的特征：

```text
small object contained_by large object
or high overlap with explicit foreground owner
```

```text
E_overlay(A,B) =
  α1 * (1 - containScore(small, large))
+ α2 * SizeMismatchPenalty
+ α3 * OwnerMismatchPenalty
```

例如：

```text
raster_icon contained_by preserve_raster
```

可能是 overlay。

## 4.7 Absolute Energy

如果所有布局解释都很差，就保留 absolute：

```text
E_abs(C) = constant_abs
```

选择 absolute 的条件：

```text
min(E_row, E_col, E_grid, E_masonry, E_overlay) > τ_layout
```

大白话：

```text
解释不出来，就不要硬套 Auto Layout。
```

## 4.8 小例子：三张卡片横排

```text
A = [10, 10, 100, 80]
B = [130, 10, 100, 80]
C = [250, 10, 100, 80]
```

中心 y：

```text
cy_A = 50
cy_B = 50
cy_C = 50
Var(cy) = 0
```

gap：

```text
gap1 = 130 - 110 = 20
gap2 = 250 - 230 = 20
Var(gapX) = 0
```

高度：

```text
80, 80, 80
Var(h) = 0
```

所以：

```text
E_row 很低
E_col 很高
E_grid 如果只有一行，也可能低，但 row 更简单
layout = row
```

## 4.9 边界

```text
Layout Energy 是解释几何排列。
它不是组件识别。
它不是语义命名。
它不是代码生成。
```

## 4.10 非目标

```text
不从单张图可靠推断所有响应式断点。
不把任意 row 自动转成 Figma Auto Layout。
不把 grid 自动转成 CSS grid。
```

## 4.11 验收指标

```text
layout type accuracy
row/column/grid/masonry precision
wrong Auto Layout rate
absolute fallback correctness
layout repair cost
```

公式：

```text
LayoutAccuracy =
  count(predictedLayout(C) = expectedLayout(C))
  / count(containers)
```

```text
WrongAutoLayoutRate =
  count(autoLayoutCreated but expectedAbsolute)
  / count(autoLayoutCreated)
```

---

# 第 5 章：Auto Layout 数学合同

Auto Layout 会改变子节点位置和 frame 尺寸，因此必须是强权限，不是随便加。

## 5.1 Auto Layout 许可

对容器 C：

```text
AutoLayoutAllowed(C) = true
```

需要满足：

```text
min(E_row(C), E_col(C), E_grid(C)) <= τ_auto
and LayoutConfidence(C) >= τ_conf
and RepairRisk(C) <= τ_risk
```

其中：

```text
LayoutConfidence(C) =
  1 / (1 + min(E_row, E_col, E_grid))
```

如果最低的是 row：

```text
layoutMode = HORIZONTAL
```

如果最低的是 column：

```text
layoutMode = VERTICAL
```

如果最低的是 grid：

```text
layoutMode = GRID
```

否则：

```text
layoutMode = NONE
```

## 5.2 Gap

横向 Auto Layout：

```text
itemSpacing = median({gapX_i})
```

纵向 Auto Layout：

```text
itemSpacing = median({gapY_i})
```

用 median 是因为：

```text
一个异常对象不会把整体 spacing 拉坏。
```

例子：

```text
gaps = {8, 8, 9, 50}
median = 8.5
mean = 18.75
```

显然 median 更合理。

## 5.3 Padding

父容器 P，子元素集合 C。

```text
contentLeft   = min(x_i)
contentRight  = max(x2_i)
contentTop    = min(y_i)
contentBottom = max(y2_i)
```

padding：

```text
paddingLeft   = contentLeft - x(P)
paddingRight  = x2(P) - contentRight
paddingTop    = contentTop - y(P)
paddingBottom = y2(P) - contentBottom
```

如果任何 padding < 0：

```text
AutoLayoutAllowed = false
or clipping/overflow required
```

## 5.4 Alignment

横向 row 需要判断垂直对齐。

```text
topError    = Var({y_i})
centerError = Var({cy_i})
bottomError = Var({y2_i})
```

选择误差最小：

```text
counterAxisAlignItems =
  argmin(topError, centerError, bottomError)
```

对应：

```text
topError 最小    => MIN
centerError 最小 => CENTER
bottomError 最小 => MAX
```

纵向 column 判断水平对齐：

```text
leftError   = Var({x_i})
centerError = Var({cx_i})
rightError  = Var({x2_i})
```

## 5.5 Justify Content

主轴方向剩余空间。

横向：

```text
freeSpace =
  w(P)
- paddingLeft
- paddingRight
- sum(w_i)
```

实际 gap 总数：

```text
gapCount = k - 1
```

如果：

```text
abs(freeSpace - itemSpacing * gapCount) <= τ
```

说明是 packed：

```text
primaryAxisAlignItems = MIN / CENTER / MAX
```

如果所有 gap 很大且等分：

```text
gapX_i ≈ freeSpace / gapCount
```

可以认为：

```text
justifyContent = space-between
```

定义：

```text
SpaceBetweenError =
  Var({gapX_i})
```

如果：

```text
SpaceBetweenError <= τ_space_between
and first child near left padding
and last child near right padding
```

则：

```text
primaryAxisAlignItems = SPACE_BETWEEN
```

## 5.6 Hug / Fill / Fixed

### Hug contents

横向 hug：

```text
contentWidth =
  sum(w_i) + itemSpacing * (k-1) + paddingLeft + paddingRight
```

```text
HugWidthError =
  |w(P) - contentWidth| / max(1, w(P))
```

如果：

```text
HugWidthError <= τ_hug
```

则：

```text
widthSizing = HUG / FIT_CONTENT
```

### Fill container

子元素 i 可填充父容器：

```text
availableWidth =
  w(P) - paddingLeft - paddingRight
```

```text
FillScore(i) =
  1 - |w_i - availableWidth| / max(1, availableWidth)
```

如果：

```text
FillScore(i) >= τ_fill
```

则：

```text
child.widthSizing = FILL
```

### Fixed

如果没有足够证据支持 hug 或 fill：

```text
sizing = FIXED
```

## 5.7 小例子：横向按钮组

父 P：

```text
P = [0, 0, 300, 40]
```

三个按钮：

```text
A = [20, 8, 60, 24]
B = [100, 8, 60, 24]
C = [180, 8, 60, 24]
```

gap：

```text
gap1 = 100 - 80 = 20
gap2 = 180 - 160 = 20
itemSpacing = 20
```

padding：

```text
paddingLeft = 20
paddingRight = 300 - 240 = 60
paddingTop = 8
paddingBottom = 40 - 32 = 8
```

中心 y：

```text
cy = 20,20,20
centerError = 0
```

所以：

```text
layoutMode = HORIZONTAL
counterAxisAlignItems = CENTER
itemSpacing = 20
paddingTop = 8
paddingBottom = 8
```

但左右 padding 不平衡，可能不是 simple packed，也可能有右侧预留空间，所以：

```text
primaryAxisAlignItems = MIN
```

## 5.8 边界

```text
Auto Layout 是 materialization 强行为。
设置后会改变子节点位置。
必须只有在 layout energy 很低时才允许。
```

## 5.9 非目标

```text
不从单张图推断真实响应式断点。
不强行把所有 group 变成 Auto Layout。
不为了“看起来高级”牺牲像素还原。
```

## 5.10 验收指标

```text
auto layout precision
itemSpacing error
padding error
alignment accuracy
sizing mode accuracy
post-auto-layout visual drift
```

公式：

```text
AutoLayoutDrift =
  sum(|renderedBBox_i - sourceBBox_i|) / n
```

如果：

```text
AutoLayoutDrift > τ_drift
```

则该 Auto Layout materialization 不合格。

---

# 第 6 章：Component Isomorphism，组件同构

组件识别不能只靠“像卡片”。它必须靠重复子图。

## 6.1 子图定义

一个组件候选是一个子图：

```text
S = (V_S, E_S)
```

其中：

```text
V_S = {source objects or groups}
E_S = {relation edges among V_S}
```

每个节点标签：

```text
Label(v) = {
  ownerType,
  visualKind,
  roleHint,
  normalizedBBox,
  styleSignature,
  contentType
}
```

## 6.2 归一化 bbox

组件实例大小可能不同，所以不能直接比绝对坐标。

给组件 bbox：

```text
B(S) = [xS, yS, wS, hS]
```

子节点 v：

```text
B(v) = [x, y, w, h]
```

归一化：

```text
relX = (x - xS) / wS
relY = (y - yS) / hS
relW = w / wS
relH = h / hS
```

归一化 bbox：

```text
NB(v,S) = [relX, relY, relW, relH]
```

大白话：

```text
不看它在页面哪儿。
只看它在组件内部的相对位置和比例。
```

## 6.3 节点距离

两个节点 a、b 的距离：

```text
D_node(a,b) =
  α1 * OwnerMismatch(a,b)
+ α2 * VisualKindMismatch(a,b)
+ α3 * GeometryDistance(a,b)
+ α4 * StyleDistance(a,b)
+ α5 * ContentTypeMismatch(a,b)
```

几何距离：

```text
GeometryDistance(a,b) =
  |relX_a - relX_b|
+ |relY_a - relY_b|
+ |relW_a - relW_b|
+ |relH_a - relH_b|
```

Owner mismatch：

```text
OwnerMismatch(a,b) =
  0 if owner(a)=owner(b)
  1 otherwise
```

## 6.4 边距离

两个 relation edge 的距离：

```text
D_edge(e1,e2) =
  β1 * PrimaryRelationMismatch
+ β2 * SecondaryRelationMismatch
+ β3 * GapDistanceError
+ β4 * AlignmentError
```

Primary mismatch：

```text
PrimaryRelationMismatch =
  0 if primarySetRelation(e1)=primarySetRelation(e2)
  1 otherwise
```

Secondary mismatch：

```text
SecondaryRelationMismatch =
  1 - |secondary(e1) ∩ secondary(e2)| / |secondary(e1) ∪ secondary(e2)|
```

## 6.5 子图匹配函数

两个子图：

```text
S1 = (V1,E1)
S2 = (V2,E2)
```

如果它们节点数相同：

```text
|V1| = |V2|
```

找一个一一对应函数：

```text
φ: V1 -> V2
```

让总距离最小：

```text
D_iso(S1,S2,φ) =
  sum(D_node(v, φ(v)))
+ sum(D_edge((u,v), (φ(u),φ(v))))
```

子图距离：

```text
D_component(S1,S2) =
  min over φ D_iso(S1,S2,φ)
```

如果：

```text
D_component(S1,S2) <= τ_component
```

则：

```text
S1 ≈ S2
```

这就是“同构”的基础版：

```text
节点能一一配上，
对应节点像，
对应关系也像。
```

## 6.6 重复次数

一个组件不能只出现一次。

```text
RepeatCount(S) =
  count({S_j | D_component(S,S_j) <= τ_component})
```

如果：

```text
RepeatCount(S) >= 2
```

可以成为：

```text
ComponentCandidate
```

如果：

```text
RepeatCount(S) >= 3
```

置信度更高。

## 6.7 Slot 一致性

组件不仅结构重复，还要有稳定槽位。

槽位：

```text
slot = {
  slotType,
  relativeBBox,
  ownerType,
  styleSignature,
  variableContent
}
```

两个槽位距离：

```text
D_slot(a,b) =
  γ1 * |relX_a - relX_b|
+ γ2 * |relY_a - relY_b|
+ γ3 * |relW_a - relW_b|
+ γ4 * |relH_a - relH_b|
+ γ5 * TypeMismatch
+ γ6 * StyleDistance
```

槽位一致分：

```text
SlotConsistency(S_family) =
  1 / (1 + average(D_slot))
```

## 6.8 小例子：两个卡片

卡片 1：

```text
C1 = {
  image: [10,10,100,80],
  title: [10,100,100,20],
  price: [10,130,60,20]
}
```

卡片 2：

```text
C2 = {
  image: [130,10,100,80],
  title: [130,100,100,20],
  price: [130,130,60,20]
}
```

每个组件 bbox：

```text
B(C1) = [10,10,100,140]
B(C2) = [130,10,100,140]
```

归一化 image：

```text
C1 image rel = [0,0,1,80/140]
C2 image rel = [0,0,1,80/140]
```

归一化 title：

```text
C1 title rel = [0,90/140,1,20/140]
C2 title rel = [0,90/140,1,20/140]
```

归一化完全一致，owner 也一致：

```text
D_component(C1,C2) ≈ 0
```

所以：

```text
ComponentCandidate = true
```

但如果只有这一个卡片：

```text
RepeatCount = 1
```

不能直接创建 Component，只能创建 group/frame。

## 6.9 边界

```text
Component Isomorphism 是结构相似。
它不是语义命名。
它不保证是 Button/Card/Nav。
```

## 6.10 非目标

```text
不把单例对象做成 Component。
不把只有尺寸相同的一排图标做成复杂组件。
不把 weak cluster 直接 materialize 成 Component。
```

## 6.11 验收指标

```text
component candidate precision
component candidate recall
false component rate
slot matching accuracy
instance override correctness
```

公式：

```text
ComponentPrecision =
  truePositiveComponents / predictedComponents
```

```text
SlotAccuracy =
  correctSlotMatches / totalPredictedSlotMatches
```

---

# 第 7 章：Design Token，设计系统数学合同

设计系统要把页面里的重复视觉值聚成 token。

## 7.1 Color Token

颜色：

```text
c = [r,g,b]
```

颜色距离：

```text
D_color(c1,c2) =
  |r1-r2| + |g1-g2| + |b1-b2|
```

如果：

```text
D_color(c1,c2) <= τ_color
```

则认为它们属于同一颜色簇。

颜色簇：

```text
ColorCluster_k = {c_i}
```

token 值：

```text
tokenColor_k =
  median(ColorCluster_k)
```

使用频率：

```text
freq(k) = count(ColorCluster_k) / totalColorUses
```

如果：

```text
freq(k) >= τ_freq
```

生成颜色 token。

## 7.2 颜色语义命名

颜色 token 需要语义角色：

```text
role ∈ {
  background,
  surface,
  primary,
  secondary,
  text_primary,
  text_secondary,
  border,
  danger,
  success
}
```

语义分：

```text
ColorRoleScore(token, role) =
  a * UsageFrequency(token, role)
+ b * OwnerContextScore(token, role)
+ c * ContrastScore(token, role)
+ d * PositionPrior(token, role)
```

例子：

```text
大量用于 editable_text 的深色
=> text_primary

大量用于按钮 shape 背景
=> primary

大量用于页面大背景
=> background

大量用于细线和边框
=> border
```

## 7.3 Contrast，文字对比

文字颜色 ct，背景颜色 cb。

简单 L1 对比：

```text
Contrast(ct,cb) =
  |r_t-r_b| + |g_t-g_b| + |b_t-b_b|
```

如果：

```text
Contrast 高
```

更像正文/标题文字。

如果：

```text
Contrast 低
```

可能是 placeholder、disabled、secondary text。

## 7.4 Spacing Token

收集所有间距：

```text
S = {
  gapX,
  gapY,
  paddingLeft,
  paddingRight,
  paddingTop,
  paddingBottom,
  margin
}
```

间距距离：

```text
D_space(a,b) = |a-b|
```

聚类：

```text
if |a-b| <= τ_space:
  same spacing cluster
```

token 值：

```text
spacingToken_k = median(cluster_k)
```

常见输出：

```text
space-4
space-8
space-12
space-16
space-24
space-32
```

但命名不要写死，可以先输出：

```text
spacing/token_001 = 8
spacing/token_002 = 16
```

## 7.5 Radius Token

圆角集合：

```text
R = {r_i}
```

距离：

```text
D_radius(r_i,r_j) = |r_i-r_j|
```

聚类：

```text
radiusToken_k = median(cluster_k)
```

pill 判断：

```text
PillScore(B,r) =
  1 - |r - min(w,h)/2| / max(1, min(w,h)/2)
```

如果：

```text
PillScore >= τ_pill
```

则：

```text
radius = full
```

## 7.6 Typography Token

文字节点：

```text
t_i = {
  fontSize,
  fontWeight,
  lineHeight,
  letterSpacing,
  color,
  bboxHeight,
  textRoleContext
}
```

文字样式距离：

```text
D_textStyle(i,j) =
  a * |fontSize_i - fontSize_j|
+ b * |lineHeight_i - lineHeight_j|
+ c * WeightMismatch(i,j)
+ d * D_color(color_i,color_j)
+ e * AlignMismatch(i,j)
```

聚类后输出：

```text
text/display
text/h1
text/h2
text/body
text/caption
text/button
text/label
```

语义分：

```text
TextRoleScore(t, role) =
  a * SizeRank(t)
+ b * PositionPrior(t)
+ c * RepetitionPattern(t)
+ d * ContainerContext(t)
```

例子：

```text
字号最大 + 页面顶部
=> h1 / display

按钮中心文字 + shape parent
=> button label

小字号 + 低对比 + 图片下方
=> caption
```

## 7.7 Shadow / Effect Token

阴影可以用四个值表达：

```text
shadow = [dx, dy, blur, spread, color]
```

两个阴影距离：

```text
D_shadow(s1,s2) =
  |dx1-dx2|
+ |dy1-dy2|
+ |blur1-blur2|
+ |spread1-spread2|
+ D_color(color1,color2)
```

聚类后：

```text
shadow-sm
shadow-md
shadow-lg
```

## 7.8 Token 覆盖率

```text
TokenCoverage =
  count(style values mapped to token)
  / count(all style values)
```

分类型：

```text
ColorTokenCoverage
SpacingTokenCoverage
RadiusTokenCoverage
TypographyTokenCoverage
ShadowTokenCoverage
```

## 7.9 小例子

按钮 A、B、C 的背景色：

```text
A = [0,120,255]
B = [1,119,254]
C = [0,121,255]
```

距离：

```text
D(A,B)=|0-1|+|120-119|+|255-254|=3
D(A,C)=1
```

如果：

```text
τ_color = 8
```

它们属于同一 token：

```text
color/primary = median = [0,120,255]
```

## 7.10 边界

```text
Token clustering 是归纳重复视觉值。
不是品牌命名。
不是设计师最终 design system 审核。
```

## 7.11 非目标

```text
不凭单个颜色就命名为 primary。
不把低频颜色全都生成 token。
不强制把所有像素颜色 token 化。
```

## 7.12 验收指标

```text
token precision
token recall
token coverage
wrong merge rate
wrong split rate
semantic naming accuracy
```

公式：

```text
WrongMergeRate =
  count(values in same predicted token but different expected token)
  / count(predicted token pairs)
```

```text
WrongSplitRate =
  count(values in different predicted tokens but same expected token)
  / count(expected token pairs)
```

---

# 第 8 章：Variant，组件变体与属性

Variant 是同一组件族内部的属性变化，例如 primary / secondary、small / medium / large、default / disabled / selected。

## 8.1 组件族

组件族：

```text
Family F = {S1, S2, ..., Sn}
```

满足：

```text
D_component(Si,Sj) <= τ_family
```

即结构相似。

## 8.2 属性向量

每个组件实例 Si 提取属性：

```text
Attr(Si) = {
  width,
  height,
  fillColor,
  borderColor,
  textColor,
  radius,
  opacity,
  iconPresence,
  textLength,
  stateHints
}
```

属性差：

```text
Δ_attr(Si,Sj) =
  [
    |width_i-width_j|,
    |height_i-height_j|,
    D_color(fill_i,fill_j),
    D_color(border_i,border_j),
    D_color(text_i,text_j),
    |radius_i-radius_j|,
    |opacity_i-opacity_j|,
    iconPresenceMismatch
  ]
```

## 8.3 Variant 轴

如果结构相同，但 fillColor 聚成多组：

```text
variantAxis = "type"
```

例如：

```text
primary / secondary / danger
```

如果高度聚成多组：

```text
variantAxis = "size"
```

例如：

```text
small / medium / large
```

如果 opacity 或 contrast 明显不同：

```text
variantAxis = "state"
```

例如：

```text
default / disabled
```

## 8.4 轴独立性

变体轴应该尽量独立。

如果 size 改变只影响 height/width，不影响 color：

```text
Independent(size,color) = high
```

定义：

```text
AxisIndependence(A,B) =
  1 - Correlation(Δ_A, Δ_B)
```

如果两个属性总是一起变：

```text
AxisIndependence 低
```

说明不该拆成两个轴，可能是一个组合 variant。

## 8.5 Disabled 分数

```text
DisabledScore(S) =
  a * (1 - opacity)
+ b * LowContrastScore
+ c * GraynessScore
```

灰度分：

```text
Grayness(c) =
  1 - (max(r,g,b)-min(r,g,b)) / 255
```

如果：

```text
DisabledScore >= τ_disabled
```

则：

```text
state = disabled
```

## 8.6 Selected 分数

Tab / nav item 的 selected 通常有：

```text
更强文字颜色
底线
背景高亮
图标高亮
```

定义：

```text
SelectedScore(S) =
  a * TextContrastGain
+ b * HasUnderline
+ c * BackgroundHighlight
+ d * IconHighlight
```

如果：

```text
SelectedScore >= τ_selected
```

则：

```text
state = selected
```

## 8.7 小例子

三个按钮：

```text
B1: height=40, fill=blue, text=white
B2: height=40, fill=white, border=blue, text=blue
B3: height=32, fill=blue, text=white
```

结构相似：

```text
D_component(B1,B2) <= τ
D_component(B1,B3) <= τ
```

属性差：

```text
B1 vs B2: color differs
B1 vs B3: size differs
```

所以：

```text
variant axes:
  type = primary / secondary
  size = medium / small
```

## 8.8 边界

```text
Variant 是同一组件族内部的属性变化。
不是完全不同组件。
```

## 8.9 非目标

```text
不从单个按钮推 variant。
不把随机颜色差当 variant。
不推断真实业务 action。
```

## 8.10 验收指标

```text
variant family precision
variant axis accuracy
state classification accuracy
wrong variant merge rate
instance property correctness
```

公式：

```text
AxisAccuracy =
  correctPredictedAxes / predictedAxes
```

---

# 第 9 章：Vectorization，矢量化

矢量化的目标是：

```text
把简单 shape / icon 的边界，从像素 mask 转成可编辑 path。
```

但复杂图片不要强行 vectorize。

## 9.1 输入

mask：

```text
M(x,y) ∈ {0,1}
```

边界点：

```text
Boundary(M) = {p1, p2, ..., pn}
p_i = [x_i, y_i]
```

## 9.2 线段拟合

给一段边界点：

```text
P = {p_s, ..., p_t}
```

用线段 a->b 拟合。

点到直线距离：

```text
d(p, line(a,b))
```

线段误差：

```text
E_line(a,b,P) =
  sum(d(p_i, line(a,b))^2)
```

如果：

```text
E_line <= τ_line
```

这段边界可以用一条直线表示。

## 9.3 曲线拟合

三次贝塞尔曲线：

```text
Bezier(t) =
  (1-t)^3 P0
+ 3(1-t)^2 t P1
+ 3(1-t)t^2 P2
+ t^3 P3
```

其中：

```text
0 <= t <= 1
```

曲线误差：

```text
E_curve(P0,P1,P2,P3) =
  sum(|p_i - Bezier(t_i)|^2)
```

## 9.4 复杂度惩罚

如果只追求误差最小，会把每个像素都变成 path 点，这不可编辑。

所以总能量：

```text
E_vector =
  E_fit
+ λ_segment * segmentCount
+ λ_point * pointCount
+ λ_curve * curveCount
```

选择：

```text
Path* = argmin E_vector
```

大白话：

```text
既要像，也要简单。
```

## 9.5 闭合路径

如果首尾点很近：

```text
distance(p1,pn) <= τ_close
```

则：

```text
isClosedPath = true
```

否则：

```text
isClosedPath = false
```

## 9.6 填充和描边

如果 mask 内部颜色稳定：

```text
ColorVarianceInside <= τ_fill
```

则：

```text
fillColor = medianColorInside
```

如果边界附近有稳定细线：

```text
strokeWidth = estimatedBoundaryThickness
strokeColor = medianBoundaryColor
```

## 9.7 Vectorization 许可

```text
VectorizeAllowed(region) = true
iff
  pixelOwner ∈ {shape_geometry, raster_icon}
  and textureScore <= τ_texture_vector
  and colorCount <= τ_color_vector
  and E_vector <= τ_vector
  and segmentCount <= K_segment
```

如果不满足：

```text
preserve as raster_icon or image
```

这继承了 M29 的原则：

```text
复杂像素宁可 raster，不要错转成 shape。
```

## 9.8 小例子：三角形 icon

边界有三条直边。

如果每条边：

```text
E_line <= τ_line
```

总 segmentCount = 3：

```text
E_vector 很低
```

所以：

```text
VectorNode with 3 line segments
```

小头像：

```text
colorCount = 120
textureScore = 0.35
```

即使边界像圆：

```text
VectorizeAllowed = false
```

应该保留 raster。

## 9.9 边界

```text
Vectorization 是几何路径重建。
不是语义图标识别。
不是把照片变成矢量插画。
```

## 9.10 非目标

```text
不把复杂图像强制 SVG 化。
不为了可编辑牺牲视觉保真。
不把低置信 OCR 裁片转路径。
```

## 9.11 验收指标

```text
path visual error
segment count
editable path simplicity
false vectorization rate
raster fallback correctness
```

公式：

```text
VectorError =
  area(mask XOR render(path)) / area(mask)
```

```text
VectorSimplicity =
  1 / (1 + segmentCount)
```

---

# 第 10 章：Figma Materialization，Figma 节点生成权限

这一层决定：

```text
哪些证据只 report，
哪些可以变成 visible node，
哪些可以变成 group/frame，
哪些可以变成 Auto Layout，
哪些可以变成 Component/Instance，
哪些可以绑定 token。
```

## 10.1 Materialization Level

定义：

```text
L0 = diagnostic_only
L1 = flat_visible_node
L2 = group
L3 = frame
L4 = auto_layout_frame
L5 = component_candidate
L6 = component_instance
L7 = token_bound_design_system_node
```

当前 M29 Direct 大概只到 L1：

```text
fallback image + accepted flat replay nodes
```

M29.4 只是 report，不创建组件。

## 10.2 L1：可见节点许可

```text
VisibleNodeAllowed(o) = true
iff
  replayDecision(o) ∈ {text_replay, image_replay, icon_replay, shape_replay}
  and confidence(o) != low
  and pixelOwner(o) matches replayDecision(o)
```

对应：

```text
editable_text + text_replay -> TextNode
preserve_raster + image_replay -> ImageNode
raster_icon + icon_replay -> ImageNode or VectorNode
shape_geometry + shape_replay -> Rectangle/Ellipse/Vector
```

## 10.3 L2：Group 许可

```text
GroupAllowed(G) = true
iff
  GroupScore(G) >= τ_group
  and OverGroupRisk(G) <= τ_overgroup
```

Group 是编辑组织，不一定改变布局。

## 10.4 L3：Frame 许可

Frame 比 Group 更强，需要容器证据：

```text
FrameAllowed(G) = true
iff
  GroupAllowed(G)
  and (
    hasExplicitContainerShape(G)
    or ParentCost evidence strong
    or LayoutEnergy evidence strong
  )
```

显式容器：

```text
hasExplicitContainerShape(G) =
  exists A where
    pixelOwner(A)=shape_geometry
    and contains(A, bbox(G))
    and ParentTypeScore(A,G) high
```

## 10.5 L4：Auto Layout Frame 许可

```text
AutoLayoutFrameAllowed(G) = true
iff
  FrameAllowed(G)
  and AutoLayoutAllowed(G)
  and AutoLayoutDrift <= τ_drift
```

## 10.6 L5：Component Candidate 许可

```text
ComponentCandidateAllowed(S) = true
iff
  RepeatCount(S) >= 2
  and D_component family mean <= τ_component
  and SlotConsistency >= τ_slot
```

这一步可以在 Figma 里创建标注或分组，但不一定创建真正 Component。

## 10.7 L6：Component / Instance 许可

```text
ComponentAllowed(Family) = true
iff
  ComponentCandidateAllowed
  and RepeatCount >= τ_repeat_strong
  and VisualDriftAfterInstance <= τ_instance_drift
  and OverrideMappingCorrectness >= τ_override
```

实例化后，每个 instance 的 override：

```text
Override(instance_i) =
  values different from master component:
    textValue
    imageSource
    variant
    size
    state
```

如果 override 太复杂：

```text
OverrideComplexity > τ_override_complex
```

说明组件抽象不稳，不应该创建真正 Component。

## 10.8 L7：Token Bound Node 许可

```text
TokenBindAllowed(node, token) = true
iff
  D_style(node.value, token.value) <= τ_token_bind
  and token confidence >= τ_token_conf
```

例如颜色：

```text
D_color(node.fill, tokenColor) <= τ_color_bind
```

## 10.9 图层顺序

M29 当前 z-order：

```text
shape/support/background -> image -> icon -> text
```

后续层级树里，子节点顺序：

```text
zIndex(o) =
  ownerZRank(pixelOwner(o))
+ sourceOrderCorrection
+ overlayBoost
```

基础 rank：

```text
shape/background = 0
image = 1
icon/vector = 2
text = 3
overlay = 4
```

## 10.10 小例子

搜索框：

```text
background shape S
search icon I
placeholder text T
```

如果：

```text
S contains I and T
GroupScore({S,I,T}) high
E_row({I,T}) low
S 是显式 container
```

则：

```text
L1: S/I/T visible
L2: group
L3: frame
L4: horizontal Auto Layout frame
```

如果页面有 5 个相似搜索框：

```text
RepeatCount >= 5
SlotConsistency high
```

则：

```text
L5: component candidate
L6: component / instance
```

## 10.11 边界

```text
Materialization 是权限系统。
不是识别系统。
前面证据不够，这里必须拒绝。
```

## 10.12 非目标

```text
不把 weak cluster 直接转 Component。
不把所有 group 转 Frame。
不把所有 Frame 转 Auto Layout。
不强制绑定 token。
```

## 10.13 验收指标

```text
materialization precision
wrong component creation rate
wrong frame creation rate
auto layout drift
token binding accuracy
figma edit repair cost
```

公式：

```text
WrongMaterializationRate =
  count(materialized level > expected level)
  / count(materialized nodes)
```

---

# 第 11 章：Quality Metrics，质量与修复成本

最终目标不是“像 Codia 一样多生成”，而是：

```text
视觉像
结构对
可编辑
误伤少
用户好修
```

## 11.1 Visual Fidelity，视觉还原

源图像：

```text
P
```

Figma 渲染图：

```text
R
```

像素误差：

```text
E_pixel =
  sum(|P(x,y) - R(x,y)|) / totalPixels
```

视觉分：

```text
VisualFidelity =
  1 - normalized(E_pixel)
```

但注意：

```text
视觉像 ≠ 可编辑正确
```

## 11.2 Object Fidelity，对象还原

对象匹配使用 IoU：

```text
ObjectMatched(pred, gt) =
  IoU(pred.bbox, gt.bbox) >= τ_iou
  and type(pred) = type(gt)
```

对象 precision：

```text
ObjectPrecision =
  matchedPredictedObjects / predictedObjects
```

对象 recall：

```text
ObjectRecall =
  matchedGroundTruthObjects / groundTruthObjects
```

## 11.3 Ownership Correctness

```text
OwnershipAccuracy =
  count(predictedOwner(o)=expectedOwner(o)) / count(objects)
```

面积加权：

```text
OwnershipAreaAccuracy =
  area(correctlyOwnedPixels) / area(allOwnedPixels)
```

## 11.4 Editability Score

可编辑面积：

```text
editableArea =
  area(editable_text)
+ area(shape_geometry)
+ area(vector_nodes)
+ area(auto_layout_containers)
```

总 UI 面积：

```text
uiArea = area(non-background UI)
```

可编辑率：

```text
EditabilityScore =
  editableArea / uiArea
```

但要扣误伤。

## 11.5 False Editable Penalty

复杂图片误转 shape：

```text
FalseShapePenalty =
  area(wrongShape) * riskWeight_shape
```

低置信 OCR 误转文本：

```text
FalseTextPenalty =
  TextEditDistance(predText, trueText) * riskWeight_text
```

错误擦图：

```text
CleanupPenalty =
  area(wrongErasedPixels) * riskWeight_cleanup
```

总误伤：

```text
FalseEditablePenalty =
  FalseShapePenalty
+ FalseTextPenalty
+ CleanupPenalty
+ WrongComponentPenalty
+ WrongAutoLayoutPenalty
```

## 11.6 Hierarchy Score

```text
HierarchyScore =
  correctParentEdges / expectedParentEdges
```

也可用边集合：

```text
PredEdges = {(parent(i), i)}
TrueEdges = {(expectedParent(i), i)}
```

```text
HierarchyF1 =
  2 * Precision * Recall / (Precision + Recall)
```

## 11.7 Layout Score

```text
LayoutTypeAccuracy =
  count(predictedLayout(C)=expectedLayout(C)) / count(C)
```

布局参数误差：

```text
LayoutParamError =
  |predGap - trueGap|
+ |predPaddingL - truePaddingL|
+ |predPaddingR - truePaddingR|
+ |predPaddingT - truePaddingT|
+ |predPaddingB - truePaddingB|
```

## 11.8 Component Score

```text
ComponentPrecision =
  trueComponentCandidates / predictedComponentCandidates
```

```text
ComponentRecall =
  trueComponentCandidates / expectedComponentCandidates
```

slot 分：

```text
SlotScore =
  correctSlots / expectedSlots
```

## 11.9 Token Score

```text
TokenCoverage =
  styleValuesMappedToTokens / allStyleValues
```

```text
TokenPrecision =
  correctTokenAssignments / predictedTokenAssignments
```

## 11.10 User Repair Cost

这是最终产品指标。

定义每种错误的修复成本：

```text
cost(move node) = 1
cost(rename layer) = 1
cost(change color) = 1
cost(edit text) = 2
cost(recreate Auto Layout) = 5
cost(detach wrong component) = 8
cost(recover erased image) = 20
```

总修复成本：

```text
RepairCost =
  sum(error_i * cost_i)
```

归一化：

```text
RepairCostNorm =
  RepairCost / pageAreaOrNodeCount
```

最终质量函数：

```text
Q =
  a * VisualFidelity
+ b * OwnershipAccuracy
+ c * EditabilityScore
+ d * HierarchyScore
+ e * LayoutScore
+ f * ComponentPrecision
+ g * TokenPrecision
- h * FalseEditablePenalty
- k * RepairCostNorm
```

大白话：

```text
能编辑是加分。
错编辑是重罚。
```

## 11.11 验收分层

建议验收分层，而不是一个总分：

```text
Level A: flat replay fidelity
Level B: ownership correctness
Level C: hierarchy correctness
Level D: layout correctness
Level E: component correctness
Level F: token/design system correctness
Level G: Figma repair cost
```

每一层都要单独过门槛。

---

# 第 12 章：总线合同

## 12.1 总 pipeline

```text
P: source pixels
T: OCR boxes
G29: primitive graph
O: source objects
I: media internal decomposition candidates
R: region relation graph
H: hierarchy tree
G: sibling groups
L: layout models
C: component candidates
D: design tokens
V: vector paths
M: materialization plan
F: Figma nodes
Q: quality report
```

数学上：

```text
O = SourceObjectResolver(P,T,G29)
I = MediaInternalDecompose(P,T,G29,O)
R = RelationKernel(O)
H = HierarchyInfer(O,R)
G = GroupInfer(O,R,H)
L = LayoutInfer(G,R)
C = ComponentInfer(G,L,R)
D = TokenInfer(O,G,C)
V = VectorInfer(P,O,I)
M = MaterializationPermission(O,I,H,G,L,C,D,V)
F = FigmaMaterialize(M)
Q = Evaluate(P,F,O,I,H,L,C,D)
```

## 12.2 最重要的权限顺序

```text
1. Source object 稳
2. Pixel owner 稳
3. Relation 稳
4. Cleanup 权限稳
5. Composite media 内部 foreground 候选只能先 report
6. Hierarchy 才能进
7. Layout 才能进
8. Auto Layout 才能进
9. Component 才能进
10. Token binding 才能进
11. Figma materialization 才能强承诺
```

## 12.3 核心禁止规则

```text
Rule 1:
  不能从 geometry fit 直接到 vector/shape。

Rule 2:
  不能从 row_like 直接到 Auto Layout。

Rule 3:
  不能从 repeated_size 直接到 Component。

Rule 4:
  不能从颜色相近直接到 design token。

Rule 5:
  不能从单张图直接承诺响应式断点。

Rule 6:
  不能没有 cleanup authorization 就擦图。

Rule 7:
  不能为了提高 editability 牺牲 high-risk raster fidelity。

Rule 8:
  不能因为 preserve_raster media 内存在 OCR 或 raw symbol，就直接创建内部 visible node。

Rule 9:
  不能用文案、文件名、行业、主题色或固定 bbox 判定 internal icon。
```

---

# 第 13 章：按开发阶段落地的数学顺序

建议按这个顺序推：

```text
Phase 1:
  Pixel Ownership Conservation
  Cleanup Authorization
  Quality Metrics v1
  Media Internal Decomposition formula

Phase 2:
  Hierarchy Tree
  Group Candidate
  Frame Permission

Phase 3:
  Layout Energy
  Auto Layout Permission
  Auto Layout Drift Test

Phase 4:
  Component Isomorphism
  Slot Matching
  Component Candidate

Phase 5:
  Design Token Clustering
  Token Binding Permission
  Variant Axis Inference

Phase 6:
  Vectorization
  Path Simplicity vs Fidelity
  Icon/vector fallback

Phase 7:
  True Figma Component/Instance
  Design system export
  Plugin repair UI
```

当前 C 阶段按更细执行相位拆分：

```text
C0:
  Quality benchmark / repair-cost calibration

C1:
  Hierarchy + sibling group confidence calibration

C2:
  Auto Layout permission calibration

C3:
  Component isomorphism report-only

C4:
  Variant report-only

C5:
  Vectorization report-only / opt-in

C6:
  Controlled materialization experiment

M29.6 parallel source-evidence track:
  Media Internal Decomposition report-only
  Transparent Asset Extraction report-only
  Execution-supported internal source promotion experiment
  M29.5 replay/cleanup authorization
  Materializer consumption of M29.5-authorized internal assets
```

---

# 最后总结

要达到 Codia 级图片转 Figma，不是“多接几个模型”，而是把每个强能力都变成一个数学许可：

```text
可编辑文本
= OCR + 背景置信 + owner 正确 + cleanup 授权

可编辑 shape
= geometry fit + shape safety + ownership 正确

层级树
= containment + tightness + padding + owner compatibility + z-order

Auto Layout
= layout energy 低 + gap/padding/alignment 稳 + drift 小

组件化
= 子图同构 + slot 一致 + 重复次数足够 + override 简单

设计系统
= 颜色/间距/字号/圆角/阴影聚类稳定 + token 绑定准确

Variant
= 同一组件族内属性变化有稳定轴

Vectorization
= mask path 拟合误差低 + path 复杂度低 + 非复杂纹理

Figma materialization
= 每一层证据达到对应 Level 权限

质量
= 视觉还原 + 可编辑性 - 误编辑 - 修复成本
```

最关键的一句：

```text
M29 解决“这些像素能不能安全重放”；
Codia 级后端还要继续解决“这些安全对象如何组成层级、布局、组件、token 和 Figma 设计系统”。
```

---

## 参考输入文档

- `m29-experimental-mathematical-contract.md`
- `m29-math-from-first-principles.md`

## 参考公开资料方向

- Codia Screenshot to Figma / VisualStruct / developer schema 公开页面
- Figma Plugin API: FrameNode、ComponentNode、Auto Layout / layoutMode 等节点属性
