# 图片转 Figma 全链路第一性原理本地核对

- 状态：reference audit
- 创建日期：2026-05-25
- 核对 commit：`246979acb7a637db55e84320b0b0fda486518778`

## 结论

用户提供的全链路判断方向基本正确：

```text
输入图片
  -> 像素 / PNG / PSD / PDF 解析
  -> primitive evidence
  -> source object
  -> pixel owner
  -> relation graph
  -> hierarchy tree
  -> group / frame
  -> layout energy
  -> auto layout
  -> component isomorphism
  -> design token
  -> variant
  -> vectorization
  -> Figma materialization
  -> quality metrics
```

但和本地代码核对后，需要修正三点：

1. 当前 runtime 只到 M29 plan-driven flat materialization，不运行 hierarchy、Auto Layout、component、token、variant、vectorization 或 quality benchmark。
2. 后半段不是完全空白；[m29-to-codia-math-contract-v0.1.md](../architecture/m29-to-codia-math-contract-v0.1.md) 已经有更完整的未来数学草案。
3. 最关键的下一个工程缺口不是组件化，而是把 `Pixel Ownership Conservation` 做成可审计 report，然后再基于它做 hierarchy / group / layout。

## 本地核对方法

核对对象：

```text
backend/app/
backend/tests/
docs/architecture/
docs/engineering/
docs/roadmap.md
packages/
figma-plugin/src/
```

关键事实源：

```text
docs/architecture/backend.md
docs/engineering/current-mainline-code-map.md
docs/architecture/m29-experimental-mathematical-contract.md
docs/architecture/m29-math-from-first-principles.md
docs/architecture/m29-to-codia-math-contract-v0.1.md
docs/engineering/m29-contract-regression-matrix.md
```

当前代码入口仍是：

```text
POST /api/upload-preview
  -> OCR
  -> raw M29 visual primitive graph
  -> M29.2 source-level UI physical graph
  -> M29.3.1 source relation graph report
  -> M29.4 stable design cluster report
  -> M29.5 replay quality plan
  -> M29 plan-driven DSL materialization
  -> /api/tasks/{taskId}/dsl
```

## 逐层核对

