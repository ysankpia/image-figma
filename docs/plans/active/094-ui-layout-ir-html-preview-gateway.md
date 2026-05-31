# 094 UI Layout IR + HTML Preview Gateway

- 状态：active
- 创建日期：2026-05-31
- 分支：`feat/editable-draft-layer-pipeline`
- 负责人：Codex

## Goal

把当前直接 `PNG -> Draft DSL -> Figma` 的不可控链路，改成可调试、可验证、可逐层替换的 compiler 链路：

```text
PNG
-> evidence: OCR + M29 physical evidence + optional vision candidates
-> ui_layout_ir.v1.json
-> HTML preview / debug overlay / screenshot diff
-> Figma Auto Layout gateway
```

本计划的核心不是继续修 `Draft assembler`，也不是把旧 Python/M29 materializer 换名重跑。核心是新增一个中间合同和第一验收面：

```text
ui_layout_ir.v1.json 是结构合同。
HTML preview 是第一可视验收面。
Figma gateway 是最后的机械翻译层。
```

如果 HTML preview 不对，不允许进入 Figma 调试。Figma 不再承担识别、布局、ownership 修复职责。

## First Principles

真实产品目标仍然是：

```text
PNG -> editable Figma draft
```

但 PNG 没有原始 Figma 图层、Auto Layout、字体、mask、组件、z-index、被遮挡背景。直接把 PNG 编译成 Figma 节点，会把识别、布局、图层、资产、渲染和 Figma API 问题混在一起，导致每次坏图都只能继续补规则。

新的不可变边界：

```text
Evidence 层回答：看到了哪些物理/语义候选？
Layout compiler 回答：这些候选如何组成行、列、区域和 overlay？
HTML preview 回答：这个结构在普通浏览器里是否接近源图、是否可解释？
Figma gateway 回答：把已验证结构翻译成 Figma Auto Layout。
```

本计划不承诺一步达到 Codia 官方效果。它先解决工程可控性：中间 IR 可审计、HTML 可截图 diff、Figma gateway 可隔离验证。

## Scope

包含：

- 新增 `ui_layout_ir.v1` 合同和 Go 类型。
- 新增 layout compiler，从 OCR、M29 evidence、vision candidates 生成 layout IR。
- 新增 HTML preview renderer，把 layout IR 渲染为 `preview.html` 和 `preview_debug.html`。
- 新增 Playwright/browser 截图验证入口，输出 `preview_screenshot.png` 和 `source_vs_html_diff.png`。
- 新增 CLI `cmd/layoutcompile`，先不接插件。
- 复用当前 Go M29、OCR、vision provider、asset crop 能力。
- 用四张样图建立首轮真实 artifact 验收：Tencent 018、Tencent 022、荔枝 011、闲鱼。
- 更新文档，把 Draft graph 标记为旧 Draft runtime 尝试，不作为新结构合同。

不包含：

- 不恢复 Python `/api/upload-preview` 作为主线。
- 不恢复 Go Codia assembly/control/tree/emitter 作为 generation 路径。
- 不把官方 Codia JSON 用于 generation。
- 不直接在插件里修结构。
- 不在第一阶段接 Figma 插件。
- 不做 SAM、Grounded-SAM、Potrace、icon vector search、SVG 还原。
- 不做 Auto Layout componentization、Figma Component/Instance、variables。
- 不按样本名、文件名、品牌、文案、固定坐标、固定 bbox、固定屏幕尺寸特化。

## Target Architecture

第一版新增 Go 包：

```text
services/backend-go/
  cmd/
    layoutcompile/

  internal/
    layoutir/
      contract/
      validate/

    layoutcompile/
      evidence/
      segment/
      cluster/
      style/
      asset/
      report/

    htmlpreview/
      render/
      diff/
      report/
```

现有包定位：

```text
internal/m29      -> physical evidence provider
internal/vision   -> semantic candidate provider
internal/draft    -> legacy Draft DSL path, not the new structure authority
internal/eval     -> eval/reference only
renderer/plugin   -> Figma gateway only after HTML preview passes
```

推荐数据流：

```text
source PNG
-> M29 physical evidence
-> OCR text boxes
-> optional vision detector candidates
-> normalized evidence set
-> block segmentation
-> row/column clustering
-> overlay/z-order assignment
-> ui_layout_ir.v1.json
-> preview.html
-> preview_debug.html
-> preview_screenshot.png
-> source_vs_html_diff.png
```

## UI Layout IR Contract

第一版顶层：

```json
{
  "version": "ui_layout_ir.v1",
  "sourceImage": {
    "width": 665,
    "height": 1440,
    "sha256": "..."
  },
  "root": {
    "id": "node_0001",
    "type": "page",
    "bbox": {"x": 0, "y": 0, "width": 665, "height": 1440},
    "layout": {"mode": "column"},
    "children": []
  },
  "assets": [],
  "evidence": [],
  "decisions": [],
  "summary": {}
}
```

节点类型第一版只允许：

```text
page
section
row
column
group
overlay
text
image
shape
icon
unknown_crop
```

布局模式第一版只允许：

```text
absolute
row
column
overlay
```

每个节点必须有：

```text
id
type
bbox
layout
style
children
sourceRefs
confidence
fallbackPolicy
```

每个结构决策必须能追溯：

```text
emit
group
split
merge
suppress
fallback_crop
promote_text
promote_image
```

`ui_layout_ir.v1` 不是 Codia tree，不是 Draft layer graph，不是 Figma canvas JSON，也不是 HTML DOM。它是跨 HTML 和 Figma gateway 的结构 IR。

