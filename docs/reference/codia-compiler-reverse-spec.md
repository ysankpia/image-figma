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
9. **单子节点容器合法**：ViewGroup 可以只包含 1 个 child（提供坐标空间）
10. **从底部向顶部编号**：GlobalSeq 从 BottomNavigation 开始递增到 StatusBar