| 层级 | 本地代码事实 | 判断 |
| --- | --- | --- |
| PNG/像素输入 | `backend/app/png_tools/` 已拆成 `metadata.py`、`decode.py`、`encode.py`、`crop.py`、`sampling.py`、`geometry.py`。支持 PNG metadata、decode、crop、fill、背景采样、文字前景采样。 | PNG/JPG 截图路径的基础够用；PSD/PDF/Web/HTML DOM source truth 当前不是 runtime 能力。 |
| bbox 几何 | `backend/app/visual_primitive/bbox.py` 和 `backend/app/region_relation_kernel.py` 有 axis-aligned bbox、area、contains、IoU、gap 等函数。 | 用户判断真实。当前主要是 axis-aligned bbox；旋转/transform matrix 未实现。 |
| mask / component | `backend/app/visual_primitive/mask.py`、`components.py` 有 binary mask、union/subtract、bbox overlap、connected components。 | 基础 component 真实存在；dilate/erode/open/close、contour tracing、多尺度 merge/split 未实现。 |
| primitive evidence | `backend/app/visual_primitive/` 有 raw M29 types、support、detectors、geometry、relations、artifacts、validation。 | M29 primitive evidence 已落地；更强 UI role hint 只以有限 `visualKind` / cluster evidence 存在，不是完整 UI element recognition。 |
| geometry fit | `backend/app/visual_primitive/geometry.py` 有 shape geometry fit、radius、occupancy、rect/ellipse/pill 等判断。 | 基础 shape 真实存在；复杂 vector path、多边形、Bezier、图标 path simplification 未实现。 |
| pixel owner | `backend/app/source_ui_physical_graph/` 输出 `visualKind`、`pixelOwner`、`replayDecision`、confidence、reasons、risks。测试矩阵覆盖 editable text、preserve raster、raster icon、shape geometry、diagnostic 等边界。 | 局部 owner 决策真实存在；全局 pixel-level ownership map / conservation report 还没有。 |
| region relation | `backend/app/region_relation_kernel.py` 和 `region_relation_graph_report.py` 有 pairwise bbox relation graph。 | Pairwise relation 真实存在；三元关系、序列关系、网格关系、父子方向置信度还没成为 runtime 合同。 |
| replay plan | `backend/app/m29_replay_plan/` 有 action decision、priority、node budget、dedupe、cleanup target 授权。 | Flat replay plan 真实存在，是当前 materialization 权限源。 |
| plan materializer | `backend/app/plan_materializer/` 只执行 M29.5 plan，负责 text/shape/image/icon replay、fallback cleanup、copied image cleanup。 | 当前正式 DSL producer 真实存在，但它不是高级 hierarchy/component materializer。 |
| hierarchy tree | 旧 M37/M38 hierarchy 文件已从 backend runtime 删除；当前 docs 明确它们是历史。DSL/schema/renderer 有透明 group 支持测试，但当前 upload mainline 不生成 hierarchy。 | 用户分析里“有雏形”的说法需要收紧：raw containment relation 存在，product hierarchy runtime 当前不存在。 |
| sibling group | `backend/app/stable_design_cluster/` 输出 M29.4 weak structural evidence。 | 弱 cluster 真实存在，但它只进入解释性 evidence，不授予 group/component/materialization 权限。 |
| layout energy | `docs/architecture/m29-to-codia-math-contract-v0.1.md` 已有 Row/Column/Grid/Masonry/Overlay energy 草案。 | 这是未来数学草案，不是当前代码。 |
| Auto Layout | 产品和架构文档明确当前不做 Auto Layout；未来草案已有 permission、gap、padding、alignment、drift 指标。 | 不是 runtime 能力。不能从 M29.4 row_like 直接跳到 Auto Layout。 |
| component isomorphism | 未来草案已有 node/edge/normalized bbox/slot distance 方向。当前代码没有 component family materialization。 | 理论草案存在，工程未落地。 |
| design token | 未来草案有 color/spacing/radius/typography/effect token 和 coverage 指标。 | 当前 runtime 不做 token clustering 或 Figma variables binding。 |
| variant | 未来草案有 family/axis/disabled/selected 分数。 | 当前 runtime 不做 variant。应等 component family 稳定后再做。 |
| vectorization | 未来草案有 path fitting/complexity/permission。当前 raw M29 symbol/icon 仍以 raster icon 为主。 | 当前 runtime 不做 SVG/Figma vectorization。 |
| Figma materialization | 当前 materialization 是 flat DSL visible nodes，再由 Renderer 写 Figma。未来草案定义 L0-L7 permission。 | 当前只覆盖 L1 flat visible node；Group/Frame/Auto Layout/Component/Token-bound node 是未来权限层。 |
| quality metrics | 当前有测试矩阵、materialization report、stage artifacts；未来草案有 visual fidelity、ownership、editability、hierarchy、layout、component、token、repair cost。 | 当前缺 ground truth benchmark、人工修复成本、视觉 diff 权重和多页面评测。 |

## 已有但容易被误读的东西

### `build_containment_relations` 不是产品 hierarchy

`backend/app/visual_primitive/relations.py` 的 containment relation 是 raw primitive relation evidence。它描述物理包含关系，不等于 Figma parent/child，也不授权 DSL group/frame。

当前 product mainline 不运行旧 M37/M38 hierarchy runtime。相关 ADR、completed plans 和 tests 是历史资料或 schema/renderer 能力，不是当前 upload-preview 行为。

### M29.4 cluster 不是 group/component

`stable_design_cluster` 能给出 row/column、icon+text、media+text 等 weak evidence，但当前规则明确：

