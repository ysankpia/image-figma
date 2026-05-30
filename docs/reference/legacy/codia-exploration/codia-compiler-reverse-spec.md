# Codia 编译器逆向规格（从真实 canvas JSON 完整解码）

> 数据来源：`腾讯动漫主要.canvas.json`（腾讯动漫022），120 节点，max depth=5
> 交叉验证：`tencent-comic-018.canvas.json`、`tencent-comic-022.canvas.json`、`lizhi-011.canvas.json`、`xianyu.canvas.json`

---

## 1. 文件结构

```json
{
  "version": 101,
  "root": { "type": "DOCUMENT", "children": [CANVAS, CANVAS] },
  "blobs": { ... }
}
```

- `root.children[0]` = "Internal Only Canvas"（空）
- `root.children[1]` = "Page 1"，包含：
  - `FRAME "Screenshot - ..."` — 原始截图占位
  - `FRAME "Figma design - ..."` → `FRAME "Root"` — 真正的设计树

---

## 2. 节点类型（仅 3 种）

| Figma Type | Codia 用途 | 命名规则 |
|---|---|---|
| `FRAME` | 所有容器（ViewGroup/Button/ListView/StatusBar/EditText/BottomNavigation） | "Root" / "Groups" / "Button" / "Text" |
| `ROUNDED_RECTANGLE` | 所有视觉元素（图片、图标、背景矩形） | "Image" / "Background" |
| `TEXT` | 文本 | 文本内容本身（如 "11:02"、"uinotes.com"） |

**关键发现：Codia 不使用 RECTANGLE、ELLIPSE、VECTOR、COMPONENT、INSTANCE 等类型。所有形状统一为 ROUNDED_RECTANGLE。**

---

## 3. 命名规则

### FRAME 命名
- `"Root"` — 根容器（唯一）
- `"Groups"` — 通用空间分组容器（占 32/38 = 84%）
- `"Button"` — 按钮/可交互控件
- `"Text"` — 文本输入框（EditText）

### ROUNDED_RECTANGLE 命名
- `"Image"` — 图片、图标、装饰元素（37/46 = 80%）
- `"Background"` — 背景矩形（9/46 = 20%）

### TEXT 命名
- 直接使用文本内容作为 name

---

## 4. schema:id 系统（pluginData）

每个节点都有 `pluginData[].key == "schema:id"`，格式：

```
{SchemaType}_{AbsX}_{AbsY}_{GlobalSeq}
```

- **SchemaType**：Codia 的内部 UI 组件分类
- **AbsX, AbsY**：节点在页面中的绝对坐标（±5px 精度）
- **GlobalSeq**：全局递增序号（0-119），**从底部导航开始递增到状态栏**

### SchemaType 分布

| SchemaType | 数量 | 对应 |
|---|---|---|
| ImageView | 37 | 图片/图标 |
| TextView | 36 | 文本 |
| ViewGroup | 25 | 通用容器 |
| ListView | 5 | 列表/滚动容器 |
| Button | 4 | 按钮 |
| Background | 4 | 大区域背景 |
| bg | 5 | 控件内背景（bg_Button_x_y_seq） |
| root | 1 | 根 |
| StatusBar | 1 | 状态栏 |
| EditText | 1 | 输入框 |
| BottomNavigation | 1 | 底部导航 |

### bg_ 前缀规则

背景矩形的 schema:id 使用 `bg_{ParentSchemaType}_{AbsX}_{AbsY}_{Seq}` 格式：
- `bg_Button_242_9_116` — Button 的背景
- `bg_EditText_22_155_96` — EditText 的背景

---

## 5. 坐标系统

- **transform**：`{m00, m01, m02, m10, m11, m12}` — 2D 仿射变换，m02=相对X，m12=相对Y
- **size**：`{x, y}` — 宽度和高度
- 坐标是**相对于父容器**的
- schema:id 中的坐标是**绝对坐标**（页面级）

---

## 6. Z-Order（渲染顺序）

**children 数组排列：前景在前（index 0），背景在后（last index）。**

所有 27 个多子节点容器都严格遵守**降序排列**（高 seq 在前）。

这意味着：
- Background 总在 children 数组的**最后位置**
- TEXT 和 Image（前景内容）在**前面位置**
- 渲染时从后往前画：先画 Background，再画前景

---

## 7. 容器创建规则（核心）

