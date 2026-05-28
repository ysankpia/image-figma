# 082 Go M29 Physical Evidence Kernel

- 状态：active
- 创建日期：2026-05-28
- 分支：`feat/final-m29-visual-compiler`
- 负责人：Codex

## Goal

从 `main` 重新开始，不继续沿着 model-first 或 Compiler V2 实验分支扩展。第一阶段只用 Go 从 0 重写 M29.0 的物理像素证据 kernel。

目标输出不是 Figma 设计稿，也不是 Codia-like AST，而是一个干净、可审计、可复跑的物理证据文档：

```text
PNG
-> optional OCR bbox mask
-> Go M29.0 physical evidence kernel
-> m29_physical_evidence.v1.json
-> masks / crops / debug overlay
```

第一性原理判断：

```text
M29.0 是 pixel evidence provider，不是 UI object authority。
Go 第一阶段解决的是证据 kernel 和合同，不是并发，不是 API，不是插件。
Codia-like 只作为后续 LayerAST 的形状约束，不进入 M29.0 主输出。
```

## Non-Goals

第一阶段明确不做：

```text
不兼容 Python M29.0 nodes.json
不移动现有 backend/、figma-plugin/、packages/
不替换 /api/upload-preview
不启动 HTTP server
不接 DSL
不接 Renderer
不接 Figma plugin
不生成 VisualElement / LayerAST
不做 button/card/modal/tab/list/component 语义
不做 source ownership / replay / cleanup / promotion / rerun
不加 OpenCV / GoCV / libvips / bild 等 CV 依赖
不按文件名、文案、品牌、颜色、坐标、task id 特化
```

CV 判断：

```text
CV 数学可以存在于 Go 自写 kernel：mask、connected components、bbox、局部背景、局部对比度、边缘/纹理测量。
CV 库依赖暂不进入第一阶段。只有当 hard samples 证明某类失败由成熟 CV 算子稳定解决时，再以 measurement backend 形式引入。
```

## Directory

只新增 Go kernel 目录：

```text
services/backend-go/
  go.mod
  cmd/m29extract/
  internal/m29/contract/
  internal/m29/pipeline/
  internal/m29/imageio/
  internal/m29/ocr/
  internal/m29/mask/
  internal/m29/components/
  internal/m29/primitive/
  internal/m29/debug/
```

暂不做目标 monorepo 搬迁：

```text
backend/          保留为 Python MVP / 对照组
figma-plugin/     保留原位
packages/         保留原位
```

后续如果 Go kernel 证明方向正确，再单独计划迁移到：

```text
apps/plugin
services/backend-py
services/backend-go
packages/dsl-schema
packages/renderer
```

## Input Contract

CLI 第一版：

```bash
go run ./cmd/m29extract --input path/to/input.png --out path/to/output
go run ./cmd/m29extract --input path/to/input.png --ocr path/to/ocr.json --out path/to/output
go run ./cmd/m29extract --input path/to/input.png --ocr-provider baidu_ppocrv5 --out path/to/output
```

OCR 是可选输入。没有 OCR 时，M29.0 仍能跑，只是没有 text mask exclusion。

`--ocr-provider baidu_ppocrv5` 复用 Python 后端现有的百度 AI Studio PP-OCRv5 异步 API 环境变量：

```text
OCR_PROVIDER
OCR_MIN_CONFIDENCE
BAIDU_PADDLE_OCR_TOKEN
BAIDU_PADDLE_OCR_JOB_URL
BAIDU_PADDLE_OCR_MODEL
BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS
BAIDU_PADDLE_OCR_TIMEOUT_SECONDS
```

Go CLI 会从仓库祖先目录加载 `.env.local`，并把标准化后的 OCR 结果写到输出目录的 `ocr.json`。这只是 M29.0 text mask 输入，不改变 M29.0 的 UI 语义边界。

最小 OCR 输入合同：

```json
{
  "image": {"width": 1170, "height": 2532},
  "blocks": [
    {
      "id": "ocr_0001",
      "text": "允许",
      "bbox": {"x": 100, "y": 200, "width": 80, "height": 32}
    }
  ]
}
```