## Layout Compiler Rules

第一版不追复杂智能布局，只做可解释启发式：

1. **Normalize evidence**
   - OCR 负责文本 bbox 和内容。
   - M29 负责物理 primitive、surface、raster/image/shape evidence。
   - Vision 只提供 role/region hint，不直接生成最终树。

2. **Top-level segmentation**
   - 使用 XY-Cut 或等价 whitespace/coverage 切分大区块。
   - 先做垂直 section：header/banner/content/footer/bottom-like 只是 semanticTags，不是节点类型。
   - 切分依据是 bbox 分布、空白带、视觉覆盖，不是样本名或固定 y。

3. **Row/column clustering**
   - 同一 section 内按 y-overlap、top/baseline alignment、gap consistency 聚合 row。
   - row 内按 x 排序。
   - row 集合再组合为 column。
   - 若证据不足，保留 absolute group，不强造 row/column。

4. **Overlay assignment**
   - OCR text 默认在 image/shape 上层。
   - icon/image 可作为 foreground overlay。
   - 大复杂背景保留为 `unknown_crop` 或 `image` substrate，但必须局部，不允许 visible full-page backing。
   - 无法证明可拆的视觉内容用 crop fallback，不继续猜 shape/vector。

5. **Spacing inference**
   - 从 child bbox 推导 padding/gap。
   - 允许绝对布局 fallback。
   - 不为了 Auto Layout 强行改 bbox。

6. **Asset policy**
   - image/icon/unknown_crop 必须有本地 asset。
   - asset crop 来自 source PNG 或 M29/vision 支持 bbox。
   - 未解析 asset 是 hard validation error。

## HTML Preview

HTML preview 是第一验收面，必须生成两个版本：

```text
preview.html        正常视觉预览
preview_debug.html  显示 bbox、node id、layout mode、source refs
```

HTML renderer 只做机械渲染：

```text
layout IR -> HTML/CSS
```

它不允许：

```text
运行 OCR
调用 vision
改 bbox
改 ownership
按样本补规则
```

HTML preview 第一版使用普通 CSS：

```text
position:absolute for absolute/overlay fallback
display:flex; flex-direction:row/column for row/column
img for image/icon/unknown_crop
span/div for text
border/background for shape
```

Browser validation 输出：

```text
preview_screenshot.png
source_vs_html_diff.png
html_preview_report.md
```

## Figma Gateway

Figma gateway 在 HTML preview 稳定后进入第二阶段。它只消费 `ui_layout_ir.v1`：

```text
page/section/group -> figma frame/group
row                -> frame.layoutMode = HORIZONTAL
column             -> frame.layoutMode = VERTICAL
overlay/absolute   -> absolute positioned children
text               -> figma text node
image/icon/crop    -> image fill
shape              -> rect/ellipse/line where supported
```

Figma gateway 不允许：

```text
读取 M29/OCR/vision 原始 artifacts
读取 Codia golden
修复 layout compiler 的结构错误
隐藏 HTML preview 中已经暴露的 overlap/asset 问题
```

## Stage Plan

### Stage 0: Dirty Tree And Baseline Isolation

Actions:

- 查看当前未提交变更。
- 对 `services/backend-go/internal/draft/assemble/*` 当前临时 patch 做决定：要么单独提交为已验证小修，要么丢弃，不能混入 094。
- 确认 `.repomixignore`、`repomix.config.json` 是否属于本计划；如果只是分析残留，不纳入提交。

Validation:

```bash
git status --short --branch
git diff --check
```

Acceptance:

- 094 开始前工作树影响范围清楚。
- 不把旧 Draft 小 patch 包装成新架构进展。

### Stage 1: Contract And CLI Skeleton

Actions:

- 新增 `internal/layoutir/contract` 类型。
- 新增 `internal/layoutir/validate` 基础校验。
- 新增 `cmd/layoutcompile`，支持：
  ```text
  -input source.png
  -out output_dir
  -vision-candidates optional.json
  -vision-enabled false|true
  ```
- CLI 先能写空 page + source metadata + validation report。

Validation:

```bash
cd services/backend-go
go test ./internal/layoutir/... ./cmd/layoutcompile
```

Acceptance:

- `ui_layout_ir.v1.json` 能稳定生成。
- schema/contract 错误能被 validate 报出。
- 不依赖 Figma、Renderer、Plugin。

### Stage 2: Evidence Normalization

Actions:

- 接入现有 M29 physical evidence 和 OCR 输出。
- 可选接入 vision detector candidates。
- 输出 `layout_evidence.v1.json` 或嵌入 IR `evidence`。
- 每个 evidence item 统一 bbox、kind、roleHint、source、confidence。

Validation:

```bash
cd services/backend-go
go test ./internal/layoutcompile/evidence ./cmd/layoutcompile
```

Acceptance:

- Tencent 018 能生成 evidence summary。
- OCR text、M29 image/shape、vision candidate 不互相覆盖为同一种对象。
- Vision 失败不阻断 layout compile。

### Stage 3: Top-Level Section Segmentation

Actions:

- 实现基于 bbox 分布和空白带的 section segmentation。
- section 节点输出 `layout.mode=column|absolute`。
- 写 `layout_segmentation_report.md`。
- debug HTML 能显示 section bbox。

Validation:

```bash
cd services/backend-go
go test ./internal/layoutcompile/segment
```

Real sample:

```bash
cd services/backend-go
go run ./cmd/layoutcompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -out /tmp/layout-018-stage3
```

Acceptance:

