下面继续输出第八份核心文档：

**`05_Image-to-Figma-Renderer渲染包/02_渲染流程_v0.1.md`**

~~~markdown
# Image-to-Figma Renderer 渲染流程 v0.1

文档名称：Image-to-Figma Renderer 渲染流程  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 核心渲染流程设计文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于说明 Image-to-Figma Renderer v0.1 的完整渲染流程。

Renderer 的职责是：

```text
DSL v0.1 → Figma 可编辑图层
~~~

Renderer 不负责：

```text
OCR
AI 分析
图片裁切
DSL 生成
质量评分
代码生成
组件化
```

本文档重点说明：

```text
1. Renderer 如何接收 DSL
2. 如何校验 DSL
3. 如何解析 assets
4. 如何创建 Figma 根 Frame
5. 如何递归渲染元素
6. 如何处理 Text / Shape / Image / Icon / Line
7. 如何处理错误和 warning
8. 如何返回渲染结果
```

------

## 2. 渲染总流程

Renderer v0.1 的主流程如下：

```text
接收 DSL
↓
检查 DSL version
↓
基础校验 DSL
↓
补默认值 / Normalize
↓
建立 assetMap
↓
创建 root Frame
↓
递归渲染 root.children
↓
应用 layout / style / content / source
↓
处理 warnings / errors
↓
选中生成结果并定位视图
↓
返回 RenderResult
```

------

## 3. 渲染入口

Renderer 对外暴露一个主入口：

```ts
renderDesign(dsl: DesignDSL, options?: RenderOptions): Promise<RenderResult>
```

示例：

```ts
import { renderDesign } from "@image-to-figma/renderer"

