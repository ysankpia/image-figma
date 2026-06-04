# Codia/Figma JSON 编译器逆向规格审计与可实施方案

> Reference-only Codia reverse-engineering audit. It is not the current product specification on this branch. Current product work targets Pencil assisted slice workspace: candidates -> `manual_slices.v1.json` -> `project.zip` + `selected-assets.zip`. This document may inform eval/reference work only.

**审计对象**

- `腾讯动漫_018_1440(1).json`：Figma/canvas JSON，作为本次审计的一手事实源。
- `/Users/luhui/Downloads/figma/json/腾讯动漫_018_1440.json`：018 raw Codia/Figma canvas JSON。
- `/Users/luhui/Downloads/figma/json/腾讯动漫主要.canvas.json`：022 raw Codia/Figma canvas JSON。
- `docs/reference/codia-samples/images/*.png`、OCR JSON、M29 physical evidence / evidence tokens：截图到 IR 的实现验证样本。

**审计目标**

这份文档不是简单总结，而是给后续工程实现使用的“可落地规格审计”。目标是回答四个问题：

1. raw Codia canvas JSON 实际证明了什么，哪些只是单样本现象。
2. 018 与 022 在节点数、root children、角色分布、StatusBar/EditText、cornerRadius 等方面有哪些真实差异。
3. 真正可实现的 Codia-like 编译器应该采用什么数据契约、算法路径和验收标准。
4. 工程团队拿到本文后，如何避免做出“视觉相似但结构错误”的实现。

---

## 0. 总结结论

### 0.1 最终判断

可以做，但前提是把目标定义为 **从截图重建 Codia-like 的 Figma 结构树**，而不是“把截图切成图层”或“用 XY-cut 递归分组”。核心路径必须是：

```text
截图/检测证据
→ 文字、图片、背景等 source primitive
→ UI 角色识别 IR
→ 允许重叠的区域/控件/列表树
→ Figma 节点发射
→ 结构 + 视觉双验收
```

如果工程实现仍以纯几何分割、纯 child-union bbox、或“按空白切块”为主干，那么无论渲染多接近，都不会匹配 Codia 的输出结构。

### 0.2 证据使用方式

| 证据 | 优先级 | 使用建议 |
|---|---:|---|
| raw Codia/Figma canvas JSON | 最高 | 作为结构、role、bbox、children order、schema suffix、visible name/type 的唯一 golden truth。 |
| sample PNG + OCR + M29 artifacts | 高 | 用于验证从截图到 Codia IR 的实现链路，不能覆盖 raw canvas 的结构事实。 |
| 推断和工程策略 | 中 | 只能作为可测试假设，必须回到 raw canvas / PNG artifact 验证。 |
| reference prose / historical reverse-spec notes | 低 | 不作为实现合同，不作为阅读前置，不允许覆盖 raw canvas 事实。 |

018 与 022 的固定数量、root child count、控件数量和层级深度只能作为各自 golden baseline，不能写成全局规则。

### 0.3 最危险的错误抽象

必须删除或降级这些实现方向：

1. **“Codia = XY-cut”**：错误。Codia 树允许 root/region 级重叠，很多背景与前景是兄弟关系，不是几何分割树。
2. **“Visible name 足够表达语义”**：错误。`Groups` 可能是 `ViewGroup`、`ListView`、`ActionBar`、`StatusBar`、`BottomNavigation`，真正角色在 `schema:id`。
3. **“容器 bbox = children union + 固定 padding”**：错误。容器 bbox 往往来自检测/区域证据，children 可以 overflow。
4. **“Background 是 parent/wrapper”**：错误。Background 通常是 sibling leaf，并且在 children 数组中靠后。
5. **“能复刻 canvas JSON 就直接手写 JSON”**：高风险。`derivedTextData`、`fillGeometry`、`strokeGeometry`、`commandsBlob`、image hash/blob、guid 等都强烈依赖 Figma 内部序列化。工程上应优先通过 Figma Plugin API/节点 API 发射节点，再导出 JSON 做验收。

### 0.4 可以直接进入实现的核心规格

实现必须保留一个内部 IR，至少包含：

- `role`：`root | ViewGroup | ListView | ActionBar | StatusBar | BottomNavigation | Button | EditText | TextView | ImageView | Background | bg_Button | bg_EditText`
- `source_bbox`：检测/OCR/裁剪证据坐标。
- `figma_bbox`：最终发射到 Figma 的 bbox。
- `evidence`：为什么这个节点存在，来自 chrome-role、control-role、collection/list、source background、repeated cell、residual group 等哪一类证据。
- `children_order`：前景/结构节点在前，背景/backplate 在后。
- `schema_id`：保留 Codia-like 的角色 + 坐标 + sequence 编号。

---

## 1. 证据优先级与审计边界

### 1.1 证据优先级

本审计采用以下证据优先级：

| 优先级 | 来源 | 使用方式 |
|---:|---|---|
| P0 | raw Codia/Figma canvas JSON | 最高优先级。凡是本文统计出的 018/022 数字，以 raw JSON analyzer 结果为准。 |
| P1 | sample PNG + OCR + M29 artifacts | 用于实现链路验证，包括 primitive、token、leaf IR、control IR 的召回/过检。 |
| P2 | 跨样本统计和本轮工程验证 | 可用于建立候选规则，但必须保留反例和验证命令。 |
| P3 | 推断和工程建议 | 必须标明为推荐路径，不当作已证明的 Codia 内部真实算法。 |

`docs/reference` 下的历史 prose / reverse-spec notes 不作为本计划实现真相源。实现和验收必须回到 raw JSON、PNG/OCR/M29 artifact、以及 analyzer 输出。

### 1.2 本次未能从 JSON 直接证明的事项