- 018/022/荔枝/闲鱼都能产生 3-12 个 top-level sections。
- 不允许固定 y、固定设备尺寸、样本名。
- segmentation report 能解释 split/merge reason。

### Stage 4: Row/Column Clustering

Actions:

- 在 section 内做 alignment-aware row clustering。
- row 内 child 按 x 排序。
- 多 row section 推导 column。
- 证据不足时保留 absolute group。

Validation:

```bash
cd services/backend-go
go test ./internal/layoutcompile/cluster
```

Acceptance:

- 常见横向 tab、列表 row、按钮文字图标组合能形成 row。
- 纵向内容流能形成 column。
- 不为追 Auto Layout 强行破坏 bbox。
- 每个 row/column 有 source children 和 reason。

### Stage 5: HTML Preview Renderer

Actions:

- 新增 `internal/htmlpreview/render`。
- 输出 `preview.html` 和 `preview_debug.html`。
- 支持 text/image/shape/unknown_crop/row/column/absolute。
- asset crop 写入 output assets 目录。

Validation:

```bash
cd services/backend-go
go test ./internal/htmlpreview/...
go run ./cmd/layoutcompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -out /tmp/layout-018-stage5
```

Acceptance:

- 浏览器打开 `preview.html` 能看到接近源图的结构草稿。
- `preview_debug.html` 能显示 bbox 和 layout mode。
- HTML renderer 不读取 M29/OCR/vision 原始 artifact，只读 layout IR。

### Stage 6: Browser Screenshot Diff Gate

Actions:

- 增加 Playwright 或 repo 现有浏览器验证入口。
- 打开 `preview.html`，截图为 `preview_screenshot.png`。
- 与 source PNG 生成 `source_vs_html_diff.png` 和 markdown report。
- 先记录指标，不设硬阈值阻断。

Validation:

```bash
pnpm --filter @image-figma/image-to-figma-renderer run test
cd services/backend-go
go test ./internal/htmlpreview/...
```

Acceptance:

- 本地命令能为 018 产出 screenshot/diff/report。
- report 至少包含尺寸、mean diff、large white hole 检测、asset missing、text count、node count。
- 失败时能定位是 IR、asset、HTML renderer 还是 browser 环境问题。

### Stage 7: Four-Sample HTML Validation

Actions:

- 新增脚本 `services/backend-go/tools/layout_smoke_4img.sh`。
- 跑四张样图：
  ```text
  docs/reference/codia-samples/images/腾讯动漫_018_1440.png
  docs/reference/codia-samples/images/腾讯动漫_022_1440.png
  docs/reference/codia-samples/images/荔枝_011_1440.png
  docs/reference/codia-samples/images/闲鱼.png
  ```
- 输出统一 summary。

Validation:

```bash
cd services/backend-go
bash tools/layout_smoke_4img.sh
```

Acceptance:

- 四图都能输出 `ui_layout_ir.v1.json`、`preview.html`、`preview_debug.html`、report。
- asset missing = 0。
- CLI 不 panic。
- 单图失败必须归因到 evidence、segmentation、cluster、asset、html renderer 中某一层。

### Stage 8A: Visible Leaf Materialization

Actions:

- 在 `segment/cluster` 后新增 visible leaf materialization。
- `preview.html` 只渲染 materialized leaf nodes，不再直接渲染 raw evidence。
- `preview_debug.html` 继续渲染 evidence、node bbox、node id、layout mode。
- OCR/text evidence 提升为 `text` leaf。
- compact image/icon evidence 提升为 `image/icon` leaf 并声明 asset。
- 大块含文本 raster 不作为 foreground `image`；稀疏不可拆区域可降级为底层 `unknown_crop` substrate，富内部证据区域必须 suppress，由内部 text/icon/shape/image leaf 承担可编辑层。
- 位于 substrate 内的 OCR text 额外生成 text eraser shape，放在 crop 上、text 下，减少原图文字和可编辑文字重影。
- page/root 和 shape/text leaf 使用从 source PNG 采样出的 fill；renderer 只消费 IR fill，不自行推断。
- 微型 shape/icon 碎片 suppress，防止 normal preview 被物理噪点淹没。

Validation:

```bash
cd services/backend-go
go test ./internal/htmlpreview/... ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile ./cmd/previewdiff
bash tools/layout_smoke_4img.sh
```

Acceptance:

- `preview.html` 中 `data-evidence-id` 数量为 0。
- `preview_debug.html` 保留 evidence debug overlay。
- 四图 validation errorCount = 0，asset missing = 0。
- 018 browser diff 相比 Stage 6 evidence preview 不退化，并记录 artifact。

### Stage 8B: Figma Gateway Plan And Minimal Prototype

Actions:

- 在 HTML leaf gate 稳定后，再新增 Figma gateway 计划或子阶段。
- 第一版可只做 CLI/renderer proof，不接插件 UI。
- `ui_layout_ir.v1` 到 Figma 的映射必须机械，不读 source evidence。

Validation:

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

Acceptance:

- row/column 能映射 Auto Layout。
- absolute/overlay fallback 可保留精确 bbox。
- Figma output 问题能和 HTML output 问题分离。

## Validation Matrix

每阶段最小必跑：

```bash
git diff --check
cd services/backend-go && go test ./internal/layoutir/... ./internal/layoutcompile/... ./internal/htmlpreview/... ./cmd/layoutcompile
```

涉及 renderer/plugin 时再跑：

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

真实样图验收：

```bash
cd services/backend-go
bash tools/layout_smoke_4img.sh
```

## Acceptance

本计划第一轮完成的最低标准：