OCR 在 M29.0 中只用于：

```text
text mask exclusion
text_region primitive
text overlap / near_text / inside_text_mask measurement
```

OCR 在 M29.0 中不得用于：

```text
根据文字内容判断 button/card/tab/modal
根据特定文案晋升、删除、合并
根据语言、品牌词、页面词汇分类
```

## Output Contract

主输出文件：

```text
m29_physical_evidence.v1.json
```

辅助输出：

```text
masks/*.png
crops/*.png
debug_overlay.png
preview_sheet.png
```

文档根结构：

```json
{
  "schemaName": "M29PhysicalEvidence",
  "version": "1.0",
  "generator": {"name": "go-m29", "mode": "purego"},
  "image": {"width": 1170, "height": 2532, "sourcePath": "input.png"},
  "ocr": {"provided": true, "blockCount": 12},
  "primitives": [],
  "physicalRelations": [],
  "assets": [],
  "diagnostics": {}
}
```

Primitive 最小结构：

```json
{
  "id": "prim_0001",
  "primitiveType": "rect|surface_region|line|image_region|symbol_region|text_region|unknown_region",
  "bbox": {"x": 12, "y": 40, "width": 300, "height": 80},
  "maskRef": "masks/prim_0001.png",
  "cropRef": "crops/prim_0001.png",
  "source": {"kind": "pixel|ocr"},
  "measurements": {
    "area": 24000,
    "fillRatio": 0.94,
    "meanColor": "#ffffff",
    "colorCount": 2,
    "edgeDensity": 0.03,
    "textureScore": 0.08,
    "localContrast": 28.4,
    "cornerRadiusEstimate": 12
  },
  "compileHints": {
    "canBeLayerBackground": true,
    "canContainForeground": true,
    "canBeImage": false,
    "canBeIcon": false,
    "hasStableRectGeometry": true,
    "confidence": 0.86,
    "reasons": ["stable_rect", "low_texture", "foreground_inside"]
  }
}
```

`compileHints` 是给后续 EvidenceToken / RelationGraph / LayerAST 的提示，不是最终 UI 判断。

禁止输出这些旧链路字段：

```text
sourceObject
replayDecision
cleanupTarget
promotion
materializerDecision
control_background
raster_icon
m292ObjectId
m295PlanItemId
```

禁止输出这些 Codia-like 主节点类型：

```text
Body
Layer
Text
Image
VisualElement
```

## Stage Plan

### Stage 1: Contract And Skeleton

新增 `services/backend-go` Go module 和 `cmd/m29extract` CLI。

验收：

```text
go test ./...
go run ./cmd/m29extract --help
```

### Stage 2: Pure Go Physical Evidence

实现：

```text
PNG decode
optional OCR JSON parse
text mask exclusion
global/local background estimate
foreground mask
connected components
primitive measurement
primitive classification
physical relation basics
crop/mask/debug overlay output
```

### Stage 3: Tests

添加合成测试：

```text
solid rect -> rect
thin line -> line
text OCR mask prevents text pixels becoming symbol_region
complex color patch -> image_region or unknown_region
bad bbox rejected
output paths are relative
```

### Stage 4: Hard Sample Smoke

先跑小样本，不看 Figma，只看 evidence overlay：

```text
/Users/luhui/Downloads/UI Notes - ima App 截图 016.png
/Users/luhui/Downloads/525测试/微信图片_20260524225318_199_118.png
/Users/luhui/Downloads/城邦图/修好/ChatGPT Image 2026年5月25日 18_43_05 1.png
/Users/luhui/Downloads/m29
```

验收只看 M29.0 层：

```text
m29_physical_evidence.v1.json 存在
debug_overlay.png 存在且可读
文字区域不被大量吞掉
主要卡片/背景/图片/图标区域能作为 primitive 被看见
没有旧 promotion/rerun
没有 DSL/Figma 输出
没有 sample-specific 规则
```

### Stage 5: Batch Evidence Review Runner

新增 `cmd/m29batch`，只负责批量调用 Go M29.0 kernel 并生成审计报告：