### 7.1 ViewGroup（通用空间分组）

**创建条件**：视觉上属于同一区域的元素被分组到一个 ViewGroup。

**子模式分类**：

| 模式 | 数量 | 特征 |
|---|---|---|
| mixed（混合内容） | 13 | 包含不同类型的子节点 |
| single_TextView | 5 | 只包含 1 个 TEXT（tab 标签） |
| single_ImageView | 5 | 只包含 1 个 Image（缩略图容器） |
| has_background | 2 | 包含 Background 子节点的区域容器 |

**关键观察**：
- ViewGroup 可以只有 1 个子节点（用于给单个元素提供独立的坐标空间）
- ViewGroup 不使用 Auto Layout（layoutMode = null）
- ViewGroup 没有 fills（透明容器）
- ViewGroup 的 bbox 是其所有子节点的包围盒

### 7.2 ListView（列表容器）

**创建条件**：包含重复结构的区域。

特征：
- 顶部 tab 栏（水平重复的 ViewGroup）
- 侧边栏（垂直重复的缩略图）
- 内容区域（垂直重复的卡片）
- 底部标签页切换条

### 7.3 Button（按钮控件）

**创建条件**：有明确背景 + 文本/图标的可交互元素。

固定结构：
```
FRAME "Button" [has Background]
├── TEXT "文案"           ← index 0 (前景)
├── ROUNDED_RECTANGLE "Image"  ← index 1 (图标，可选)
└── ROUNDED_RECTANGLE "Background" ← last index (背景)
```

特征：
- 总是 3 children（text + icon + bg）或 2 children（text + bg）
- Background 有 `rectangleCornerRadius`（圆角）
- Background 的 fillPaints 是 SOLID 颜色
- Button 的 size 比 TEXT 大（有 padding）

### 7.4 StatusBar

**创建条件**：页面顶部的系统状态栏区域。

### 7.5 EditText（输入框）

**创建条件**：搜索框/输入框区域。

结构：
```
FRAME "Text" [EditText]
├── ROUNDED_RECTANGLE "Image"      ← 搜索图标
└── ROUNDED_RECTANGLE "Background" ← 输入框背景
```

### 7.6 BottomNavigation

**创建条件**：页面底部的导航栏。

---

## 8. Background 规则

### 8.1 何时创建 Background

Background 只在以下情况创建：
1. **Button/EditText 的内部背景**：圆角矩形，SOLID 填充，schema:id 前缀 `bg_`
2. **大区域背景**：覆盖整个容器的矩形，schema:id 前缀 `Background`

### 8.2 Background 的属性

- `fillPaints`: SOLID 颜色（如 `rgba(0.965, 0.969, 0.965, 1.0)` 浅灰）
- `rectangleCornerRadius`: 圆角值（Button 背景通常 16px）
- `strokeWeight`: 0（无边框）
- 位于 children 数组的**最后位置**

### 8.3 何时 NOT 创建 Background

- **纯文本区域不创建 Background**
- **图片列表不创建 Background**
- **只有当区域有明确的视觉背景色时才创建**

---

## 9. 树深度与扇出

```
depth 0: 1 node  (Root)
depth 1: 5 nodes (大区域划分)
depth 2: 10 nodes
depth 3: 34 nodes (主要内容层)
depth 4: 68 nodes (叶子层)
depth 5: 2 nodes  (极少数深层)
```

- Max depth = 5（极浅）
- 典型路径：Root → 区域 → 子区域 → 内容容器 → 叶子
- 扇出：depth 1 平均 5 children，depth 2 平均 3.4，depth 3 平均 2.0

---

## 10. 全局序号（GlobalSeq）分配规则

序号从 0 开始，**从页面底部向顶部递增**：

```
seq 0:   Root
seq 1:   BottomNavigation (底部导航)
seq 2-19: 底部导航内部节点
seq 20-70: 主内容区域（从下往上）
seq 71-84: 侧边栏和顶部区域
seq 85-119: 状态栏和顶部控件
```

这暗示 Codia 的处理顺序是**从底部向顶部扫描**。

---

## 11. 节点属性完整列表

### FRAME 属性
```
guid, phase, type, name, visible, opacity, size, transform,
strokeWeight, strokeAlign, strokeJoin, fillPaints, fillGeometry,
horizontalConstraint, verticalConstraint, frameMaskDisabled,
pluginData, editInfo, children
```