- `ui_layout_ir.v1.json` 成为新的结构合同。
- `preview.html` 和 `preview_debug.html` 成为第一调试面。
- `cmd/layoutcompile` 可对 018/022/荔枝/闲鱼生成 artifacts。
- HTML preview 可以本地打开，不依赖 Figma。
- 每个节点和每个结构决策都能追溯 source refs 和 reason。
- asset missing = 0。
- 没有样本名、品牌、文案、固定 bbox、固定坐标、固定屏幕尺寸特化。
- Figma gateway 不在 HTML preview 稳定前承载结构修复。

## Risk And Counterarguments

最大风险：

```text
HTML preview 看起来更像，但仍然只是 crop overlay 旧路重演。
```

防线：

- 第一阶段的目标是验证 layout IR 和调试面，不承诺 Codia parity。
- HTML preview 必须输出 layout tree、decision report 和 debug overlay，而不是只输出图片拼贴。
- 如果 IR 退化成大量 absolute crop，report 必须显式标红：
  ```text
  auto_layout_coverage_low
  absolute_fallback_ratio_high
  crop_fallback_ratio_high
  ```

第二风险：

```text
XY-Cut/row clustering 又变成手写视觉模型。
```

防线：

- layout compiler 只处理 bbox 结构关系，不判断复杂 UI 语义。
- 语义来自 vision/M29/OCR evidence。
- 不为单图修阈值；任何阈值必须用四图 smoke 复核。

第三风险：

```text
Figma gateway 提前接入后又把调试面拖回 Figma。
```

防线：

- Figma gateway 明确排在 HTML gate 后。
- HTML 不通过，不修 Figma。

## Learning Backflow

本计划吸收的历史教训：

- Python M29 direct replay 和 plan-driven materializer 已证明 flat replay/crop overlay 不是终点。
- Go Codia-like compiler 已证明直接追 Codia tree 会把 role detection、ownership、tree 和 output format 混成一团。
- 当前 Go Draft 已证明没有中间可视验收面时，Figma 输出变差后难以定位责任层。

因此本计划的核心产物不是又一个 Draft renderer，而是：

```text
可审计 layout IR
可截图对比 HTML preview
可隔离 Figma gateway
```

## Notes

- `093 Editable Draft Layer Pipeline Rebuild` 仍记录当前 Draft branch 的历史重构过程；094 是新的执行方向。
- 如果 094 Stage 1-7 证明 HTML preview 也只能退化成 absolute crop 拼贴，应停止本路线，转向训练/接入能输出 mask/ownership 的 `ui_layer_candidates` 模型合同。
- 本计划允许破坏性重构，但每个阶段都必须可运行、可验证、可回滚。

## Stage 1 Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutir/contract
  services/backend-go/internal/layoutir/validate
  services/backend-go/internal/layoutcompile
  services/backend-go/cmd/layoutcompile
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile
  rm -rf /tmp/layout-018-stage1
  cd services/backend-go && go run ./cmd/layoutcompile \
    -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
    -out /tmp/layout-018-stage1
  git diff --check
  ```
- 真实样图输出：
  ```text
  /tmp/layout-018-stage1/ui_layout_ir.v1.json
  /tmp/layout-018-stage1/ui_layout_ir_validation.v1.json
  /tmp/layout-018-stage1/layout_compile_report.md
  ```
- 018 Stage 1 artifact summary：
  ```text
  version: ui_layout_ir.v1
  source size: 665x1440
  root: node_0001 page bbox 0,0,665,1440 layout column
  nodes: 1
  assets: 0
  evidence: 0
  decisions: 1
  validation errors: 0
  validation warnings: 0
  ```
- 说明：Stage 1 只建立空 page 合同、校验和 CLI；evidence normalization、segmentation、clustering、HTML preview、Figma gateway 仍未激活。

## Stage 2 Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutcompile/evidence
  services/backend-go/internal/layoutcompile
  services/backend-go/internal/layoutir/validate
  services/backend-go/cmd/layoutcompile
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile
  rm -rf /tmp/layout-018-stage2
  cd services/backend-go && go run ./cmd/layoutcompile \
    -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
    -out /tmp/layout-018-stage2
  git diff --check
  ```
- 真实样图输出：
  ```text
  /tmp/layout-018-stage2/ui_layout_ir.v1.json
  /tmp/layout-018-stage2/ui_layout_ir_validation.v1.json
  /tmp/layout-018-stage2/layout_compile_report.md
  /tmp/layout-018-stage2/m29/m29_physical_evidence.v1.json
  /tmp/layout-018-stage2/tokens/evidence_tokens.v1.json
  ```
- 018 Stage 2 artifact summary：
  ```text
  version: ui_layout_ir.v1
  source size: 665x1440
  nodes: 1
  evidence: 203
  decisions: 1
  validation errors: 0
  validation warnings: 0
  evidence kind counts:
    m29_token: 203
  role hint counts:
    icon: 70
    shape: 53
    text: 47
    line: 13
    image: 10
    unknown: 9
    texture_fragment: 1
  ```
- 说明：Stage 2 只做 evidence normalization；layout tree 仍只有 page root。M29/OCR/vision 原始证据不会直接变成 Figma 或 HTML 节点，后续 Stage 3/4 才消费这些 normalized evidence 做 section 和 row/column。