下面这些不能从 raw canvas JSON 单独证明，只能作为推断或工程建议：

- Codia 内部是否真的使用 Android View hierarchy、目标检测模型、或某个固定 11-class detector。
- Codia 原始编译器的训练数据来源。
- image hash 的生成算法、blob 的压缩/去重策略。
- Figma `commandsBlob` 与文字 glyph/vector 的完整生成过程。
- `StatusBar`、`ActionBar`、浏览器 URL pill 是否来自原始截图、插件 chrome、或 Codia 预处理。

工程实现可以采用这些推断，但验收不能把推断当事实。验收应基于最终树结构、role 分布、bbox、层级、排序、视觉 diff。

---

## 2. 上传 018 JSON 的事实基线

### 2.1 文件外壳

018 raw JSON 是独立 golden sample，不应被 022 的节点数或层级结论覆盖。它的外壳结构为：

```text
DOCUMENT "Document"
  CANVAS "Internal Only Canvas"
  CANVAS "Page 1"
    FRAME "Screenshot - 腾讯动漫_018_1440.png"
    FRAME "Figma design - 腾讯动漫_018_1440.png"
      FRAME "Root"
```

真正的设计树是右侧 `Figma design - 腾讯动漫_018_1440.png / Root`，不是左侧截图 frame。

### 2.2 018 设计树统计

| 指标 | 018 JSON 实际值 |
|---|---:|
| JSON `version` | 101 |
| Root size | `665 x 1440` |
| Root direct children | 3 |
| Design-root nodes | 146 |
| 规范化 max depth（Root=0） | 6 |
| Figma types | `FRAME: 41`, `TEXT: 48`, `ROUNDED_RECTANGLE: 57` |
| `schema:id` 覆盖 | 146/146 |
| `guid` 覆盖 | 146/146 |
| `schema:id` suffix 范围 | 0..145 |
| suffix 唯一性 | 146/146 |
| pluginID | 全部为 `1329812760871373657` |

### 2.3 018 role 分布

| Internal role | Count | Visible output |
|---|---:|---|
| `TextView` | 48 | `TEXT`，name 为文本内容 |
| `ImageView` | 39 | `ROUNDED_RECTANGLE "Image"` |
| `ViewGroup` | 24 | `FRAME "Groups"` |
| `Button` | 9 | `FRAME "Button"` |
| `bg_Button` | 9 | `ROUNDED_RECTANGLE "Background"` |
| `Background` | 9 | `ROUNDED_RECTANGLE "Background"` |
| `ListView` | 5 | `FRAME "Groups"` |
| `ActionBar` | 1 | `FRAME "Groups"` |
| `BottomNavigation` | 1 | `FRAME "Groups"` |
| `root` | 1 | `FRAME "Root"` |

关键差异：018 没有 `StatusBar` 和 `EditText` role；状态栏/浏览器栏相关元素在一个 `ActionBar` 中表达。022 的 “1 StatusBar + 1 EditText + 120 节点 + 5 root children” 是 022 样本特例，不适用于 018。

### 2.4 018 root children

018 的 Root 只有三个直接子节点：

| Index | Role / `schema:id` | Type / name | Abs bbox | Children |
|---:|---|---|---|---:|
| 0 | `ListView_8_30_19` | `FRAME "Groups"` | `(0,0,665,1301)` | 11 |
| 1 | `BottomNavigation_0_1299_2` | `FRAME "Groups"` | `(0,1299,665,141)` | 6 |
| 2 | `Background_0_1298_1` | `ROUNDED_RECTANGLE "Background"` | `(0,1298,665,142)` | 0 |

这三者存在明显重叠：`ListView` 到 y=1301，`BottomNavigation` 从 y=1299 开始，root-level `Background` 从 y=1298 开始。这直接证明 Codia 的树不是排他空间分割树。

### 2.5 018 layer/order 事实

| 指标 | 018 JSON 实际值 |
|---|---:|
| 多子节点 parent 数 | 41 |
| children 完全 y/x 排序的 parent | 14 |
| children 完全 x/y 排序的 parent | 10 |
| children suffix 严格降序的 parent | 41/41 |
| `Background` last-child | 9/9 |
| `bg_Button` last-child | 9/9 |

018 中，所有多子节点 parent 的 children 都按 schema suffix 降序排列；所有 Background / bg_Button 都是所在 parent 的最后一个 child。实现上应采用“前景/结构节点在前，背景/backplate 在后”的规则，而不是几何排序。

### 2.6 018 Button 模式

018 有 9 个 Button：

| Button 模式 | Count | 说明 |
|---|---:|---|
| `TextView + ImageView + bg_Button` | 2 | 顶部 URL pill、用户信息旁节省金额 pill |
| `TextView + bg_Button` | 7 | 价格角标、折扣标签、支付按钮、权益标签等 |

因此，“所有 Button 都是 text + icon + bg”不能作为通用规则。正确规则是：Button 必须有 owner-local `bg_Button`，但 foreground 可以是 text-only、text+icon、甚至跨样本出现 two text + bg。

### 2.7 018 cornerRadius 事实

018 中有 8 个带 corner radius 的节点：

- 4 个 `bg_Button`。
- 4 个普通 `Background`。

因此，“只有 Button/EditText 的 Background 有 cornerRadius”不能作为通用规则。正确规则是：radius 属于被检测到的可见背景/控制面，不应硬绑定到 `bg_Button` / `bg_EditText`。

### 2.8 018 Text 事实