### ROUNDED_RECTANGLE 属性
```
guid, phase, type, name, visible, opacity, size, transform,
strokeWeight, strokeAlign, strokeJoin, fillPaints, fillGeometry,
horizontalConstraint, verticalConstraint,
rectangleTopLeftCornerRadius, rectangleTopRightCornerRadius,
rectangleBottomLeftCornerRadius, rectangleBottomRightCornerRadius,
rectangleCornerRadiiIndependent,
pluginData, editInfo
```

### TEXT 属性
```
guid, phase, type, name, visible, opacity, size, transform,
fontSize, textAlignVertical, lineHeight, fontName, textData,
derivedTextData, letterSpacing, fontVersion, leadingTrim,
textUserLayoutVersion, textExplicitLayoutVersion, fontVariations,
textBidiVersion, emojiImageSet,
strokeWeight, strokeAlign, strokeJoin, fillPaints,
textDecorationSkipInk, horizontalConstraint, verticalConstraint,
pluginData, autoRename, textTracking, textAutoResize
```

---

## 12. fillPaints 规则

| 场景 | fillPaints |
|---|---|
| FRAME 容器 | `[{type:"SOLID", color:{r:0,g:0,b:0,a:1}, opacity:0}]`（透明黑 = 无填充） |
| Background 矩形 | `[{type:"SOLID", color:{...}, opacity:1}]`（实色填充） |
| Image 矩形 | `[{type:"IMAGE", imageRef:"hash", ...}]`（图片填充） |
| TEXT | `[{type:"SOLID", color:{r,g,b,a}}]`（文字颜色） |

---

## 13. 关键设计决策总结

1. **只用 3 种 Figma 类型**：FRAME（容器）、ROUNDED_RECTANGLE（视觉元素）、TEXT
2. **不使用 Auto Layout**：所有布局通过绝对坐标定位
3. **不使用 Component/Instance**：每个元素都是独立的
4. **Background 是兄弟不是包装器**：背景矩形和前景内容是同级 children
5. **Z-order = 前景在前**：children[0] 是最上层，children[last] 是最底层
6. **命名极度机械化**：容器叫 "Groups"/"Button"/"Text"，矩形叫 "Image"/"Background"，文本用内容
7. **schema:id 暴露内部分类**：ViewGroup/ListView/Button/StatusBar/EditText/BottomNavigation
8. **树极浅**：max depth 5，大部分内容在 depth 3-4
9. **单子节点容器合法**：ViewGroup 可以只包含 1 个 child（提供坐标空间/touch target）
10. **从底部向顶部编号**：GlobalSeq 从 BottomNavigation 开始递增到 StatusBar

---

## 14. 二次审核关键修正

### 14.1 容器 bbox 不是 children 的紧凑包围盒

容器的 size 通常**大于** children 的包围盒（有 padding）。38 个容器中：
- 5 个 TIGHT（padding ≤ 2px）
- 30 个 PADDED（有明确 padding）
- 3 个 OVERFLOW（children 超出容器边界）

**Button 的 padding 模式**：约 (5-8, 6, 3-5, 0-3)px，不对称。

### 14.2 容器之间允许重叠（非排他空间分割）

**这是与我们 xycut 方法的根本差异。**

Root 的 5 个子节点之间存在大量重叠：
- 主内容区 (Y=160-1339) 与 header (Y=0-236) 重叠 76px
- 主内容区与侧边栏完全重叠
- 主内容区与底部导航重叠 55px

**结论：Codia 的树不是空间分割树，是语义分层树。** 不同语义层（header、content、sidebar、footer）可以在空间上重叠。这意味着 XY-cut（排他空间分割）从根本上就不是正确的算法。

### 14.3 列表项保持平铺，不做子分组

排名列表区域（ViewGroup_21_236_57）有 12 个 children 全部平铺：
- 7 个 TEXT（标题、副标题、热度值）
- 5 个 ROUNDED_RECTANGLE（封面、图标、背景）

**Codia 不为每个列表项创建子容器。** 整个列表区域是一个扁平的 ViewGroup。

这与我们的 xycut 行为完全相反——xycut 会在列表项之间的间隙处切分，为每个项创建子容器。

### 14.4 单子节点容器的存在理由