## Stage 3 Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutcompile/segment
  services/backend-go/internal/layoutcompile
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile
  rm -rf /tmp/layout-018-stage3
  cd services/backend-go && go run ./cmd/layoutcompile \
    -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
    -out /tmp/layout-018-stage3
  git diff --check
  ```
- 真实样图输出：
  ```text
  /tmp/layout-018-stage3/ui_layout_ir.v1.json
  /tmp/layout-018-stage3/ui_layout_ir_validation.v1.json
  /tmp/layout-018-stage3/layout_compile_report.md
  ```
- 018 Stage 3 artifact summary：
  ```text
  version: ui_layout_ir.v1
  source size: 665x1440
  nodes: 5
  root children: 4 sections
  evidence: 203
  decisions: 5
  validation errors: 0
  validation warnings: 0
  sections:
    section_0001 bbox 27,14,611,817 evidence 141
    section_0002 bbox 55,695,495,107 evidence 8
    section_0003 bbox 41,860,577,198 evidence 15
    section_0004 bbox 0,1087,665,353 evidence 34
  ```
- 修正说明：第一版 section split 被大块 image/shape substrate bbox 吞掉纵向 gap，只得到 1 个 section。Stage 3 改为先用 text/icon/line anchor evidence 找 top-level vertical gaps，再把重叠的大块 image/shape/unknown evidence 吸收到对应 section bbox。这是通用责任分离：anchor evidence 负责切分，substrate/background evidence 负责 section 覆盖扩展。

## Stage 4 Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutcompile/cluster
  services/backend-go/internal/layoutcompile
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile
  rm -rf /tmp/layout-018-stage4
  cd services/backend-go && go run ./cmd/layoutcompile \
    -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
    -out /tmp/layout-018-stage4
  git diff --check
  ```
- 真实样图输出：
  ```text
  /tmp/layout-018-stage4/ui_layout_ir.v1.json
  /tmp/layout-018-stage4/ui_layout_ir_validation.v1.json
  /tmp/layout-018-stage4/layout_compile_report.md
  ```
- 018 Stage 4 artifact summary：
  ```text
  version: ui_layout_ir.v1
  source size: 665x1440
  nodes: 38
  root children: 4 sections
  rows: 33
  evidence: 203
  decisions: 38
  validation errors: 0
  validation warnings: 0
  rows outside parent section: 0
  section row counts:
    section_0001: 20
    section_0002: 2
    section_0003: 5
    section_0004: 6
  ```
- 修正说明：第一版 row expansion 会把跨 section 的大块 image/shape substrate 吸收到局部 row，导致 row bbox 逃出父 section。Stage 4 加入通用 section containment gate：substrate 必须中心落在 section 内，或自身至少 50% 面积落在 section 内；row 扩展后的 union 也必须完全留在父 section bounds 内。这不是样本特化，而是 layout IR 的父子 bbox 合同。

## Stage 5 Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/htmlpreview/render
  services/backend-go/internal/layoutcompile
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/htmlpreview/... ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile
  rm -rf /tmp/layout-018-stage5
  cd services/backend-go && go run ./cmd/layoutcompile \
    -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
    -out /tmp/layout-018-stage5
  git diff --check
  ```
- 真实样图输出：
  ```text
  /tmp/layout-018-stage5/ui_layout_ir.v1.json
  /tmp/layout-018-stage5/ui_layout_ir_validation.v1.json
  /tmp/layout-018-stage5/layout_compile_report.md
  /tmp/layout-018-stage5/preview.html
  /tmp/layout-018-stage5/preview_debug.html
  /tmp/layout-018-stage5/html_preview_report.md
  /tmp/layout-018-stage5/preview_assets/
  ```
- 018 Stage 5 artifact summary：
  ```text
  version: ui_layout_ir.v1
  source size: 665x1440
  nodes: 38
  root children: 4 sections
  rows: 33
  evidence: 203
  decisions: 38
  validation errors: 0
  validation warnings: 0
  html preview warnings: 0
  preview assets: 90
  preview.html size: 64464 bytes
  debug preview: generated
  text evidence z-index: 40
  image evidence z-index: 20
  ```
- 修正说明：Stage 5 新增 HTML preview 作为第一可视验收面。Renderer 只消费 `ui_layout_ir.v1`，不读取 M29/OCR/vision 原始 artifacts；source PNG 仅用于按 IR bbox 写本地 preview crop asset。文本 evidence 固定绘制在 image/shape evidence 上方，避免“文字被底图压住”的基础层级错误。当前 Stage 5 仍未做 child materialization 和 Figma gateway，因此 HTML 是结构草稿和调试面，不是最终设计稿。

## Stage 6 Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/htmlpreview/render
  services/backend-go/internal/htmlpreview/diff
  services/backend-go/cmd/previewdiff
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/htmlpreview/... ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile ./cmd/previewdiff
  rm -rf /tmp/layout-018-stage6
  cd services/backend-go && go run ./cmd/layoutcompile \
    -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
    -out /tmp/layout-018-stage6
  ```
- Chrome DevTools MCP 验证：
  ```text
  navigate: file:///tmp/layout-018-stage6/preview.html?capture=1
  evaluate:
    pageRect: 665x1440
    evidenceCount: 193
    nodeCount: 37
    assetImages: 80
    textZ: 40
    imageZ: 20
  screenshot:
    /tmp/layout-018-stage6/preview_screenshot.png
  ```
- Diff 命令：
  ```bash
  cd services/backend-go && go run ./cmd/previewdiff \
    -source ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
    -screenshot /tmp/layout-018-stage6/preview_screenshot.png \
    -preview-html /tmp/layout-018-stage6/preview.html \
    -out /tmp/layout-018-stage6
  git diff --check
  ```
- 真实样图输出：
  ```text
  /tmp/layout-018-stage6/preview_screenshot.png
  /tmp/layout-018-stage6/preview_screenshot_normalized.png
  /tmp/layout-018-stage6/source_vs_html_diff.png
  /tmp/layout-018-stage6/html_preview_diff_report.md
  ```