| 指标 | 018 JSON 实际值 |
|---|---:|
| TextView count | 48 |
| name 与 `textData.characters` | 48/48 完全一致 |
| `textAlignVertical` | 48/48 为 `CENTER` |
| `lineHeight` | 48/48 为 `100 PERCENT` |
| `textAutoResize` | 47 个缺失，1 个 `HEIGHT` |
| 字体分布 | `PingFang SC Regular: 29`, `Inter Regular: 7`, `PingFang SC Medium: 4`, `Inter Semi Bold: 3`, `Inter Medium: 3`, `PingFang SC Semibold: 2` |
| fontSize 范围 | 13..51，median 20 |

结论：`name == textData.characters`、垂直居中、100% lineHeight 是强规则；`textAutoResize = NONE` 不是 018 通用事实，工程不应硬编码。

### 2.9 018 Image / Background fill 事实

| 类别 | Count |
|---|---:|
| `ImageView` + IMAGE fill | 39 |
| `Background` + SOLID fill | 5 |
| `Background` + IMAGE fill | 4 |
| `bg_Button` + IMAGE fill | 5 |
| `bg_Button` + SOLID fill | 4 |
| IMAGE fill 总数 | 48 |
| unique image hashes | 48 |

结论：不能按 fill type 区分 `Image` 与 `Background`。Background 可以是 image fill；bg_Button 也可以是 image fill。每个 image-like 节点基本是独立裁剪资产，不应实现成“整张截图 atlas + clip”。

---

## 3. Raw JSON 事实的逐项审计

### 3.1 可以直接保留为核心规格的结论

| 结论 | 来源 | 审计判断 | 工程动作 |
|---|---|---|---|
| Codia 不是 loose layer dump，也不是纯 XY-cut | 018/022 raw JSON 的 overlap、background sibling、non-space-partition tree | 保留 | 编译器主干必须是 role-aware pipeline。 |
| 内部 role 保存在 `schema:id` 中 | 018/022 raw JSON | 保留 | IR 必须显式存 role，不能只靠 Figma visible name。 |
| 可见 Figma type 集合极小：`FRAME/TEXT/ROUNDED_RECTANGLE` | 018/022 raw JSON | 保留 | 发射器只需覆盖这三类节点。 |
| visible name 机械化：`Root/Groups/Button/Text/Image/Background/text` | 018/022 raw JSON | 保留 | 不要输出 `Card/Nav/Tab/SearchBar` 等语义名。 |
| parent/children 允许 overlap 和 overflow | 018/022 raw JSON | 保留 | Tree builder 禁止使用“必须完全 containment”的硬约束。 |
| Background/backplate 往往作为 leaf sibling，且 order 靠后 | 018/022 raw JSON | 保留 | 不要把背景统一包装成 parent。 |
| Button/EditText 必须由背景证据驱动，不从 text bbox 单独合成 | raw JSON 的 owner-local bg_Button/bg_EditText 模式 + screenshot pixel evidence | 保留 | control synthesis 必须先于 generic grouping。 |
| ListView 与 ViewGroup 的边界是语义/行为边界，不是简单几何阈值 | 018/022 raw JSON | 保留 | 需要 collection/list/body/rail evidence。 |
| schema suffix 是 deterministic generation sequence | 018/022 raw JSON | 保留 | 实现稳定编号；当前 golden replay 使用 reverse-children DFS。 |

### 3.2 必须降级为样本特例的结论

| 原说法 | 审计结论 | 证据/原因 | 正确写法 |
|---|---|---|---|
| 设计树 120 nodes、max depth 5、Root 5 children | 022 特例 | 018 是 146 nodes、Root 3 children、max depth 6。 | 每个 golden sample 单独建 structural baseline。 |
| 1 个 StatusBar、1 个 EditText | 022 特例 | 018 有 `ActionBar`，没有 `StatusBar/EditText`。 | Chrome/input roles 必须按证据可选，不固定存在。 |
| 所有 Button 都是 text + icon + background | 错误作为通用规则 | 018 的 9 个 Button 中 7 个是 text + bg。 | Button = explicit `bg_Button` + foreground text/image 组合。 |
| 只有 Button/EditText 背景有 cornerRadius | 错误作为通用规则 | 018 中普通 `Background` 也有 cornerRadius。 | radius 属于可见背景/控制面检测结果。 |
| 所有节点 constraint 都是 `MAX/MAX` | 错误作为通用规则 | 018 中 145 个是 `MAX/MAX`，Root 是 `STRETCH/<missing>`。 | 大部分节点为 `MAX/MAX`，Root 允许例外。 |
| Root fill 是页面背景色且 opacity=1 | 错误作为通用规则 | 018 Root frame 是透明 fill opacity=0。 | Root fill 不能跨样本硬编码。 |
| `textAutoResize` 几乎总是 `NONE` | 022 特例 | 018 中 47 个缺失，1 个 HEIGHT。 | 发射时让 Figma/API 自然生成；验收不以固定字段为强规则。 |
| ViewGroup bbox 是 children 包围盒 | 错误作为通用规则 | 018/022 都有 padding、overflow、sibling background。 | ViewGroup bbox 来自区域/控件/list cell/background evidence。 |
| Tree construction = containment smallest-container-wins | 过度简化 | 018 有 sibling background、root overlap、children overflow。 | smallest-container 只能做 fallback；必须有 role-aware override。 |
| UI Component Detector = 固定 11 classes object detector | 未证实 | JSON 只能证明输出 role，不证明内部模型架构。 | 可以作为实现假设，不写成 Codia 事实。 |

### 3.3 对实现有约束力的反例

- `Button` 可以是 text-only + `bg_Button`，不能要求必有 icon。
- `Background` 可以是 SOLID，也可以是 IMAGE fill，不能用 fill type 推 role。
- `ListView` 可以表示内容 body、横向价格卡、权益网格或 strip，不能只靠 fanout。
- root-level children 可以重叠，不能使用排他空间切分树作为主干。
- `schema:id` 中的 x/y 更像 source/detector 坐标，不等于唯一 transform truth。