11 个单子节点容器的用途：
- **Tab 标签**（5 个）：为每个 tab 文本提供 touch target 区域（有 padding）
- **缩略图**（2 个）：为图片提供点击区域
- **Tab bar 图片**（3 个）：为底部 tab 图片提供容器
- **BottomNavigation**（1 个）：语义包装

**规则：单子节点容器存在于需要独立 touch target 或语义边界的场景。**

### 14.5 Constraint 系统完全统一

所有 120 个节点的 `horizontalConstraint` 和 `verticalConstraint` 都是 `"MAX"`。Codia 不使用 constraint 做响应式布局。

### 14.6 容器分组的真正判据（语义而非几何）

**创建子容器的条件**：
1. 元素是可交互的 touch target（Button、Tab、缩略图）
2. 元素有独立的视觉背景（Button 有 Background 子节点）
3. 元素是水平重复列表中的 item（tab 栏的每个 tab）

**不创建子容器的条件**：
1. 垂直列表中的 item（保持平铺）
2. 同一区域内的混合内容（标题 + 图标 + 文本 = 平铺）
3. 没有独立交互意义的元素组合

### 14.7 与我们当前实现的根本差异

| 维度 | Codia | 我们的 xycut |
|---|---|---|
| 分组算法 | 语义分类（Android UI 组件识别） | 几何空间分割（gap 检测） |
| 容器重叠 | 允许（语义层可重叠） | 不允许（排他分割） |
| 列表项 | 平铺在一个容器里 | 每个 item 一个子容器 |
| 分组判据 | touch target / 交互边界 | 空间间隙大小 |
| 背景处理 | 兄弟节点，放在 children 最后 | 包装器容器 |
| 树深度 | max 5，大部分内容 depth 3-4 | 可达 8+，递归切分 |

---

## 15. 容器 bbox 计算规则（第一轮深度审核）

### 15.1 容器 bbox 来自视觉区域检测，不是 children 包围盒

**证据**：
- Tab 标签容器（单 TEXT child）的 padding 不对称、不统一（L=17-22, T=9-28, R=15-30, B=13-17）
- 容器尺寸不规则（152x76, 98x75, 94x63, 91x64, 91x65）
- 没有一致的 padding 公式能解释这些数值

**结论**：Codia 先从截图中检测 UI 组件的视觉边界（可能用目标检测模型），得到容器 bbox，然后把识别出的内容元素放入容器中。容器不是从 children 计算出来的，children 是放进容器里的。

### 15.2 三层 bbox 嵌套关系

```
Container bbox >= Background bbox >= Content bbox
```

- **Container bbox**：从截图视觉检测得到的组件区域（包含 padding/margin）
- **Background bbox**：实际可见的背景矩形（比 container 小，有 inset）
- **Content bbox**：文本/图标的紧凑包围盒

Button 的典型关系：
```
Container: 177x50
Background: 166x41 @(8,6)   ← inset 约 5-8px
Content: 148x23 @(16,15)    ← 在 Background 内部
```

### 15.3 Padding 按 schema_type 的统计

| SchemaType | 平均 padding (L,T,R,B) | 特征 |
|---|---|---|
| ViewGroup | (19, 10, 24, 20) | 变化大，来自视觉检测 |
| ListView | (1, 0, 0, 10) | 几乎无 padding（紧贴内容） |
| Button | (16, 10, 13, 5) | 有明确 padding（touch target） |
| StatusBar | (73, 9, 45, 8) | 大左 padding（避开系统图标） |
| BottomNavigation | (0, 14, 0, 1) | 顶部有 padding |

### 15.4 Background 的两种模式

1. **FULL-BLEED**：Background size == Container size，起点 (0,0)
   - 用于大区域背景（header、bottom nav）
   - fill 可以是 IMAGE 或 SOLID

2. **INSET**：Background 比 Container 小，有 offset
   - 用于 Button、EditText
   - offset 约 (3-8, 0-6)px
   - 有 cornerRadius（圆角）
   - fill 是 SOLID 颜色

---

## 16. fillPaints 规则（第 2 轮深度审核）

### 16.1 每个 Image 节点有独立的图片数据

41 个 IMAGE fill 有 **41 个不同的 hash**。Codia 为每个视觉元素单独裁剪了图片，不是共享一张截图。每个 ROUNDED_RECTANGLE "Image" 都是一个独立的裁剪区域。

### 16.2 fillPaints 完整规则