- 018 Stage 6 artifact summary：
  ```text
  source size: 665x1440
  DevTools screenshot size: 2370x2880
  normalized screenshot size: 665x1440
  inferred screenshot scale: 2.00
  mean channel diff: 66.91
  max channel diff: 247
  white hole pixels: 0
  white hole ratio: 0.0000
  large white hole: false
  referenced assets: 80
  missing assets: 0
  ```
- 修正说明：浏览器截图由 Chrome DevTools MCP 负责，Go 后端不再启动或管理 Chrome。`preview.html?capture=1` 只提供截图友好的零边距模式；`cmd/previewdiff` 是纯离线 PNG diff/report 工具，会把 Retina/高 DPR 截图按源图高度归一化到源图尺寸后再比较。Stage 6 只记录指标，不把 mean diff 设为硬阻断，因为当前 HTML 仍是 evidence/row 调试草稿。

## Stage 7 Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/tools/layout_smoke_4img.sh
  ```
- 已执行：
  ```bash
  bash services/backend-go/tools/layout_smoke_4img.sh
  git diff --check
  ```
- 真实样图输出根目录：
  ```text
  /tmp/layout_smoke_4img/
  ```
- 每张样图都检查：
  ```text
  ui_layout_ir.v1.json exists
  ui_layout_ir_validation.v1.json exists
  layout_compile_report.md exists
  preview.html exists
  preview_debug.html exists
  html_preview_report.md exists
  validation errorCount == 0
  preview.html referenced local assets exist
  ```
- 四图 summary：
  ```text
  | case | nodes | sections | rows | evidence | html assets | warnings |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: |
  | t018 | 38 | 4 | 33 | 203 | 80 | 0 |
  | t022 | 37 | 6 | 30 | 121 | 33 | 0 |
  | lizhi | 32 | 8 | 23 | 76 | 31 | 0 |
  | xianyu | 35 | 4 | 30 | 143 | 40 | 0 |
  ```
- 修正说明：Stage 7 建立四图批量 HTML gate。它不评价 Figma，也不把视觉相似度作为硬阻断；它只证明 `layoutcompile -> ui_layout_ir.v1 -> preview.html/preview_debug.html -> asset references` 可以对四张真实样图稳定复跑，并且失败时能归因到 validation、artifact 缺失或 asset 引用缺失。

## Stage 8A Validation Evidence

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutcompile/materialize/
  services/backend-go/internal/layoutcompile/compile.go
  services/backend-go/internal/htmlpreview/render/
  docs/plans/active/094-ui-layout-ir-html-preview-gateway.md
  ```
- 已执行：
  ```bash
  git diff --check
  cd services/backend-go && go test ./internal/htmlpreview/... ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile ./cmd/previewdiff
  cd services/backend-go && bash tools/layout_smoke_4img.sh
  cd services/backend-go && go run ./cmd/layoutcompile -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png -out /tmp/layout-018-stage8a
  cd services/backend-go && go run ./cmd/previewdiff -source ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png -screenshot /tmp/layout-018-stage8a/preview_screenshot.png -preview-html /tmp/layout-018-stage8a/preview.html -out /tmp/layout-018-stage8a
  ```
- Chrome DevTools MCP artifact：
  ```text
  /tmp/layout-018-stage8a/preview_screenshot.png
  ```
- 018 artifact summary：
  ```text
  nodes: 230
  assets: 80
  evidence: 203
  decisions: 275
  validation errors: 0
  preview evidence tags: 0
  debug evidence tags: 203
  preview img refs: 80
  missing assets: 0
  browser mean channel diff: 10.48
  white hole ratio: 0.0004
  large white hole: false
  ```
- 018 visible leaf counts：
  ```text
  text: 47
  image: 7
  icon: 70
  shape: 65
  unknown_crop: 3
  ```
- 018 materialization decisions：
  ```text
  materialize_text_evidence: 47
  materialize_image_crop: 7
  materialize_compact_icon: 70
  materialize_shape_evidence: 31
  materialize_text_bearing_raster_as_substrate: 2
  materialize_structural_band_raster_as_substrate: 1
  materialize_text_eraser_for_substrate: 34
  materialize_micro_fragment_suppressed: 31
  materialize_micro_shape_suppressed: 4
  materialize_unresolved_non_structural_evidence: 10
  ```
- 四图 summary：
  ```text
  | case | nodes | sections | rows | evidence | html assets | warnings |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: |
  | t018 | 230 | 4 | 34 | 203 | 80 | 0 |
  | t022 | 148 | 10 | 30 | 121 | 33 | 0 |
  | lizhi | 103 | 8 | 23 | 76 | 31 | 0 |
  | xianyu | 192 | 4 | 30 | 143 | 40 | 0 |
  ```
- 修正说明：Stage 8A 把 normal HTML preview 从 raw evidence debug view 改成 visible leaf view。raw evidence 只在 `preview_debug.html` 出现。大块含文本 raster 被降级为底层 `unknown_crop` substrate，OCR 文本保持可编辑并绘制在上层，必要时插入 text eraser 降低原图文字重影。当前仍不是 Figma gateway，也不是 Codia clone；剩余主要缺口是 text eraser 的视觉粗糙度、字体样式恢复和 row/column 语义布局覆盖率。