## 4. 修正后的 Codia-like 编译器契约

### 4.1 目标函数

实现不是为了生成漂亮的静态图，而是同时满足：

1. **视觉接近**：Figma 渲染结果接近原截图。
2. **结构接近**：节点类型、visible names、role 分布、bbox、层级、children order 接近 Codia。
3. **可追溯**：每个 Figma 节点能追溯回内部 IR node 和 source evidence。
4. **可调试**：错误可以定位到 OCR、crop、role classifier、tree builder、emitter 的具体阶段。
5. **可扩展**：不能为了某个腾讯动漫样本写死布局。

### 4.2 输出节点映射

| Internal role | Figma type | Visible name | 必要说明 |
|---|---|---|---|
| `root` | `FRAME` | `Root` | 设计树根。 |
| `ViewGroup` | `FRAME` | `Groups` | 通用结构容器。 |
| `ListView` | `FRAME` | `Groups` | 列表、滚动、重复、主体/rail 区域。 |
| `ActionBar` | `FRAME` | `Groups` | 顶部操作/浏览器/搜索区域。 |
| `StatusBar` | `FRAME` | `Groups` | 可选，不是每个样本都有。 |
| `BottomNavigation` | `FRAME` | `Groups` | 底部导航语义 frame。 |
| `Button` | `FRAME` | `Button` | 必须有 owner-local `bg_Button`。 |
| `EditText` | `FRAME` | `Text` | 必须有 owner-local `bg_EditText`，可无文字 child。 |
| `TextView` | `TEXT` | 文本内容 | `name == textData.characters` 是强规则。 |
| `ImageView` | `ROUNDED_RECTANGLE` | `Image` | 通常 IMAGE fill，但不要以 fill type 推 role。 |
| `Background` | `ROUNDED_RECTANGLE` | `Background` | 可 SOLID 或 IMAGE fill。 |
| `bg_Button` | `ROUNDED_RECTANGLE` | `Background` | Button 的 owner-local backplate，last child。 |
| `bg_EditText` | `ROUNDED_RECTANGLE` | `Background` | EditText 的 owner-local backplate，last child。 |

### 4.3 坐标契约

每个 IR node 必须存两个 bbox：

```text
source_bbox: 检测/OCR/crop/背景证据坐标，页面绝对坐标
figma_bbox:  最终发射到 Figma 的坐标，页面绝对坐标
```

发射到 Figma JSON/API 时：

```text
node.transform.m02 = node.figma_bbox.x - parent.figma_bbox.x
node.transform.m12 = node.figma_bbox.y - parent.figma_bbox.y
node.size.x = node.figma_bbox.w
node.size.y = node.figma_bbox.h
schema:id 中的 x/y 优先来自 source_bbox 或 detector bbox
```

为什么必须双 bbox：018 中 `TextView` 的 schema x 相对 emitted bbox x 通常偏左 0..6px，`ImageView` schema x/y 也常与 emitted bbox 有几像素差；raw JSON 显示 schema 坐标更像 source evidence 坐标，而不是唯一 transform 真相。

### 4.4 Parent-child 契约

必须允许：

- parent-child 局部 overflow。
- root direct children 重叠。
- region foreground 与 Background sibling 重叠。
- 大图/背景作为 sibling，而不是被迫成为 parent。
- 单子节点 ViewGroup，用于 touch target、list item slot、缩略图/标签语义边界。

禁止：

- 用非重叠空间切分树作为根层级主干。
- 用 child union 反推所有容器 bbox。
- 把所有视觉背景包装为 parent。
- 看到 `Image + Text` 就自动判 Button。

### 4.5 Children order 契约

推荐稳定规则：

```text
1. 结构/前景 content children 在前。
2. Background / bg_Button / bg_EditText / 大 backplate image 靠后。
3. 对 Button/EditText，owner-local bg 必须为最后 child。
4. 对普通 region，Background 通常靠后；可以允许少数 separator/特殊背景不是全局最后。
5. schema suffix 使用 deterministic sequence。018 中 reverse-children DFS 完全匹配，可作为第一版实现规则。
```

推荐 sequence 伪代码：

```pseudo
counter = 0
assign(root):
  root.seq = counter++
  for child in reverse(root.children):
    assign(child)
```

注意：sequence 是生成/层级调试信号，不是几何真相。

---

## 5. 推荐 IR 数据结构

### 5.1 基础类型

```ts
type Role =
  | 'root'
  | 'ViewGroup'
  | 'ListView'
  | 'ActionBar'
  | 'StatusBar'
  | 'BottomNavigation'
  | 'Button'
  | 'EditText'
  | 'TextView'
  | 'ImageView'
  | 'Background'
  | 'bg_Button'
  | 'bg_EditText';

type PaintKind = 'SOLID' | 'IMAGE' | 'NONE';

type EvidenceKind =
  | 'ocr_text'
  | 'image_crop'
  | 'solid_background'
  | 'rounded_background'
  | 'chrome_role'
  | 'control_role'
  | 'collection_role'
  | 'bottom_navigation_role'
  | 'repeated_cell_slot'
  | 'source_region'
  | 'residual_group';

interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}
```

### 5.2 IRNode

```ts
interface IRNode {
  id: string;                  // internal stable id
  role: Role;
  source_bbox: BBox;
  figma_bbox: BBox;
  visible_name: string;
  figma_type: 'FRAME' | 'TEXT' | 'ROUNDED_RECTANGLE';
  children: IRNode[];
  evidence: Evidence[];
  style: NodeStyle;
  asset?: AssetRef;
  text?: TextPayload;
  schema_id?: string;
  seq?: number;
}

interface Evidence {
  kind: EvidenceKind;
  bbox: BBox;
  confidence: number;
  source_id?: string;
  notes?: string;
}
```