| 节点类型 | fill 规则 |
|---|---|
| FRAME 容器 | `{type:"SOLID", color:{0,0,0,1}, opacity:0}` — 透明（不可见） |
| FRAME "Root" | `{type:"SOLID", color:{0.949,0.976,0.996,1}, opacity:1}` — 页面背景色 |
| ROUNDED_RECT "Image" | `{type:"IMAGE", image:{hash:[...]}}` — 独立裁剪图片 |
| ROUNDED_RECT "Background" (控件) | `{type:"SOLID", color:{~0.96,~0.96,~0.96,1}}` — 采样的背景色 |
| ROUNDED_RECT "Background" (区域) | `{type:"IMAGE", image:{hash:[...]}}` — 区域背景裁剪 |
| TEXT | `{type:"SOLID", color:{r,g,b,1}}` — 从截图采样的文字颜色 |

### 16.3 TEXT 颜色采样

每个 TEXT 有独立的颜色，从截图中对应位置采样：
- 深灰色文本：rgba(0.17-0.40, ...) — 标题、正文
- 中灰色文本：rgba(0.50-0.73, ...) — 副标题、辅助信息
- 彩色文本：蓝色(0.37,0.66,0.95) = 链接，橙色(0.72,0.53,0.25) = 强调

### 16.4 Background SOLID 颜色

所有 Button/EditText 的 Background 颜色都在 (0.95-1.0) 范围内（近白/浅灰），从截图中背景区域采样。

---

## 17. cornerRadius 规则（第 3 轮深度审核）

### 17.1 只有 Button/EditText 的 Background 有 cornerRadius

46 个 ROUNDED_RECTANGLE 中只有 4 个有 cornerRadius，全部是 `bg_Button` 或 `bg_EditText`。

### 17.2 cornerRadius 值

- 总是 uniform（四角相同）
- 值 = shortSide 的 39-51%（接近半圆/胶囊形）
- `rectangleCornerRadiiIndependent: true`（即使四角相同也标记为独立）

### 17.3 普通 Image 节点没有 cornerRadius

所有 37 个 "Image" ROUNDED_RECTANGLE 的 cornerRadius = 0。虽然类型名是 ROUNDED_RECTANGLE，但实际是直角矩形。

---

## 18. TEXT 属性规则（第 4 轮深度审核）

### 18.1 字体

- 中文：PingFang SC（Regular 72%, Medium 17%, Semibold 3%）
- 英文/数字：Inter（Regular + Semi Bold）

### 18.2 fontSize

从截图中检测，范围 10-49px。没有统一的 type scale。

### 18.3 固定属性（所有 TEXT 相同）

- `textAlignVertical: "CENTER"`
- `lineHeight: {value: 100, units: "PERCENT"}`
- `textAutoResize: "NONE"`（35/36）
- `letterSpacing: {value: 0, units: "PERCENT"}`

### 18.4 TEXT size 计算

TEXT 的 size 不等于文字的 intrinsic size。它是从截图中检测到的文字区域 bbox，可能比文字本身大（包含行间距/字间距的视觉空间）。

---

## 19. GlobalSeq 分配算法（第 5 轮深度审核）

### 19.1 遍历算法

**PRE-ORDER DFS，children 逆序遍历**：

```
function assignSeq(node, counter):
    node.seq = counter++
    for child in reverse(node.children):  // 从最后一个 child 开始
        counter = assignSeq(child, counter)
    return counter
```

### 19.2 效果

- Root = seq 0
- 最后一个 child 的子树先编号（底部导航 = seq 1-19）
- 第一个 child 的子树最后编号（状态栏 = seq 111-119）
- 每个子树的 seq range 严格连续（无间隙）

### 19.3 语义含义

由于 children 数组是前景在前（index 0 = z-top），逆序遍历意味着：
- **低 seq = 背景层**（先画）
- **高 seq = 前景层**（后画）
- seq 顺序 = 渲染顺序（从后往前）

---

## 20. ListView vs ViewGroup 判据（第 6 轮）

### 20.1 ListView 的语义

ListView 表示**可滚动或重复内容区域**：
- 水平 tab 栏（aspect=8.29）
- 垂直侧边栏（aspect=0.06）
- 主内容滚动区域（aspect=0.56）
- 水平 tab 指示条（aspect=21.34）

### 20.2 判据