```text
M29.4 weak cluster -> explanation only
M29.5 replay plan -> materialization order / budget / cleanup authorization
plan_materializer -> execute plan only
```

不能把 `row_like`、`repeated_size`、`icon_text` 直接升成 group、Auto Layout 或 Component。

### Pixel Ownership Conservation 还没落成一等 report

当前已有：

```text
pixelOwner per source object
replayDecision per source object
cleanupTargets in M29.5
materializer cleanup authorization checks
```

当前还没有：

```text
per-pixel or sampled pixel ownership map
foreground/background ownership collision report
cleanup coverage report tied to owner conservation
owner conservation acceptance metric
```

所以用户判断“局部 owner 已有，全局 owner 守恒还缺”是准确的。

## 和用户输入分析的修正表

| 用户分析点 | 本地核对结论 |
| --- | --- |
| “M29 已有 bbox / mask / primitive / owner / relation / replay plan” | 准确。代码和测试都存在。 |
| “后半段已有方向但不够可执行” | 基本准确，但仓库中已有更完整的 `m29-to-codia` 数学草案，应作为未来 contract 起点。 |
| “明显缺 PSD/PDF/Web source truth” | 准确。当前 runtime 是 PNG upload mainline。 |
| “Hierarchy 有 build_containment_relations 雏形” | 需要修正。raw containment evidence 有，当前 product hierarchy 没有。 |
| “M29.4 有 weak cluster 但不是 group/component/layout tree” | 准确。 |
| “Layout Energy/Auto Layout/Component/Token/Variant/Vectorization 需要继续补” | 准确，但这些已在未来草案中有比用户输入更详细的公式框架。 |
| “最优先 Pixel Ownership Conservation + Hierarchy Tree” | 方向正确，但顺序应更严格：先做 ownership conservation report，再做 hierarchy readiness report；不要同时改 materialization。 |

## 推荐下一步

不要马上做 Auto Layout、Component、Token 或 Vectorization。那会把错误 source object 包装成更复杂的错误。

建议下一阶段只做 report-only：

```text
Phase A: Pixel Ownership Conservation Report
  输入：source PNG, raw M29, M29.2, M29.3, M29.5, materialization report
  输出：ownership conservation report
  不改 DSL / Figma / replay plan / cleanup 行为

Phase B: Hierarchy Readiness v2 Report
  输入：M29.2 source objects, relation graph, ownership conservation report, M29.4 weak clusters
  输出：候选 parent/group/frame readiness report
  不创建 group/frame

Phase C: Group Candidate Conflict Resolution
  输入：Hierarchy readiness v2 + weak clusters
  输出：group candidate graph + conflict resolution report
  仍不做 Auto Layout / Component
```

只有当 A/B/C 的 false positive 受控，才进入：

```text
Layout Energy
Auto Layout Permission
Component Isomorphism
Design Token
Variant
Vectorization
Advanced Figma Materialization
Quality Metrics
```

## 当前禁止跳跃

```text
不能从 bbox contains 直接到 hierarchy。
不能从 row_like 直接到 Auto Layout。
不能从 repeated_size 直接到 Component。
不能从颜色相似直接到 Design Token。
不能从 mask contour 直接到 Vector。
不能没有 M29.5 cleanup authorization 就擦 fallback 或 copied image asset。
```

## 最小验证建议

下一阶段如果做 `Pixel Ownership Conservation Report`，focused tests 应覆盖：

```text
editable text over fallback: fallback cleanup allowed only by plan target
editable text inside copied media: copied asset cleanup allowed only by plan target
shape behind text: shape owns background, text owns foreground
raster icon near text: icon/text ownership must not collide
preserve raster text: no editable node, no fallback cleanup
diagnostic node: no visible owner claim
```

无效信号：

```text
report 为了通过而按颜色、文案、主题、文件名或固定 bbox 特化
materializer 重新判断 owner
Renderer 或 plugin 修 owner 错误
M29.4 cluster 直接产生 group/component/autolayout
```