## Stage 8A Follow-up: Decomposable Raster Suppression

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutcompile/materialize/
  docs/plans/active/094-ui-layout-ir-html-preview-gateway.md
  ```
- 根因：
  ```text
  Stage 8A 把“大块含文本 raster”统一降级为 visible unknown_crop substrate。
  这保住了像素相似度，但对已经有足够内部 text/icon/shape/image evidence 的区域，会重新生成一个覆盖式大图层。
  结果是 normal preview 看起来接近，但 Figma/editable 目标上仍然留下不可编辑大块。
  ```
- 通用规则：
  ```text
  non-compact raster candidate
  + 覆盖面积达到结构区块量级
  + 内部存在足够多、足够分散、至少三类的 editable evidence
  -> suppress as decomposable raster evidence
  ```
- 反向保护：
  ```text
  compact media/image card/avatar/cover 继续可 emit 为 image。
  sparse large raster 继续可作为 fallback unknown_crop substrate。
  判断不读取样本名、文件名、leaf id、token id、固定 bbox、固定坐标、品牌或文案。
  ```
- 单测覆盖：
  ```text
  TestBuildSuppressesDecomposableLargeRaster
  TestBuildKeepsSparseLargeRasterAsSubstrate
  TestBuildKeepsCompactMediaEvenWithInternalHints
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/layoutcompile/materialize ./internal/layoutcompile ./internal/htmlpreview/render ./cmd/layoutcompile
  cd services/backend-go && go run ./cmd/layoutcompile -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png -out /tmp/layout-018-decomposable
  cd services/backend-go && bash tools/layout_smoke_4img.sh
  ```
- Chrome DevTools MCP artifact：
  ```text
  /tmp/layout-018-decomposable/preview_screenshot.png
  /tmp/layout-018-decomposable/preview_debug_screenshot.png
  /tmp/layout-018-decomposable/preview_screenshot_normalized.png
  /tmp/layout-018-decomposable/source_vs_html_diff.png
  /tmp/layout-018-decomposable/source_html_diff_sheet_normalized.png
  ```
- 018 artifact summary：
  ```text
  nodes: 194
  assets: 78
  evidence: 203
  decisions: 241
  validation errors: 0
  unknown_crop: 1
  missing assets: 0
  browser mean channel diff: 27.08
  white hole ratio: 0.0000
  large white hole: false
  ```
- 大块 crop 验证：
  ```text
  evidence_token_0085 -> decision_materialize_0085 suppress materialize_decomposable_raster_suppressed
  evidence_token_0077 -> decision_materialize_0077 suppress materialize_decomposable_raster_suppressed
  asset_leaf_0040.png still exists only because leaf ids are sequence numbers; current asset_leaf_0040 is 17x40 icon, not the old 665x346 region.
  Judge by sourceRefs/reason/bbox/asset dimensions, not by filename.
  ```
- 四图 summary：
  ```text
  | case | nodes | sections | rows | evidence | html assets | warnings |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: |
  | t018 | 194 | 4 | 34 | 203 | 78 | 0 |
  | t022 | 124 | 10 | 30 | 121 | 31 | 0 |
  | lizhi | 98 | 8 | 23 | 76 | 30 | 0 |
  | xianyu | 157 | 4 | 30 | 143 | 38 | 0 |
  ```
- 取舍说明：
  ```text
  mean diff 从 Stage 8A 的 10.48 上升到 27.08 是预期取舍：移除覆盖式大 crop 后，像素相似度下降，但可编辑性提高。
  这不是最终视觉质量完成。剩余主要缺口是 shape/style 重建、局部背景补洞、字体样式和布局细节，不应再用整块 crop 兜回去。
  ```

## Stage 8C: Row Layout Contract And Structural Health Gate

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutcompile/cluster/
  services/backend-go/internal/htmlpreview/render/
  services/backend-go/tools/layout_smoke_4img.sh
  docs/plans/active/094-ui-layout-ir-html-preview-gateway.md
  ```
- 第一性原理结论：
  ```text
  HTML preview 不能只优化 source PNG pixel diff。
  source[bbox] -> crop -> paste at original bbox 是恒等变换，像素上容易变好，但不能证明 Figma Auto Layout 可编辑性。
  HTML preview 的主职责必须改成结构验收：row/column/gap/padding/align 是否能被机械翻译。
  ```
- 已证实的问题：
  ```text
  contract.Layout 已有 row/column/gap/padding/align 字段。
  cluster/rows.go 过去只把 evidence 聚成 row bbox，row.Layout.Mode 仍是 absolute。
  htmlpreview/render 过去 flatten 全树后绝对定位输出，layout.mode 只出现在 debug label。
  report 过去没有 auto_layout_coverage、absolute_fallback_ratio、gap variance、text eraser count。
  ```
- 修复：
  ```text
  cluster row 输出 LayoutRow，并推导 gap/padding/align。
  row gap 基于 text/icon 前景 anchor 推导；shape/background 不参与主轴 gap，避免把背景当 flex item。
  HTML renderer 改为 tree-aware render：row 节点输出 display:flex；text/icon/image 作为 flow item；shape/unknown/text_eraser 继续作为 absolute overlay/fallback。
  HTML report 新增 Structural Health。
  四图 smoke 输出 auto layout coverage、absolute fallback ratio、mean gap variance。
  ```
- 当前 Structural Health 不是通过门，而是暴露门：
  ```text
  coverage 高不等于结构完成；gap variance 高说明 row 聚类仍粗糙。
  pixel diff 仍记录，但不作为进入 Figma gateway 的主验收。
  ```