const result = await renderDesign(dsl, {
  selectAfterRender: true,
  scrollIntoView: true,
  createMissingImagePlaceholder: true
})
```

------

## 4. RenderOptions

### 4.1 结构

```ts
export interface RenderOptions {
  selectAfterRender?: boolean
  scrollIntoView?: boolean
  createMissingImagePlaceholder?: boolean
  imageConcurrency?: number
  logger?: RendererLogger
}
```

### 4.2 字段说明

| 字段                            | 类型    | 默认值         | 说明                         |
| ------------------------------- | ------- | -------------- | ---------------------------- |
| `selectAfterRender`             | boolean | `true`         | 渲染完成后是否选中根 Frame   |
| `scrollIntoView`                | boolean | `true`         | 是否将视图定位到生成结果     |
| `createMissingImagePlaceholder` | boolean | `true`         | 图片加载失败时是否创建占位块 |
| `imageConcurrency`              | number  | `3`            | 图片加载并发数               |
| `logger`                        | object  | console logger | 日志对象                     |

------

## 5. RenderResult

### 5.1 成功结果

```ts
export interface RenderSuccessResult {
  success: true
  rootNodeId: string
  renderedElementCount: number
  skippedElementCount: number
  warningCount: number
  warnings: RenderWarning[]
}
```

示例：

```json
{
  "success": true,
  "rootNodeId": "123:456",
  "renderedElementCount": 128,
  "skippedElementCount": 2,
  "warningCount": 3,
  "warnings": [
    {
      "elementId": "img_003",
      "code": "ASSET_LOAD_FAILED",
      "message": "Image asset failed to load"
    }
  ]
}
```

### 5.2 失败结果

```ts
export interface RenderFailedResult {
  success: false
  errorCode: string
  message: string
  warnings?: RenderWarning[]
}
```

示例：

```json
{
  "success": false,
  "errorCode": "UNSUPPORTED_DSL_VERSION",
  "message": "DSL version 0.2 is not supported by renderer v0.1"
}
```

------

## 6. 渲染主入口伪代码

```ts
export async function renderDesign(
  dsl: DesignDSL,
  options: RenderOptions = {}
): Promise<RenderResult> {
  const ctx = createRenderContext(dsl, options)

  try {
    validateVersion(dsl)
    validateRoot(dsl)
    normalizeDSL(dsl)

    ctx.assetMap = buildAssetMap(dsl.assets)

    const rootFrame = await renderRootFrame(dsl.root, dsl, ctx)

    await renderChildren(rootFrame, dsl.root.children ?? [], ctx)

    if (options.selectAfterRender !== false) {
      figma.currentPage.selection = [rootFrame]
    }

    if (options.scrollIntoView !== false) {
      figma.viewport.scrollAndZoomIntoView([rootFrame])
    }

    return {
      success: true,
      rootNodeId: rootFrame.id,
      renderedElementCount: ctx.renderedElementCount,
      skippedElementCount: ctx.skippedElementCount,
      warningCount: ctx.warnings.length,
      warnings: ctx.warnings
    }
  } catch (error) {
    return {
      success: false,
      errorCode: getErrorCode(error),
      message: getErrorMessage(error),
      warnings: ctx.warnings
    }
  }
}
```

------

## 7. RenderContext

### 7.1 结构

Renderer 内部需要一个上下文对象：

```ts
export interface RenderContext {
  dsl: DesignDSL
  options: RenderOptions
  assetMap: Map<string, DSLAsset>
  imageCache: Map<string, ImageHash>
  warnings: RenderWarning[]
  renderedElementCount: number
  skippedElementCount: number
  logger: RendererLogger
}
```

### 7.2 用途

RenderContext 用于在递归渲染过程中共享：

```text
assets 映射
图片缓存
warnings
计数器
logger
options
```

------

## 8. 第一步：检查 DSL version

### 8.1 规则

Renderer v0.1 只支持：

```text
version = "0.1"
```

### 8.2 伪代码

```ts
function validateVersion(dsl: DesignDSL) {
  if (dsl.version !== "0.1") {
    throw new RendererError(
      "UNSUPPORTED_DSL_VERSION",
      `DSL version ${dsl.version} is not supported`
    )
  }
}
```

### 8.3 错误

如果版本不支持，属于 fatal error，停止渲染。

------

## 9. 第二步：基础校验 DSL

Renderer 端只做轻量防御性校验。

完整 Schema 校验应由后端完成。

### 9.1 必须校验

```text
dsl 是否存在
dsl.page 是否存在
dsl.page.width / height 是否大于 0
dsl.root 是否存在
dsl.root.type 是否为 frame
dsl.root.layout 是否存在
dsl.assets 是否为数组
```

### 9.2 伪代码

```ts
function validateRoot(dsl: DesignDSL) {
  if (!dsl.page || dsl.page.width <= 0 || dsl.page.height <= 0) {
    throw new RendererError("INVALID_PAGE", "Invalid page size")
  }

  if (!dsl.root) {
    throw new RendererError("ROOT_MISSING", "DSL root is missing")
  }

  if (dsl.root.type !== "frame") {
    throw new RendererError("INVALID_ROOT_TYPE", "Root must be frame")
  }

  if (!isValidLayout(dsl.root.layout)) {
    throw new RendererError("INVALID_ROOT_LAYOUT", "Invalid root layout")
  }
}
```

------

## 10. 第三步：Normalize / 补默认值

Renderer 可做轻量默认值补全。

### 10.1 默认值

```text
role → unknown
name → 根据 type / role / id 自动生成
style → {}
children → []
meta → {}
opacity → 1
visible → true
clipContent → false
```

### 10.2 注意

Renderer 只做轻量补全，不做复杂修复。

不做：

```text
重新推断布局
重新归组元素
重新生成 DSL
重新调用 AI
```

------

## 11. 第四步：建立 assetMap

### 11.1 输入

```json
{
  "assets": [
    {
      "assetId": "asset_product_001",
      "url": "http://localhost:8000/files/assets/product_001.jpg"
    }
  ]
}
```

### 11.2 输出

```ts
Map<string, DSLAsset>
```

### 11.3 伪代码

```ts
function buildAssetMap(assets: DSLAsset[]): Map<string, DSLAsset> {
  const map = new Map<string, DSLAsset>()

  for (const asset of assets ?? []) {
    if (!asset.assetId) continue
    map.set(asset.assetId, asset)
  }

  return map
}
```

### 11.4 规则

如果重复 assetId：

```text
后出现的覆盖前一个
记录 DUPLICATE_ASSET_ID warning
```

------

## 12. 第五步：创建 Root Frame

### 12.1 Root Frame 来源

Root Frame 来自：

```json
{
  "root": {
    "type": "frame",
    "layout": {
      "x": 0,
      "y": 0,
      "width": 390,
      "height": 844
    },
    "style": {
      "fill": "#F7F8FA"
    }
  }
}
```

### 12.2 创建规则

```ts
const rootFrame = figma.createFrame()
rootFrame.name = root.name ?? dsl.page.name ?? "Generated Screen"
rootFrame.x = root.layout.x
rootFrame.y = root.layout.y
rootFrame.resize(root.layout.width, root.layout.height)
applyStyle(rootFrame, root.style, ctx)
```

### 12.3 root fill

优先级：

```text
root.style.fill
page.background
默认 #FFFFFF
```

------

## 13. 第六步：递归渲染 children

### 13.1 规则

children 顺序即图层顺序。

```text
children[0] 最底层
children[n] 最上层
```

Renderer 不重新推断 z-index。

### 13.2 伪代码

```ts
async function renderChildren(
  parent: BaseNode & ChildrenMixin,
  children: DSLElement[],
  ctx: RenderContext
) {
  for (const child of children) {
    try {
      const node = await renderElement(child, ctx)

      if (node) {
        parent.appendChild(node)
        ctx.renderedElementCount += 1
      }
    } catch (error) {
      ctx.skippedElementCount += 1
      ctx.warnings.push(toRenderWarning(error, child))
      ctx.logger.warn("Render child failed", child.id, error)
    }
  }
}
```

### 13.3 重要原则

单个 child 渲染失败，不能导致整页失败。

除非失败的是 root。

------

## 14. 第七步：按 type 分发渲染

### 14.1 分发规则

```ts
async function renderElement(element: DSLElement, ctx: RenderContext) {
  switch (element.type) {
    case "frame":
      return renderFrame(element, ctx)
    case "group":
      return renderGroup(element, ctx)
    case "text":
      return renderText(element, ctx)
    case "shape":
      return renderShape(element, ctx)
    case "image":
      return renderImage(element, ctx)
    case "icon":
      return renderIcon(element, ctx)
    case "line":
      return renderLine(element, ctx)
    default:
      throw new RendererError("INVALID_ELEMENT_TYPE", element.type)
  }
}
```

### 14.2 不支持类型

如果出现不支持的 type：

```text
记录 INVALID_ELEMENT_TYPE
跳过该元素
不中断整页
```

------

## 15. Frame 渲染流程

### 15.1 输入示例

```json
{
  "id": "card_001",
  "type": "frame",
  "role": "card",
  "name": "Product Card",
  "layout": {
    "x": 16,
    "y": 352,
    "width": 358,
    "height": 112
  },
  "style": {
    "fill": "#FFFFFF",
    "radius": 12
  },
  "children": []
}
```

### 15.2 渲染流程

```text
createFrame
apply name
apply layout
apply style
render children
return node
```

### 15.3 伪代码

```ts
async function renderFrame(element: DSLElement, ctx: RenderContext) {
  const node = figma.createFrame()

  applyName(node, element)
  applyLayout(node, element.layout)
  applyStyle(node, element.style, ctx)

  await renderChildren(node, element.children ?? [], ctx)

  return node
}
```

------

## 16. Group 渲染流程

### 16.1 v0.1 建议

Figma Group 对动态创建和样式处理不如 Frame 灵活。

v0.1 可以把 `group` 也渲染成 Frame。

```text
type = group → figma.createFrame()
```

### 16.2 规则

Group 渲染成无填充 Frame：

```text
fill = transparent / no fill
clipsContent = false
```

------

## 17. Text 渲染流程

### 17.1 输入示例

```json
{
  "id": "title_001",
  "type": "text",
  "content": {
    "text": "首页"
  },
  "layout": {
    "x": 160,
    "y": 55,
    "width": 70,
    "height": 22
  },
  "style": {
    "fontFamily": "PingFang SC",
    "fontSize": 17,
    "fontWeight": 600,
    "lineHeight": 22,
    "color": "#111111",
    "textAlign": "center"
  }
}
```

### 17.2 渲染流程

```text
校验 content.text
加载字体
createText
设置 characters
apply layout
apply text style
return node
```

### 17.3 伪代码

```ts
async function renderText(element: DSLElement, ctx: RenderContext) {
  const text = element.content?.text

  if (typeof text !== "string") {
    throw new RendererError("TEXT_CONTENT_MISSING", "Text content missing")
  }

  const node = figma.createText()

  applyName(node, element)

  await loadFontForText(element.style, ctx)

  node.characters = text

  applyLayout(node, element.layout)
  applyTextStyle(node, element.style, ctx)
  applyVisibility(node, element.style)

  return node
}
```

### 17.4 字体加载失败

如果字体加载失败：

```text
使用默认字体
记录 FONT_LOAD_FAILED warning
继续渲染
```

默认字体建议：

```text
PingFang SC
Inter
Arial
```

------

## 18. Shape 渲染流程

### 18.1 输入示例

```json
{
  "id": "button_bg_001",
  "type": "shape",
  "role": "button_background",
  "layout": {
    "x": 24,
    "y": 720,
    "width": 342,
    "height": 48
  },
  "style": {
    "fill": "#FF4D4F",
    "radius": 24
  }
}
```

### 18.2 渲染流程

```text
createRectangle
apply name
apply layout
apply style
return node
```

### 18.3 圆形头像 / 圆形 shape

v0.1 统一用 Rectangle + cornerRadius。

如果 radius = 999：

```text
cornerRadius = min(width, height) / 2
```

------

## 19. Image 渲染流程

### 19.1 输入示例

```json
{
  "id": "product_img_001",
  "type": "image",
  "source": {
    "assetId": "asset_product_001"
  },
  "layout": {
    "x": 28,
    "y": 360,
    "width": 96,
    "height": 96
  },
  "style": {
    "radius": 8,
    "clipContent": true
  },
  "imageFill": {
    "mode": "fit"
  }
}
```

### 19.2 渲染流程

```text
resolve asset
fetch image bytes
figma.createImage
createRectangle
apply layout
apply radius
apply ImagePaint
return node
```

### 19.3 伪代码

```ts
async function renderImage(element: DSLElement, ctx: RenderContext) {
  const asset = resolveAsset(element.source, ctx)

  if (!asset?.url) {
    return renderMissingImagePlaceholder(element, ctx, "ASSET_NOT_FOUND")
  }

  try {
    const imageHash = await loadFigmaImage(asset.url, ctx)

    const node = figma.createRectangle()
    applyName(node, element)
    applyLayout(node, element.layout)
    applyStyle(node, element.style, ctx)

    node.fills = [
      {
        type: "IMAGE",
        scaleMode: toFigmaScaleMode(element.imageFill?.mode),
        imageHash
      }
    ]

    return node
  } catch (error) {
    return renderMissingImagePlaceholder(element, ctx, "ASSET_LOAD_FAILED")
  }
}
```

### 19.4 imageFill.mode 对应

| DSL    | Figma scaleMode |
| ------ | --------------- |
| `fill` | `FILL`          |
| `fit`  | `FIT`           |

------

## 20. Icon 渲染流程

### 20.1 输入示例

```json
{
  "id": "search_icon",
  "type": "icon",
  "source": {
    "kind": "builtin_svg",
    "iconName": "search"
  },
  "layout": {
    "x": 32,
    "y": 112,
    "width": 16,
    "height": 16
  },
  "style": {
    "color": "#999999"
  }
}
```

### 20.2 渲染流程

```text
读取 iconName
查找 builtinIcons
createNodeFromSvg
resize
position
apply color
return node
```

### 20.3 伪代码

```ts
function renderIcon(element: DSLElement, ctx: RenderContext) {
  const iconName = element.source?.iconName
  const svg = builtinIcons[iconName]

  if (!svg) {
    throw new RendererError("ICON_NOT_FOUND", iconName)
  }

  const node = figma.createNodeFromSvg(svg)

  applyName(node, element)
  applyLayout(node, element.layout)
  applyIconColor(node, element.style?.color)

  return node
}
```

### 20.4 注意

v0.1 如果 SVG 改色复杂，可以先使用内置 SVG 自带颜色。

后续再优化 SVG fill / stroke 替换。

------

## 21. Line 渲染流程

### 21.1 输入示例

```json
{
  "id": "divider_001",
  "type": "line",
  "layout": {
    "x": 16,
    "y": 200,
    "width": 358,
    "height": 0.5
  },
  "style": {
    "fill": "#EEEEEE"
  }
}
```

### 21.2 v0.1 渲染方式

建议用 Rectangle 渲染 line。

```text
createRectangle
width = layout.width
height = max(layout.height, 0.5)
fill = style.fill
```

这样比 Figma LineNode 更容易控制 0.5px。

------

## 22. Original Reference 渲染流程

### 22.1 判断方式

```text
role = original_reference
```

### 22.2 渲染方式

本质还是 image。

特殊处理：

```text
name = Original PNG Reference
visible = false
opacity = 0.5
放在 root children 最底部
```

如果 DSL 已经把它放在 children 第一项，Renderer 不需要重新排序。

------

## 23. Fallback 渲染流程

### 23.1 判断方式

```text
role = fallback_region
meta.fallback = true
```

### 23.2 渲染方式

本质还是 image。

Renderer 不判断是否应该 fallback，只按 DSL 渲染。

------

## 24. applyLayout 流程

### 24.1 输入

```json
{
  "x": 24,
  "y": 88,
  "width": 342,
  "height": 48
}
```

### 24.2 伪代码

```ts
function applyLayout(node: SceneNode, layout: Layout) {
  if (!isValidLayout(layout)) {
    throw new RendererError("INVALID_LAYOUT", "Invalid layout")
  }

  node.x = layout.x
  node.y = layout.y

  if ("resize" in node) {
    node.resize(layout.width, layout.height)
  }
}
```

### 24.3 规则

```text
width / height 必须大于 0
x / y 必须为 number
允许 0.5px
不自动对齐
不自动居中
```

------

## 25. applyStyle 流程

### 25.1 支持字段

```text
fill
opacity
visible
radius
stroke
shadow
clipContent
```

### 25.2 处理顺序

```text
visible
opacity
fill
radius
stroke
shadow
clipContent
```

### 25.3 异常处理

单个 style 应用失败：

```text
记录 STYLE_APPLY_FAILED warning
继续渲染元素
```

------

## 26. applyTextStyle 流程

### 26.1 支持字段

```text
fontFamily
fontSize
fontWeight
lineHeight
color
textAlign
```

### 26.2 字号

```ts
node.fontSize = style.fontSize ?? 14
```

### 26.3 行高

如果提供 lineHeight：

```ts
node.lineHeight = {
  unit: "PIXELS",
  value: style.lineHeight
}
```

否则使用 Figma 默认。

### 26.4 对齐

```text
left → LEFT
center → CENTER
right → RIGHT
```

------

## 27. applyEffects 流程

### 27.1 支持 shadow

```json
{
  "shadow": [
    {
      "type": "drop_shadow",
      "x": 0,
      "y": 4,
      "blur": 12,
      "spread": 0,
      "color": "rgba(0,0,0,0.08)"
    }
  ]
}
```

### 27.2 v0.1 规则

只支持：

```text
drop_shadow
```

复杂多层阴影可支持 1～2 层，过多可截断。

建议最多：

```text
2 层 shadow
```

------

## 28. applyGradient 流程

### 28.1 支持范围

v0.1 支持简单线性渐变。

```json
{
  "fill": {
    "type": "linear_gradient",
    "angle": 90,
    "stops": [
      {
        "color": "#FF6A00",
        "position": 0
      },
      {
        "color": "#FF3D3D",
        "position": 1
      }
    ]
  }
}
```

### 28.2 复杂渐变

复杂渐变建议后端 fallback 为图片，Renderer 不做复杂推断。

------

## 29. 图片加载与缓存

### 29.1 目标

同一个 assetId 不应重复 fetch。

### 29.2 imageCache

```ts
Map<string, ImageHash>
```

key 建议：

```text
assetId 或 url
```

### 29.3 伪代码

```ts
async function loadFigmaImage(url: string, ctx: RenderContext) {
  if (ctx.imageCache.has(url)) {
    return ctx.imageCache.get(url)
  }

  const response = await fetch(url)
  const bytes = new Uint8Array(await response.arrayBuffer())
  const image = figma.createImage(bytes)

  ctx.imageCache.set(url, image.hash)

  return image.hash
}
```

------

## 30. 图片并发控制

v0.1 建议图片加载并发：

```text
3～5
```

原因：

```text
避免大量图片同时 fetch
避免插件卡顿
避免 Figma 插件环境不稳定
```

第一版如果实现并发控制成本较高，可以先串行加载，后续再优化。

------

## 31. Missing Image Placeholder

### 31.1 触发场景

```text
assetId 找不到
asset.url 缺失
fetch 图片失败
figma.createImage 失败
```

### 31.2 开发阶段建议

创建浅灰色占位块：

```text
fill = #F2F2F2
stroke = #FF4D4F
name = Missing Image / {element.id}
```

### 31.3 正式阶段建议

可以跳过或创建更轻量占位。

v0.1 建议先创建占位，方便调试。

------

## 32. 字体加载策略

### 32.1 字体来源

Text 元素可能提供：

```text
fontFamily
fontWeight
```

### 32.2 加载策略

```text
优先加载 DSL 指定字体
失败后加载默认字体
仍失败则记录 FONT_LOAD_FAILED
```

### 32.3 默认字体

```text
中文：PingFang SC
英文：Inter / Arial
```

### 32.4 注意

Figma 插件中必须先 loadFontAsync，才能设置 characters。

------

## 33. 错误处理原则

### 33.1 fatal error

以下错误会导致整体失败：

```text
DSL version 不支持
page 缺失或尺寸无效
root 缺失
root layout 无效
root frame 创建失败
```

### 33.2 element error

以下错误只跳过当前元素：

```text
不支持的 element.type
layout 无效
text content 缺失
asset 找不到
icon 找不到
style 应用失败
```

### 33.3 warning

以下情况记录 warning，但继续：

```text
字体加载失败
图片加载失败并创建占位
style 某字段无法应用
重复 assetId
未知 role
```

------

## 34. RenderWarning 结构

```ts
export interface RenderWarning {
  elementId?: string
  elementType?: string
  code: string
  message: string
  stage?: string
  assetId?: string
}
```

示例：

```json
{
  "elementId": "img_001",
  "elementType": "image",
  "code": "ASSET_LOAD_FAILED",
  "message": "Failed to load image asset",
  "stage": "renderImage",
  "assetId": "asset_product_001"
}
```

------

## 35. 渲染完成后的处理

渲染完成后：

```text
选中 root Frame
滚动视图到 root Frame
返回 RenderResult
通知插件 UI 生成完成
```

### 35.1 伪代码

```ts
figma.currentPage.selection = [rootFrame]
figma.viewport.scrollAndZoomIntoView([rootFrame])
```

------

## 36. 渲染流程中的日志

### 36.1 建议日志

```text
start render
validate version
build asset map
create root frame
render element count
warning count
finish render
```

### 36.2 开发阶段

开发阶段可以使用：

```ts
console.log
console.warn
console.error
```

正式阶段再接入统一日志。

------

## 37. Renderer 文件拆分建议

```text
renderDesign.ts        主入口
renderElement.ts       元素分发
renderChildren.ts      子元素递归
renderFrame.ts         Frame 渲染
renderGroup.ts         Group 渲染
renderText.ts          Text 渲染
renderShape.ts         Shape 渲染
renderImage.ts         Image 渲染
renderIcon.ts          Icon 渲染
renderLine.ts          Line 渲染
applyLayout.ts         布局应用
applyStyle.ts          通用样式
applyTextStyle.ts      文本样式
applyEffects.ts        阴影等效果
applyGradient.ts       渐变
assetResolver.ts       资源解析
imageLoader.ts         图片加载
figmaFonts.ts          字体加载
errors.ts              错误定义
logger.ts              日志
```

------

## 38. 最小实现优先级

### P0 必须实现

```text
renderDesign
renderElement
renderFrame
renderText
renderShape
renderImage
applyLayout
applyStyle
assetResolver
imageLoader
```

### P1 尽快实现

```text
renderIcon
renderLine
renderReference
applyTextStyle
figmaFonts
errors
logger
```

### P2 后续增强

```text
applyGradient
applyEffects
图片并发加载
SVG 精细改色
Missing Image 占位优化
```

------

## 39. MVP 渲染成功标准

Renderer v0.1 渲染成功应满足：

```text
1. 合法 DSL 能创建 root Frame
2. 能递归渲染 children
3. 能显示文本
4. 能显示图片
5. 能显示 shape
6. 能显示基础 icon
7. 能显示分割线
8. 能应用基础颜色、圆角、透明度
9. 能加载隐藏原图参考层
10. 单个元素失败不影响整页
11. 返回 warning 信息
```

------

## 40. 版本结论

Renderer v0.1 的渲染流程必须保持简单：

```text
校验 DSL
建立 assetMap
创建 root
递归渲染元素
应用布局和样式
返回结果
```

v0.1 不追求完美渲染所有复杂视觉效果。

核心目标是：

```text
稳定把 DSL v0.1 转成 Figma 可编辑图层。
```

第一版只要能稳定支撑：

```text
PNG → DSL → Figma 可编辑稿
```

就完成 Renderer 的主要任务。

```
这就是第八份文档：

**`05_Image-to-Figma-Renderer渲染包/02_渲染流程_v0.1.md`**

下一份建议继续输出：

**`04_技术架构文档/01_整体技术架构_v0.1.md`**
```