```bash
go run ./cmd/m29batch \
  --input-dir /Users/luhui/Downloads/m29 \
  --ocr-provider baidu_ppocrv5 \
  --out tmp/batch-m29-ocr
```

输出：

```text
summary.json
review.md
cases/<slug>/m29_physical_evidence.v1.json
cases/<slug>/ocr.json
cases/<slug>/debug_overlay.png
cases/<slug>/preview_sheet.png
```

`m29batch` 不是质量判定器。它只统计：

```text
case count
completed / failed
ocr block count
primitive count
primitive type distribution
text mask pixel count
foreground pixel count
warning/error
artifact paths
```

验收重点仍是人工看 `preview_sheet.png` / `debug_overlay.png`：

```text
文字是否仍大量碎成 symbol_region
卡片/弹窗/背景是否作为物理区域被看见
图片区域是否被整块识别
图标/符号区域是否保留
噪声是否过多
```

禁止把 batch runner 做成：

```text
AST 生成器
DSL 生成器
Figma 判断器
自动阈值调参器
样本特化修复器
```

### Stage 6: EvidenceToken v1 Compiler

新增 Go EvidenceToken 层：

```text
m29_physical_evidence.v1.json
-> evidence_tokens.v1.json
-> token_overlay.png
-> token_preview_sheet.png
```

目标不是识别业务语义，而是把 raw primitive 收口成后续 RelationGraph / LayerAST 能消费的证据 token。

Token 类型第一版限制为：

```text
text_token
layer_background_token
surface_region_token
raster_region_token
symbol_cluster_token
texture_fragment_token
line_token
unknown_token
```

输入权限：

```text
text_region -> text_token
rect -> layer_background_token 或 line_token
surface_region -> surface_region_token
image_region -> raster_region_token
symbol_region -> symbol_cluster_token 或 texture_fragment_token
line -> line_token
unknown_region -> unknown_token 或 texture_fragment_token
```

关键归并原则：

```text
大 raster/image region 内部的碎片默认降级为 texture_fragment_token，不能独立进入 LayerAST。
相邻小 symbol_region 可按 bbox 邻近和面积限制合成 symbol_cluster_token。
OCR text_region 永远保留为 text_token。
稳定 rect 可成为 layer_background_token，但不能命名为 card/button/modal。
稳定低纹理面可成为 surface_region_token，但不能命名为 search/card/banner。
```

禁止：

```text
不输出 Body / Layer / Text / Image。
不输出 button / card / modal / tab / list。
不生成 DSL。
不删除 M29.0 primitive。
不按样本文案、品牌、固定坐标、文件名特化。
```

验收：

```text
raw primitive 数量明显高于 token 数量。
text_token 数量等于 OCR text_region 数量。
运营图/头像/大图内部纹理碎片不会成为主 token。
symbol_cluster_token 保留小图标/符号的可用候选。
token_overlay.png 可用于人工审计归并后的候选层。
```

### Stage 7: UI Surface Evidence Pass

补充 M29.0 物理层缺失的 UI 面证据。目标不是识别“搜索框”“轮播图”“卡片”，而是识别跨截图成立的 UI 物理不变量：

```text
局部低纹理稳定色面
局部低频平滑渐变面
带稳定边界/圆角暗示的容器面
可包含 OCR 文本、图标、按钮文字的面
```

新增 primitive：

```text
surface_region
```

`surface_region` 只能 claim：

```text
bbox
mask/crop
meanColor / colorCount / edgeDensity / textureScore / localContrast
canBeLayerBackground=true
canContainForeground=true
hasStableRectGeometry=true
```

`surface_region` 不能 claim：

```text
search input
button
card
banner
carousel
modal
DSL frame
cleanup ownership
```

第一版检测允许用通用 UI 物理约束：

```text
从 OCR 文本附近向外寻找连续低纹理面。
面与周围局部背景存在边界对比。
面内部可以包含文本 mask，不因为包含 OCR 就被前景 mask 切碎。
高频纹理区域仍保留为 image_region / raster_region。
低频平滑渐变不能因为颜色数量多直接判为 image_region。
```

禁止：