- 已执行：
  ```bash
  git diff --check
  cd services/backend-go && go test ./internal/htmlpreview/... ./internal/layoutir/... ./internal/layoutcompile/... ./cmd/layoutcompile ./cmd/previewdiff
  cd services/backend-go && bash tools/layout_smoke_4img.sh
  cd services/backend-go && go run ./cmd/layoutcompile -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png -out /tmp/layout-018-flex-health
  ```
- Chrome DevTools MCP artifact：
  ```text
  /tmp/layout-018-flex-health/preview_screenshot.png
  /tmp/layout-018-flex-health/preview_screenshot_normalized.png
  /tmp/layout-018-flex-health/source_vs_html_diff.png
  /tmp/layout-018-flex-health/source_html_flex_diff_sheet.png
  ```
- 018 artifact summary：
  ```text
  row layout nodes: 33
  row modes: row
  preview layout-row html count: 35
  preview flow-node count: 125
  missing assets: 0
  browser mean channel diff: 35.03
  auto layout coverage: 0.7949
  absolute fallback ratio: 0.2051
  single-child row count: 11
  mean gap variance: 946.79
  text eraser nodes: 0
  ```
- 四图 summary：
  ```text
  | case | nodes | sections | rows | evidence | html assets | auto layout coverage | absolute fallback | mean gap variance | warnings |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
  | t018 | 194 | 4 | 34 | 203 | 78 | 0.7949 | 0.2051 | 946.79 | 0 |
  | t022 | 124 | 10 | 30 | 121 | 31 | 0.8046 | 0.1954 | 3613.20 | 0 |
  | lizhi | 98 | 8 | 23 | 76 | 30 | 0.8636 | 0.1364 | 1015.48 | 0 |
  | xianyu | 157 | 4 | 30 | 143 | 38 | 0.6311 | 0.3689 | 498.60 | 0 |
  ```
- 取舍说明：
  ```text
  mean diff 从 27.08 上升到 35.03 是预期代价：row flex 渲染开始暴露聚类和 gap 推导问题。
  这次修复不是让 HTML 更像源图，而是让 HTML 不再掩盖结构错误。
  下一步应修 cluster：降低单子 row、分离背景 overlay 与前景 flow、按局部行/卡片层级重新聚类，而不是退回 flat absolute/crop overlay。
  ```

## Stage 8D: Row Ownership Diagnostics And Empty Row Repair

- 日期：2026-05-31
- 状态：passed
- 改动范围：
  ```text
  services/backend-go/internal/layoutcompile/cluster/
  services/backend-go/internal/htmlpreview/render/
  services/backend-go/tools/layout_smoke_4img.sh
  docs/plans/active/094-ui-layout-ir-html-preview-gateway.md
  ```
- 第一性原理结论：
  ```text
  row 聚类的源真相必须来自 section 的 sourceRefs。
  如果 cluster 在每个 section 内重新按 bbox 从全量 evidence 捞成员，重叠 section 会重复拥有同一 evidence。
  materialize 之后 leaf 只能落到一个最佳容器，重复 row 就会变成 zero-flow 空 flex row。
  这不是 renderer 问题，也不是 pixel diff 问题，是 section ownership 在 cluster 阶段被绕过。
  ```
- 修复：
  ```text
  cluster.BuildRows 优先使用 section.SourceRefs 中声明的 layout_evidence 作为 section 成员。
  只有旧节点没有可匹配 sourceRefs 时，才回退到 bbox containment。
  row anchors 不再使用 line evidence；明显小于同组字号尺度的 icon fragment 不再作为 row anchor。
  sparse row merge 增加垂直重叠条件，避免把上下两个孤立元素合成假横向 row。
  row overlay 吸附增加局部尺寸限制，避免大背景/整块区域把 row bbox 撑爆。
  ```
- HTML report 增强：
  ```text
  新增 absolute row fallback nodes。
  新增 zero-flow row count。
  新增 high-gap row count。
  新增 Top Bad Rows 表，输出 row id、reason、bbox、children、flow、overlay、gap、gap variance。
  ```
- smoke 增强：
  ```text
  tools/layout_smoke_4img.sh 输出 zero-flow rows 和 high-gap rows。
  warnings=0 不再被当作结构健康的充分信号。
  ```
- 已执行：
  ```bash
  cd services/backend-go && go test ./internal/layoutcompile/cluster ./internal/htmlpreview/render
  cd services/backend-go && bash tools/layout_smoke_4img.sh
  ```
- 四图 summary：
  ```text
  | case | nodes | sections | rows | evidence | html assets | auto layout coverage | absolute fallback | zero-flow rows | high-gap rows | mean gap variance | warnings |
  | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
  | t018 | 188 | 4 | 40 | 203 | 78 | 0.7308 | 0.2692 | 0 | 1 | 221.44 | 0 |
  | t022 | 116 | 10 | 33 | 121 | 31 | 0.6782 | 0.3218 | 0 | 2 | 3838.68 | 0 |
  | lizhi | 94 | 8 | 20 | 76 | 30 | 0.8636 | 0.1364 | 0 | 2 | 1229.26 | 0 |
  | xianyu | 147 | 4 | 28 | 143 | 38 | 0.5902 | 0.4098 | 0 | 3 | 602.10 | 0 |
  ```
- 取舍说明：
  ```text
  zero-flow row 已归零，这是本阶段修复的硬信号。
  auto layout coverage 在 t018/t022/xianyu 低于 Stage 8C，因为重复/重叠 section 的空结构不再被错误计入可用 row。
  high-gap rows 仍存在，尤其 t022 和 xianyu；这说明下一步仍应修 region/card-aware 局部 grouping，而不是在 renderer 里隐藏或恢复 crop overlay。
  ```