### 5.3 样式契约

```ts
interface NodeStyle {
  opacity: number;
  visible: boolean;
  fillPaints: Paint[];
  strokePaints?: Paint[];
  strokeWeight?: number;
  strokeAlign?: 'INSIDE' | 'OUTSIDE' | 'CENTER';
  cornerRadius?: CornerRadius;
  font?: TextFont;
  lineHeight?: { value: number; units: 'PERCENT' | 'PIXELS' };
}
```

强建议：不要把 Figma 内部字段全部作为 IR 必填项。`derivedTextData`、`glyphs`、`fillGeometry`、`strokeGeometry`、`commandsBlob` 应由 Figma/API 或下游 serializer 生成。IR 只保留可解释、可验证、可生成的源信息。

---

## 6. 推荐编译 Pipeline

### 6.1 总流程

```text
INPUT: screenshot image or source canvas screenshot

0. Sample parser / analyzer
   - 读取 Codia golden JSON，建立结构验收基线。

1. Screenshot normalization
   - 统一像素尺寸、scale、颜色空间。

2. Primitive extraction
   - OCR TextView candidates：文本、bbox、字体、字号、颜色。
   - ImageView candidates：图片/图标/装饰 crop bbox。
   - Background candidates：实色区域、圆角区域、图片背景区域。
   - Thin marks：separator、cursor、home indicator 等。

3. Role classification and component detection
   - 先识别 Button/EditText/BottomNavigation/ActionBar/StatusBar 等强语义控件。
   - 再识别 ListView、repeated cell、rail、main body。
   - 最后做 residual ViewGroup。

4. Tree construction
   - role-aware ownership assignment。
   - 允许 overlap/overflow。
   - 背景作为 owner child 或 sibling，由 evidence 决定。

5. Coordinate fitting
   - source_bbox → figma_bbox。
   - text fitting：字体/字号/bbox 微调。
   - image/background crop fitting。

6. Layer ordering and schema numbering
   - foreground-first, background-late。
   - assign deterministic seq。
   - generate schema:id。

7. Figma emission
   - 优先使用 Figma Plugin API 创建节点。
   - 或生成最小可导入结构，再由 Figma 生成内部派生字段。

8. Validation
   - 结构验收：节点、role、bbox、parent、order。
   - 视觉验收：render diff。
   - 可追溯验收：每个节点有 source evidence。
```

### 6.2 为什么 control synthesis 必须早于 generic grouping

Button/EditText 不是普通空间组。它们有 owner-local background，且 background 在 children 数组最后。如果先用 generic grouping 或 XY-cut 处理，它们很容易被错误拆成：

```text
ViewGroup
  TextView
  ImageView
  Background
```

这在视觉上可能接近，但 role、visible name、schema:id、children order 都错。正确做法是：一旦检测到可交互控制面 + foreground text/icon，就先合成 `Button` 或 `EditText`，然后把合成后的 control node 交给上层 region/list 分配。

### 6.3 为什么 ListView 不能只靠 fanout 判断

018 中 `ListView` 包括：

- root-level 大内容区。
- 价格卡横向列表。
- 权益四宫格横向列表。
- 权益/宝藏榜水平图片 strip。

结合 018/022 raw JSON 和后续样本扩展，ListView 可表示 horizontal category tabs、floating side rail、main content body、keyboard suggestion strip 等。它不是“children 数量超过 N 的容器”。第一版可用以下证据加权：

| Evidence | 对 ListView 的支持 |
|---|---:|
| repeated cell slot | 高 |
| horizontal/vertical rail | 高 |
| scroll/body region | 高 |
| children 类型高度一致 | 中 |
| bbox 长条形 | 中，但不能单独决定 |
| 只有 2-3 个 children | 不能排除 |
| 混合 children | 不能排除 |

---

## 7. Tree Builder 设计

### 7.1 输入

Tree Builder 不应该直接吃 OCR bbox。它应该吃已经分类过的 IR candidates：

```text
TextView leaves
ImageView leaves
Background leaves
Button controls
EditText controls
region candidates
list/cell candidates
chrome candidates
bottom nav candidates
```

### 7.2 Ownership 规则优先级

推荐优先级：

1. `root` 固定为 viewport。
2. `BottomNavigation`、top chrome、major body、floating rail 等 root-level regions 先入树，允许互相 overlap。
3. `Button`、`EditText` 已经拥有自己的 `bg_*`，不再被拆。
4. Repeated cell/list slot 优先于 residual grouping。
5. Source background/image region 可以作为 owner，也可以作为 sibling；由 role evidence 决定。
6. 最后用 residual ViewGroup 收拢仍未归属的 foreground clusters。

### 7.3 背景归属判定

| 背景类型 | 推荐归属 |
|---|---|
| `bg_Button` | Button owner child，last |
| `bg_EditText` | EditText owner child，last |
| tab/nav backplate | BottomNavigation 或 row ViewGroup child，靠后 |
| 大内容 raster background | 可能是 region child，也可能是 region sibling；不要强制包装 |
| root-level bottom/home indicator | 可为 Root child 或 BottomNavigation inner child，按样本证据 |
| 卡片内实色/图像背景 | 若与 card region 强绑定，作为 card ViewGroup child，靠后 |

### 7.4 允许 overlap 的匹配策略

不要使用“一个像素区域只能属于一个 parent”的分割策略。应使用 ownership graph，再投影成树：