```text
不按“杭州市”“搜索”“立即办理”等文案触发。
不按固定 y 坐标、固定宽高、固定蓝色主题触发。
不把 surface_region 直接接入 LayerAST/DSL。
不让大 raster parent 吞掉 surface_region/text_region 的审计可见性。
```

验收样本：

```text
第二张政务样本：顶部搜索框白底应作为 surface_region 出现，内部 OCR 仍为 text_region。
第一张游戏样本：轮播图/运营图区至少保留 raster surface 证据，不强行矢量化内部图片。
通用测试：合成低纹理容器面应产出 surface_region，复杂高频图片不应误判为 surface_region。
```

### Stage 8: RelationGraph v1

新增 Go RelationGraph 层：

```text
evidence_tokens.v1.json
-> relation_graph.v1.json
-> relation_overlay.png
-> relation_report.md
```

目标不是识别 UI 语义，而是把 EvidenceToken 之间的空间事实变成可审计的关系边。

RelationGraph v1 只允许 claim：

```text
contains
inside_surface
foreground_inside_background
overlaps
adjacent_left / adjacent_right / adjacent_top / adjacent_bottom
same_row
same_column
same_band
raster_parts_same_region
near_duplicate
```

RelationGraph v1 不允许 claim：

```text
button
card
search
carousel
modal
tab
list
LayerAST node
DSL node
cleanup authorization
```

输入权限：

```text
main token 进入主关系图。
review token 可参与 weak relation。
suppressed token 默认不进主关系图。
```

核心原则：

```text
RelationGraph 只能加边，不能删除、合并、改写 EvidenceToken。
大 raster parent 只能建立 background/inside 关系，不能吞掉 surface/text。
PC/Web/App 都只能通过归一化几何指标判断，不能使用固定坐标、固定屏幕尺寸、文案、品牌、主题色。
```

通用 metrics：

```text
intersectionRatio
iou
childCoverage
parentCoverage
horizontalOverlapRatio
verticalOverlapRatio
gapX / gapY
centerDistance
areaRatio
```

验收样本：

```text
第二张政务样本：search surface token 应 contains/inside_surface 搜索文字、搜索按钮文字和图标候选。
第一张游戏样本：顶部两个 raster_region_token 应产生 adjacent / same_band / raster_parts_same_region 关系。
大 raster background 与内部 text/surface 只建立关系，不 suppress 它们。
```

输出报告：

```text
relation_graph.v1.json
relation_overlay.png
relation_report.md
```

禁止：

```text
不输出 Body / Layer / Text / Image。
不生成 DSL。
不按样本文案、品牌、固定坐标、文件名特化。
不把 same_band 直接解释成 carousel。
```

### Stage 9: VisualTree / LayerAST v0

新增 Go VisualTree 层：

```text
evidence_tokens.v1.json
relation_graph.v1.json
-> visual_tree.v1.json
-> visual_tree_overlay.png
-> visual_tree_report.md
```

目标是把物理证据 token 和空间关系编译成第一版可审计视觉树。它不是 DSL，不是 Figma 输出，也不是业务语义树。

VisualTree v0 只允许输出四类主节点：

```text
Body
Layer
Text
Image
```

节点权限：

```text
Body:
  只代表整张画布根节点。

Layer:
  代表有面积、可包含子节点的视觉容器。
  来源可以是 surface_region_token / layer_background_token / 有 children 的 raster_region_token。

Text:
  只来自 text_token。
  OCR 内容可进入 content.text，但 Text 不能被降级成 Image。

Image:
  代表不可拆或暂不拆的 raster/symbol/unknown 可见片段。
```

建树规则：

```text
只消费 RelationGraph 的 contains 关系选择父节点。
一个 child 有多个 contains parent 时，选择面积最小的 parent。
same_row / same_column / adjacent / same_band 只作为 layout hint，不参与父子树。
子节点 layout 必须转换成 parent-relative。
没有 contains relation 时不根据 bbox 重新猜父子，直接挂 Body。
```

背景处理：

```text
raster_region_token 如果有 foreground children，则表达为 Layer，并记录 style.backgroundRef。
原始 raster token id 必须保留在 sourceRefs / backgroundTokenIds。
背景不能吞掉内部 Text/Image children。
```