| 特征 | ListView | ViewGroup |
|---|---|---|
| 语义 | 可滚动/重复 | 静态分组 |
| 典型 children | 重复结构的 ViewGroup | 混合内容 |
| 嵌套 | 可嵌套 ListView | 不嵌套自身 |
| 几何 | 无特定约束 | 无特定约束 |

**判据是语义的（Android 组件类型），不是几何的。** 无法从 bbox/children 结构推导出 ListView vs ViewGroup。

---

## 21. Button 识别条件（第 7 轮）

### 21.1 Button 的必要条件

**Button = 有 "Background" 子节点的容器。**

所有 4 个 Button 都有：
1. 一个 TEXT child（按钮文案）
2. 一个 ROUNDED_RECTANGLE "Image" child（图标）
3. 一个 ROUNDED_RECTANGLE "Background" child（背景矩形）

### 21.2 Button vs ViewGroup 的区分

底部导航的 tab 项（ViewGroup）也有 Image + Text，但**没有 Background 子节点**。

**规则：有可见背景矩形 → Button；无背景矩形 → ViewGroup。**

这意味着 Button 分类器检测的是：截图中是否存在一个有颜色/圆角的背景区域在文本后面。

---

## 22. 语义分层模型（第 9 轮）

### 22.1 Android Activity Layout 映射

Codia 将截图映射到 Android 的 Activity 布局模型：

```
Root
├── Header (ViewGroup): StatusBar + ActionBar + SearchBar
├── Sidebar (ListView): 浮动在内容上方的侧边栏
├── Content (ListView): 主滚动内容区域
├── Decorative (Background): 小装饰元素
└── BottomNavigation: 底部导航栏
```

### 22.2 层级重叠是正确行为

Content 区域 (Y=160-1339) 延伸到 Header (Y=0-236) 和 BottomNav (Y=1284-1440) 的后面。这不是 bug，而是 Android 的 `fitsSystemWindows` / `CoordinatorLayout` 行为的正确表达。

---

## 23. 固定属性（第 8 轮）

所有节点统一设置，Codia 不做个性化：
- `opacity: 1`
- `visible: true`
- `strokeWeight: 1`（Background 为 0）
- `strokeAlign: "INSIDE"`（TEXT 为 "OUTSIDE"）
- `horizontalConstraint: "MAX"`
- `verticalConstraint: "MAX"`
- `frameMaskDisabled: true`（不裁剪溢出）

---

## 24. guid 系统（第 11 轮）

- 所有节点 `sessionID: 2`（单一 session）
- `localID` 范围 [5, 124]，连续无间隙
- 120 个节点 = 120 个唯一 localID

---

## 25. 生成时间戳（第 12 轮）

所有节点在 **5 秒内**创建完成（2026-05-29 12:41:31 ~ 12:41:36）。
单一 userId。确认：Codia 通过 Figma Plugin API 在一次原子操作中生成整棵树。

---

## 26. schema:id 坐标来源（第 15 轮）

schema:id 中的 (X, Y) 是**检测模型的原始输出坐标**（绝对页面坐标），不是 Figma 树中的相对坐标。

- 86% 的节点：schema 坐标与计算的绝对坐标差 ≤ 5px
- 97% 的节点：差 ≤ 10px
- 4 个 outlier 全是 ListView（树构建时位置被调整）

**确认的 pipeline**：
```
1. 检测模型输出 bbox（绝对坐标）→ 记录到 schema:id
2. 分类器标注组件类型（ViewGroup/Button/ListView/...）
3. 树构建器将元素分组到容器中
4. 坐标转换为相对于父容器
5. schema:id 保留原始检测坐标不变
```

---

## 27. 跨样本验证（第 14 轮）

腾讯动漫018 与 022 对比：

| 维度 | 022 | 018 |
|---|---|---|
| 总节点 | 120 | 146 |
| max depth | 5 | 6 |
| FRAME | 38 | 41 |
| ROUNDED_RECT | 46 | 57 |
| TEXT | 36 | 48 |
| ViewGroup | 25 | 24 |
| ListView | 5 | 5 |
| Button | 4 | 9 |

**一致的模式**：
- 只有 3 种 Figma 类型
- schema:id 系统相同
- ViewGroup/ListView/Button 分类逻辑相同
- 018 多了 ActionBar（替代 022 的 StatusBar）
- 018 有更多 Button（更多可交互控件）

---