```pseudo
for candidate in high_level_regions:
  attach_to_root(candidate)

for control in controls:
  attach_to_best_region(control, allow_overlap=true)

for list in lists:
  attach_to_best_region_or_root(list, allow_overlap=true)

for leaf in leaves:
  parent = best_owner_by_role_evidence(leaf)
  if parent == null:
    parent = best_spatial_owner_with_overflow_tolerance(leaf)
  attach(leaf, parent)

for parent in all_containers:
  sort_children_foreground_then_background(parent)
```

“best owner”不能只用 IoU，还要看：role 类型、source evidence、z/layer关系、foreground/background关系、重复 cell slot、control ownership。

---

## 8. Figma 发射器设计

### 8.1 推荐目标

优先目标应是 **Figma Plugin API / 节点 API 发射**，不是手写完整 `.canvas.json`。

原因：

- JSON 中 `derivedTextData.glyphs`、`commandsBlob`、`fillGeometry`、`strokeGeometry` 等是 Figma 内部产物。
- image hash/blob 的生成与 Figma 资源管理相关，直接手写容易不可导入或不可稳定复现。
- guid/localID、editInfo、createdAt/lastEditedAt 也不应作为业务契约。

工程上可采用两层输出：

```text
IR JSON           // 自己可控、可测试、可 diff
Figma emitter     // 把 IR 发射到 Figma
Exported canvas   // 用于验收，不作为主写入接口
```

### 8.2 发射属性强规则

| 节点 | 强规则 |
|---|---|
| Container FRAME | visible true，opacity 1，translation-only transform，透明 fill，通常 strokeWeight 1。 |
| Root FRAME | size 等于 viewport；fill 不跨样本硬编码。 |
| TextView | `name == textData.characters`；字体/字号/颜色来自 fitting；lineHeight 100%；垂直居中。 |
| ImageView | `ROUNDED_RECTANGLE "Image"`；通常 IMAGE fill；imageScaleMode FILL；一般无 radius。 |
| Background | `ROUNDED_RECTANGLE "Background"`；可 SOLID 或 IMAGE；radius/stroke 来自检测。 |
| Button | `FRAME "Button"`；children 包含 `bg_Button` last。 |
| EditText | `FRAME "Text"`；children 包含 `bg_EditText` last；可以没有 TextView。 |

### 8.3 不要硬编码的属性

| 字段/属性 | 原因 |
|---|---|
| `localID` 连续性 | Figma 内部生成；不同运行可能不同。 |
| `editInfo.lastEditedAt` | 运行时元数据，不是结构契约。 |
| Root fill 颜色 | 跨 018/022 不一致。 |
| `textAutoResize` | 018 与 022 不一致。 |
| 所有 constraints 为 `MAX/MAX` | 018 root 有例外。 |
| cornerRadius 只给 control bg | 018 普通 Background 也有 radius。 |
| Button child count 固定为 3 | 018 有大量 text+bg Button。 |

---

## 9. 验收体系

### 9.1 结构验收必须优先于视觉验收

视觉相似不能证明结构正确。最小验收维度如下：

| 维度 | 验收内容 |
|---|---|
| Node vocabulary | 只使用允许的 Figma types 和 visible names。 |
| Identity | 每个节点有 compiler id / schema-like id，并可追溯 source evidence。 |
| Role distribution | 与 golden sample 的 role count 接近或完全匹配。 |
| Parent edges | Button/EditText/bg ownership、BottomNavigation/tab、ListView/cell 等关键边匹配。 |
| BBox | role-aware IoU / center delta / size delta。 |
| Order | foreground-first，control bg last，background late。 |
| Overlap policy | 不把合法 overlap 判为错误。 |
| Visual | Figma render 与源截图做 pixel diff。 |

### 9.2 018 golden sample hard checks

对于上传的 018 JSON，第一阶段实现可使用以下 hard checks：

| Check | Expected |
|---|---|
| Design root path | `Figma design - 腾讯动漫_018_1440.png / Root` |
| Root size | `665 x 1440` |
| Root direct children | 3 |
| Design nodes | 146 |
| Max depth（Root=0） | 6 |
| Types | `FRAME 41`, `TEXT 48`, `ROUNDED_RECTANGLE 57` |
| Roles | `TextView 48`, `ImageView 39`, `ViewGroup 24`, `Button 9`, `bg_Button 9`, `Background 9`, `ListView 5`, `ActionBar 1`, `BottomNavigation 1`, `root 1` |
| Schema coverage | 146/146 |
| Suffix range | 0..145，无缺失 |
| Multi-child parent sequence | 41/41 children suffix 降序 |
| Background last-child | `Background 9/9`, `bg_Button 9/9` |
| Buttons | 2 个 text+image+bg；7 个 text+bg |
| Text name/characters | 48/48 match |
| Image fills | 48 个 IMAGE fill，48 个 unique hash |

这些 checks 不代表所有样本都应如此，而是用于复刻当前上传样本。

### 9.3 Cross-sample checks

跨样本验收不应要求固定节点数，而应要求规则成立：

1. 所有节点有 identity 和 role。
2. visible vocabulary 关闭。
3. Button/EditText 背景 owner-local 且 last。
4. Background 可以是 SOLID 或 IMAGE。
5. Root/region 子节点允许 overlap。
6. ViewGroup/ListView 不由纯几何阈值决定。
7. bbox 有 `source_bbox` 和 `figma_bbox` 双轨。
8. 大图/背景可以作为 sibling，不强迫成为 parent。
9. BottomNavigation tab items 是 ViewGroup，不因为 image+text 自动变 Button。
10. 视觉 diff 与结构 diff 同时达标。

### 9.4 指标建议