禁止：

```text
不输出 button / card / search / carousel / modal / tab / list。
不把 repeated_group / navigation_cluster / media_panel 作为主节点类型。
不做 Auto Layout / Flex 求解。
不做 remove_bg / SVG vectorization。
不生成 DSL。
不按样本文案、品牌、固定坐标、文件名特化。
```

验收：

```text
Text 节点数量等于可进入主图的 text_token 数量。
surface 内部 text/image 通过 contains relation 成为 Layer children。
raster background 有 children 时不再作为平级 Image 吞掉前景。
visual_tree_report.md 能解释父子来源 relation。
visual_tree_overlay.png 只展示树节点 bbox，不画 layout hint 蜘蛛网。
```

### Stage 10: VisualGroup v0

在 VisualTree 内部新增中性视觉分组 pass：

```text
RelationGraph
-> VisualGroup v0
-> VisualTree v1
```

目标是减少 Body 下的平铺节点，把明显属于同一视觉行/区域的 sibling 编译成 synthetic Layer。它仍然不是业务语义层。

允许使用：

```text
same_row
same_band
raster_parts_same_region
```

暂不使用：

```text
same_column
```

原因：

```text
纵向关系在长页面上容易跨多个真实区域串成大组。
在没有更强边界证据前，same_column 只能留作 layout_hint，不能进入父子树。
```

VisualGroup v0 输出规则：

```text
synthetic group 仍然是 Layer。
通过 meta.synthetic=true / meta.groupKind 标记来源。
groupKind 只能是 row_group / band_group / raster_parts_group。
group 的 sourceRefs 必须保留 member token ids 和 relation ids。
group children 必须使用 parent-relative layout。
```

禁止：

```text
不输出 search / button / card / carousel / navigation / tab / list。
不因为尺寸相似直接跨页面聚合 repeated_group。
不跨不同 parent scope 分组。
不使用文案、品牌、固定坐标、主题色、文件名。
不把 group 当 Auto Layout 结论。
```

验收：

```text
Body 直挂节点相比 VisualTree v0 下降。
Text 数量不下降。
Image 不吞 Text。
nodeTypes 仍然只包含 Body / Layer / Text / Image。
visual_tree_report.md 能看到 synthetic groupKind 和 relation 来源。
```

## Validation

开发期至少运行：

```bash
cd services/backend-go
go test ./...
go run ./cmd/m29extract --input /path/to/input.png --out /tmp/m29-go-smoke
go run ./cmd/m29batch --input-dir /path/to/images --out /tmp/m29-go-batch-smoke
go run ./cmd/m29tokens --input /tmp/m29-go-smoke/m29_physical_evidence.v1.json --out /tmp/m29-go-smoke
go run ./cmd/m29relations --input /tmp/m29-go-smoke/evidence_tokens.v1.json --out /tmp/m29-go-smoke
go run ./cmd/m29visualtree --tokens /tmp/m29-go-smoke/evidence_tokens.v1.json --relations /tmp/m29-go-smoke/relation_graph.v1.json --out /tmp/m29-go-smoke
```

最终静态检查：

```bash
git diff --check
git status --short --branch
```

## Acceptance Criteria

必须满足：

```text
Go M29.0 CLI 可独立运行。
输出 m29_physical_evidence.v1.json。
输出 debug overlay / masks / crops。
OCR 可选；有 OCR 时只参与 text mask 和物理测量。
`--ocr-provider baidu_ppocrv5` 可调用现有百度 PP-OCRv5 API 并产生 `text_region` / text mask。
没有 Python M29.0 nodes.json 兼容层。
没有旧 M29.6 / transparent / evidence / promotion / rerun 逻辑。
没有 DSL / Renderer / Figma / API 改动。
没有 CV heavy dependency。
```

失败判定：

```text
任何 UI 语义直接进入 M29.0 输出。
任何按样本文件名、文案、品牌、颜色、固定坐标、task id 的特化。
任何为了短期效果把 M29.0 变成 LayerAST/DSL 生成器。
任何恢复旧 promotion/rerun 思路。
```