## 28. 树构建算法（第 16-17 轮）

### 28.1 空间包含率

95% 的容器完全包含其所有 children（±5px 容差）。仅 2 个容器有溢出 children（侧边栏和内容区的边缘溢出）。

### 28.2 推导的树构建算法

```python
def build_tree(detections):
    containers = [d for d in detections if d.class in CONTAINER_CLASSES]
    leaves = [d for d in detections if d.class in LEAF_CLASSES]
    backgrounds = [d for d in detections if d.class in BACKGROUND_CLASSES]
    
    # Sort containers smallest-first for assignment
    containers.sort(key=lambda c: c.bbox.area)
    
    # Assign each leaf to smallest containing container
    for leaf in leaves + backgrounds:
        for container in containers:
            if container.bbox.contains(leaf.bbox):
                container.children.append(leaf)
                break
    
    # Nest containers (assign each to smallest larger container)
    for i, small in enumerate(containers):
        for large in containers[i+1:]:
            if large.bbox.contains(small.bbox):
                large.children.append(small)
                break
    
    # Sort children: foreground first, Background last
    for container in containers:
        fg = [c for c in container.children if c.name != 'Background']
        bg = [c for c in container.children if c.name == 'Background']
        container.children = fg + bg
    
    return root_container
```

---

## 29. Image 裁剪策略（第 18 轮）

- 每个 ImageView 检测 → 独立裁剪为单独的图片 blob
- 每个 Background(image) 检测 → 独立裁剪
- 裁剪区域 = 检测模型输出的 bbox（绝对坐标）
- 不共享图片、不做 atlas、不用截图作为统一背景
- 尺寸范围：9x17（小指示器）到 610x346（大卡片背景）

---

## 30. 完整 Pipeline 重建（第 19 轮）

```
Screenshot PNG (665x1440)
    │
    ▼
┌─────────────────────────────────┐
│ STEP 1: UI Component Detection  │
│ (object detection model)        │
│ Output: [{class, bbox, conf}]   │
│ 11 classes, absolute coords     │
└─────────────────────────────────┘
    │
    ├──── TextView bboxes ────▶ STEP 2: OCR
    │                          {text, fontSize, fontFamily, color}
    │
    ├──── ImageView bboxes ──▶ STEP 3: Image Crop
    │     Background bboxes    {blob} or {solidColor}
    │
    ▼
┌─────────────────────────────────┐
│ STEP 4: Tree Construction       │
│ Containment-based assignment    │
│ Smallest-container-wins rule    │
│ Background → last child         │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ STEP 5: Coordinate Transform    │
│ Absolute → parent-relative      │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ STEP 6: Figma Serialization     │
│ FRAME / ROUNDED_RECT / TEXT     │
│ schema:id, guid, fixed props    │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ STEP 7: Z-Order + Seq           │
│ Front-to-back children order    │
│ PRE-ORDER DFS reverse traversal │
└─────────────────────────────────┘
    │
    ▼
  canvas.json (Figma Plugin API write)
```

---

## 31. 可实现性评估（第 20 轮）

### 31.1 五个模块

| 模块 | 难度 | 说明 |
|---|---|---|
| UI Component Detector | **极高** | 需要检测不可见容器边界，需要 Android UI 标注数据训练 |
| OCR + Text Props | 中 | 现有 OCR 引擎 + 颜色采样 |
| Image Cropper | 低 | 纯工程，bbox 裁剪 |
| Tree Builder | 中 | 包含分配 + 排序，逻辑清晰 |
| Figma Serializer | 低 | 固定格式输出 |

### 31.2 关键瓶颈

**UI Component Detector 是唯一的硬问题。** 它需要：
- 检测**不可见的容器边界**（ViewGroup 没有视觉边框）
- 区分**语义类型**（Button vs ViewGroup = 有无背景色）
- 检测**重叠层**（content 在 header/footer 后面）
- 训练数据来源：Android View hierarchy dump + 配对截图

### 31.3 与我们当前系统的差距

我们用 xycut（空间分割）替代了 Codia 的 UI Component Detector。这是根本性的方法论差异：
- xycut 假设空间排他分割 → Codia 允许重叠
- xycut 基于间隙几何 → Codia 基于语义分类
- xycut 递归产生深树 → Codia 检测产生浅树
- xycut 不知道容器边界 → Codia 直接检测容器 bbox