| 指标 | 用途 | 建议门槛 |
|---|---|---:|
| Leaf recall | 文本/图标/背景是否漏检 | golden 样本先追求 95%+ |
| Text exact match | OCR 文案正确率 | 关键 UI 文案 100%，小装饰文本可分级 |
| Role precision | 避免把 ViewGroup/ListView/Button 混淆 | 高优先级 role 95%+ |
| Parent edge F1 | 树结构接近度 | golden 样本分角色计算 |
| BBox IoU | 节点几何接近度 | leaf 高，container role-aware |
| Background order accuracy | 层级/渲染正确性 | control bg 必须 100% |
| Pixel diff | 视觉接近度 | 与结构指标联合使用 |

---

## 10. 工程分阶段实施方案

### 阶段 0：建立样本分析器和 golden baseline

先不要做生成器。先写 analyzer，能对 Codia JSON 输出：

- design root 定位。
- node count / depth。
- type/name/role 分布。
- schema coverage / suffix continuity。
- bbox 绝对化。
- parent-child edge list。
- Background last-child 检查。
- Button/EditText 模式检查。
- overlap/overflow 报告。

这个 analyzer 是以后所有生成结果的验收器。

### 阶段 1：IR → Figma emitter

先用手工 IR 或从 golden JSON 反解出的 IR 发射 Figma 节点，验证发射器能生成正确 visible tree。这个阶段不做 CV/OCR。

目标：证明 `FRAME/TEXT/ROUNDED_RECTANGLE`、visible names、background ordering、schema-like ids、parent-relative coordinates 都能稳定发射。

### 阶段 2：Leaf extraction

实现：

- OCR text candidates。
- font/style/color fitting。
- image crop extraction。
- solid/rounded background detection。
- asset packaging。

目标：即使没有完美容器，也能重建 TextView/ImageView/Background leaves。

### 阶段 3：Control synthesis

优先实现：

- Button：explicit background + text/icon foreground。
- EditText：input/search background + icon/text/cursor。
- Bottom tab item：image + text 但无 owner-local background 时保持 ViewGroup。

这个阶段专门防止把控件降级为 generic groups。

### 阶段 4：Region/List classifier

实现：

- top chrome / ActionBar / StatusBar。
- BottomNavigation。
- main content body。
- ListView/repeated cells。
- floating rail/overlay。

目标：从纯 leaf/control 变成 Codia-like 浅树。

### 阶段 5：Residual ViewGroup + order + sequence

实现：

- 残余空间/语义 group。
- 背景 sibling vs owner child 决策。
- foreground-first ordering。
- reverse DFS schema sequence。

### 阶段 6：闭环验收与迭代

每次生成都跑：

```text
IR validation
→ Figma emission
→ canvas export
→ structural analyzer
→ render screenshot
→ pixel diff
→ error attribution by pipeline stage
```

---

## 11. 关键风险与控制措施

| 风险 | 严重性 | 触发信号 | 控制措施 |
|---|---:|---|---|
| 继续使用 XY-cut 当主干 | 极高 | root/region children 不重叠，树深过深，列表项被过度拆分 | 改成 role-aware region/control/list pipeline；XY-cut 只做 residual fallback。 |
| 没有内部 role IR | 极高 | 所有容器只有 Groups，无 ViewGroup/ListView/ActionBar 等内部角色 | 增加 IR role 和 schema-like id，不从 visible name 反推。 |
| 手写完整 canvas JSON | 高 | derivedTextData/geometry/blob/hash 不稳定或不可导入 | 用 Figma API 发射节点，canvas JSON 只做验收输出。 |
| 把 022 特例当通用规则 | 高 | 018/其他样本大量 hard check 失败 | 区分 per-sample baseline 与 cross-sample invariant。 |
| Button 识别过窄 | 高 | text+bg button 被降级为 ViewGroup | Button 支持 text+bg、text+icon+bg、two text+bg 等模式。 |
| 背景归属错误 | 高 | 大背景变 parent，前景 child 被错误包裹 | 背景作为 leaf sibling；只在 control/card 强 evidence 时归 owner。 |
| OCR bbox 直接当 Text node bbox | 中 | 文字位置/宽高与 Codia 偏差大 | 增加 text fitting：字体、字号、bbox、颜色联合优化。 |
| 只做视觉 diff | 高 | 视觉近似但 role/tree 全错 | 结构 diff 必须成为 release gate。 |
| dataset 太少 | 高 | 规则在新 app 上崩溃 | 持续加入 Codia raw JSON golden set，按 app 类型分层验收。 |

---

## 12. 最小可交付定义（Definition of Done）

一个工程版本只有满足以下条件，才算“这个东西能够做出来”的第一阶段可用版本：

1. 能解析上传的 018 JSON 并复现本文第 2 节的统计结果。
2. 能从内部 IR 发射一个 Figma-like tree，满足 visible type/name/role 映射。
3. 每个节点有 source id、role、source_bbox、figma_bbox、schema-like id。
4. Button/bg_Button、EditText/bg_EditText ownership 正确。
5. Background 不被统一包装成 parent。
6. Root/region 允许 overlap，tree builder 不强制非重叠。
7. 018 hard checks 至少先在“由 golden IR 回放发射”的模式下通过。
8. 视觉 diff 与结构 diff 都能自动跑。
9. 工程文档明确哪些是 per-sample baseline，哪些是 cross-sample invariant。
10. 失败报告能定位到 OCR、image crop、background detection、role classifier、tree builder、emitter 中的一个阶段。

---

## 13. 给工程团队的最终规格摘要

可以把下面这段直接放到任务说明里：

```text
Build a Codia-like screenshot-to-Figma compiler.

Do not build a pure XY-cut layer splitter.
The compiler must preserve an internal UI role IR and emit a simple Figma visible tree.
Visible Figma nodes are limited to FRAME, TEXT, and ROUNDED_RECTANGLE.
Visible names are mechanical: Root, Groups, Button, Text, Image, Background, or literal text.
Internal roles are stored in schema-like ids: ViewGroup, ListView, ActionBar, StatusBar,
BottomNavigation, Button, EditText, TextView, ImageView, Background, bg_Button, bg_EditText.

Every node must have source_bbox and figma_bbox.
Parent-child relationships may overlap and overflow.
Backgrounds are leaf siblings/backplates, not universal wrappers.
Button/EditText must be synthesized from explicit background evidence before generic grouping.
ListView is a semantic collection/body/rail role, not a geometry threshold.
Children are ordered foreground-first and background-late; control backgrounds are last.
Use deterministic sequence ids, preferably reverse-children DFS.

Prefer Figma Plugin API emission over direct hand-written canvas JSON.
Validate with both structural diff and visual render diff.
For the uploaded 018 golden sample, match the 146-node, 3-root-child, role-count baseline.
For 022 and other samples, use their own baselines and enforce only cross-sample invariants globally.
```

---

## 附录 A：018 样本的树骨架

```text
Root (665x1440)
├── ListView_8_30_19 (0,0,665,1301), children=11
│   ├── TextView "Ｖ会员特权"
│   ├── TextView "更多权益"
│   ├── ActionBar_0_0_135 (0,0,665,74)
│   │   ├── TextView "11:02"
│   │   ├── Button URL pill: TextView + ImageView + bg_Button
│   │   ├── ImageView signal/wifi/battery-like assets
│   ├── ViewGroup_30_80_62 (30,80,610,752), children=12
│   │   ├── header/user/payment texts and buttons
│   │   ├── ListView_30_283_88 price cards
│   │   ├── ListView_62_524_69 gift tiles
│   │   ├── payment Button text+bg
│   │   └── large ImageView background/artwork
│   ├── ListView_19_907_36 privilege row, children=5
│   ├── ViewGroup_20_1078_22 treasure strip
│   ├── large ImageView_0_0_21 (0,0,665,1299)
│   └── Background_0_1297_20 separator
├── BottomNavigation_0_1299_2 (0,1299,665,141)
│   ├── five ViewGroup tab items: 推荐 / 圈子 / V会员 / 书架 / 我的
│   └── Background home indicator image
└── Background_0_1298_1 (0,1298,665,142)
```

---

## 附录 B：实现 checklist

### B.1 Parser/analyzer checklist

- [ ] 定位 `Figma design - ... / Root`，不要分析 screenshot frame。
- [ ] 计算 absolute bbox。
- [ ] 解析 `schema:id` role/x/y/seq。
- [ ] 校验 guid/schema coverage。
- [ ] 输出 type/name/role count。
- [ ] 输出 root children。
- [ ] 输出 max depth。
- [ ] 输出 background last-child 报告。
- [ ] 输出 button/editText 模式报告。
- [ ] 输出 overlap/overflow 报告。

### B.2 IR checklist

- [ ] 每个节点有 `role`。
- [ ] 每个节点有 `source_bbox`。
- [ ] 每个节点有 `figma_bbox`。
- [ ] 每个节点有 `evidence[]`。
- [ ] 每个节点有 stable `id`。
- [ ] 每个发射节点有 schema-like id。
- [ ] role 到 visible name 的映射集中定义，不分散硬编码。

### B.3 Tree builder checklist

- [ ] control synthesis 先于 residual grouping。
- [ ] Background 归属有专门规则。
- [ ] 允许 overlap/overflow。
- [ ] 不以 child union 作为唯一 bbox 来源。
- [ ] ListView 分类有 collection/body/rail evidence。
- [ ] BottomNavigation tab item 不误判 Button。
- [ ] children order 不使用纯 x/y sort。

### B.4 Emitter checklist

- [ ] 只发射 `FRAME/TEXT/ROUNDED_RECTANGLE`。
- [ ] visible name 只使用允许词汇。
- [ ] TextView `name == characters`。
- [ ] Button bg last。
- [ ] EditText bg last。
- [ ] Image/Background fill type 不反推 role。
- [ ] schema-like id unique。
- [ ] sequence deterministic。

### B.5 Validation checklist

- [ ] 018 golden hard checks 通过。
- [ ] 022 golden hard checks 单独通过。
- [ ] 跨样本 invariant 通过。
- [ ] 结构 diff 报告可读。
- [ ] render diff 报告可读。
- [ ] 每次失败能定位 pipeline stage。

---

## 附录 C：需要保留的开放问题

1. `ViewGroup` 与 `ListView` 的精确分类边界仍然需要更多样本验证。
2. root-level `ImageView` 与 `Background` 的边界不能只靠 fill type 或 bbox。
3. `StatusBar` 与 `ActionBar` 的拆分在 018/022 之间已经不同，不能硬编码固定结构。
4. `schema:id` 的 x/y 更像 source/detector bbox，不应作为唯一 transform 坐标。
5. `commandsBlob`、`derivedTextData`、image hash/blob 不应成为第一版自研 serializer 的目标。
6. 如果未来目标是“直接生成 canvas JSON 文件而不经过 Figma API”，需要单独立项研究 Figma 内部序列化格式。

---

## 附录 D：最终推荐

采用 raw Codia/Figma canvas JSON 作为主规格基线；任何 prose 结论都必须被 analyzer 统计或真实样本 artifact 验证后才能进入实现合同。工程启动时先做 analyzer + IR emitter，而不是先做 CV 模型；否则很难知道生成结果到底错在识别、分组还是发射。

第一版可用目标应定义为：

```text
先在 golden IR replay 模式下复现 018/022 的结构，
再逐步替换为真实截图 primitive extraction 和 role classifier。
```

这样能把“Figma 发射正确性”和“截图理解正确性”分开验证，避免在一个大黑盒里同时调 OCR、检测、树构建、Figma 序列化。
