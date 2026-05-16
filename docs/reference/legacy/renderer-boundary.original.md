下面继续输出第七份核心文档：

**`05_Image-to-Figma-Renderer渲染包/01_渲染包职责边界_v0.1.md`**

~~~markdown
# Image-to-Figma Renderer 职责边界 v0.1

文档名称：Image-to-Figma Renderer 职责边界  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 核心渲染包设计文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于明确 Image-to-Figma Renderer 在 v0.1 中的职责边界。

Renderer 是 Figma 插件内的核心渲染包，负责将后端生成的 DSL v0.1 转换成 Figma 可编辑图层。

核心链路如下：

```text
PNG
→ 后端识别
→ DSL v0.1
→ Image-to-Figma Renderer
→ Figma 可编辑设计稿
~~~

Renderer 只处理：

```text
DSL → Figma 图层
```

Renderer 不处理：

```text
PNG → DSL
```

------

## 2. Renderer 的核心定位

Renderer 是一个纯渲染层。

它的输入是：

```text
DSL v0.1
```

它的输出是：

```text
Figma 当前画布中的 Frame / Text / Shape / Image / Icon / Line 图层
```

Renderer 不理解业务，不重新识别图片，不重新调用 AI。

它只做一件事：

```text
按 DSL 描述，在 Figma 中创建对应图层。
```

------

## 3. Renderer 在系统中的位置

整体系统分层如下：

```text
用户上传 PNG
↓
后端 API
↓
图片预处理
↓
OCR / CV / AI 分析
↓
DSL Builder
↓
DSL Validator / Repair
↓
Figma Plugin
↓
Image-to-Figma Renderer
↓
Figma 可编辑设计稿
```

Renderer 位于：

```text
Figma Plugin 内部
```

它依赖：

```text
DSL v0.1
Asset URL
Figma Plugin API
内置 SVG Icon Map
```

它不依赖：

```text
OCR 服务
AI 模型
后端识别算法
图片裁切算法
质量评分系统
```

------

## 4. Renderer 的输入

### 4.1 输入对象

Renderer 接收完整 DSL：

```json
{
  "version": "0.1",
  "taskId": "task_001",
  "page": {},
  "assets": [],
  "root": {},
  "meta": {}
}
```

### 4.2 必须字段

Renderer 必须依赖的字段：

```text
version
page.width
page.height
assets
root
root.type
root.layout
root.children
```

Element 必须字段：

```text
id
type
layout
```

不同类型还需要额外字段：

```text
text  → content.text
image → source.assetId 或 source.url
icon  → source.kind + source.iconName
```

------

## 5. Renderer 的输出

Renderer 输出 Figma 图层。

输出对象包括：

```text
FrameNode
GroupNode 或 FrameNode
TextNode
RectangleNode
Image Paint
SVG / VectorNode
Line / thin Rectangle
```

Renderer 最终应在当前 Figma 页面中生成一个根 Frame：

```text
Generated Screen / page.name
```

该 Frame 内部包含 DSL root.children 对应的所有图层。

------

## 6. Renderer 必须做的事情

### 6.1 版本校验

Renderer 必须检查 DSL 版本。

支持：

```text
0.1
```

不支持时返回错误：

```text
UNSUPPORTED_DSL_VERSION
```

------

### 6.2 基础 DSL 校验

Renderer 需要做轻量校验，避免插件崩溃。

校验内容：

```text
root 是否存在
root.type 是否为 frame
page.width / height 是否有效
assets 是否为数组
element.type 是否支持
layout 是否存在
layout.width / height 是否大于 0
```

注意：

```text
完整 Schema 校验应由后端完成。
Renderer 只做必要防御性校验。
```

------

### 6.3 建立资产索引

Renderer 需要把 assets 转为映射表：

```ts
assetMap: Map<string, Asset>
```

用于 image 元素快速查找：

```json
{
  "source": {
    "assetId": "asset_product_001"
  }
}
```

------

### 6.4 创建 Root Frame

Renderer 必须根据 DSL root 创建 Figma 根 Frame：

```text
name = root.name 或 page.name
x = root.layout.x
y = root.layout.y
width = root.layout.width
height = root.layout.height
fill = root.style.fill 或 page.background
```

------

### 6.5 递归渲染 children

Renderer 必须递归渲染元素树：

```text
root
├─ child
│  ├─ child
│  └─ child
└─ child
```

渲染顺序应遵循 DSL children 顺序：

```text
children 越靠前，图层越靠下
children 越靠后，图层越靠上
```

------

### 6.6 渲染基础元素

Renderer v0.1 必须支持以下元素类型：

```text
frame
group
text
shape
image
icon
line
```

------

### 6.7 应用布局

Renderer 必须应用：

```text
x
y
width
height
```

所有元素均使用绝对定位。

------

### 6.8 应用基础样式

Renderer 必须尽量支持：

```text
fill
color
opacity
visible
radius
stroke
shadow
clipContent
fontFamily
fontSize
fontWeight
lineHeight
textAlign
```

------

### 6.9 加载图片资产

Renderer 需要根据 asset URL 加载图片，并创建 Figma Image Paint。

流程：

```text
source.assetId
→ assetMap 找 URL
→ fetch image
→ figma.createImage(bytes)
→ apply image paint
```

如果图片加载失败，应记录错误，不应导致整页崩溃。

------

### 6.10 渲染内置 SVG 图标

Renderer 需要支持内置图标：

```json
{
  "type": "icon",
  "source": {
    "kind": "builtin_svg",
    "iconName": "search"
  }
}
```

流程：

```text
iconName
→ builtinIcons 查找 SVG
→ figma.createNodeFromSvg
→ resize / position
→ apply color
```

低优先级：如果 SVG 颜色难以替换，v0.1 可先使用默认 SVG 颜色，后续优化。

------

### 6.11 渲染 Original PNG Reference

Renderer 必须支持隐藏原图参考层。

推荐处理：

```text
role = original_reference
visible = false
opacity = 0.5
```

该图层用于用户或开发者在 Figma 中手动对比。

------

### 6.12 渲染 Fallback 区域

Fallback 通常是 image 元素：

```text
type = image
role = fallback_region
meta.fallback = true
```

Renderer 按普通 image 渲染即可。

------

### 6.13 错误收集

Renderer 应记录渲染过程中的错误。

错误内容包括：

```text
elementId
elementType
errorCode
message
assetId
stage
```

例如：

```json
{
  "elementId": "img_001",
  "elementType": "image",
  "errorCode": "ASSET_LOAD_FAILED",
  "message": "Failed to fetch image asset",
  "assetId": "asset_product_001",
  "stage": "renderImage"
}
```

------

## 7. Renderer 不做的事情

### 7.1 不做 OCR

Renderer 不识别文字。

不做：

```text
图片文字检测
OCR 调用
文本纠错
文字 bbox 计算
```

文字必须由 DSL 提供：

```json
{
  "type": "text",
  "content": {
    "text": "首页"
  }
}
```

------

### 7.2 不做 AI 分析

Renderer 不调用大模型。

不做：

```text
页面理解
组件识别
语义判断
布局推理
图标匹配
DSL 修复大模型调用
```

------

### 7.3 不做图片裁切

Renderer 不裁切原图。

不做：

```text
从原 PNG 中裁切商品图
从原 PNG 中裁切头像
从原 PNG 中裁切 fallback 区域
从原 PNG 中裁切状态栏
```

图片裁切由后端完成，并在 DSL assets 中提供 URL。

------

### 7.4 不做 DSL 生成

Renderer 不负责：

```text
根据 PNG 生成 DSL
根据 OCR 生成 DSL
根据 AI 输出组装 DSL
```

Renderer 只消费已经生成好的 DSL。

------

### 7.5 不做业务语义判断

Renderer 不判断：

```text
这是商品
这是订单
这是优惠券
这是课程
这是用户
```

`role` 只用于命名和轻量辅助，不驱动复杂逻辑。

------

### 7.6 不做页面类型判断

Renderer 不判断：

```text
App 页面
小程序页面
网页页面
后台系统页面
```

这些信息可出现在：

```text
meta.platformHint
```

但 Renderer 不依赖它。

------

### 7.7 不做 Auto Layout

Renderer v0.1 不创建 Auto Layout。

不做：

```text
layoutMode
primaryAxisSizingMode
counterAxisSizingMode
itemSpacing
paddingLeft
paddingRight
paddingTop
paddingBottom
```

所有节点按 DSL 的绝对坐标生成。

------

### 7.8 不做 Figma Component

Renderer v0.1 不创建真正 Figma Component / Instance。

不调用：

```text
figma.createComponent
figma.createComponentFromNode
```

所有结构均生成普通 Frame / Group / Node。

------

### 7.9 不做代码生成

Renderer 不生成：

```text
HTML
CSS
React
Vue
小程序代码
Tailwind
```

------

### 7.10 不做质量评分

Renderer 不负责判断生成得像不像。

不做：

```text
视觉相似度评分
文本可编辑率评分
fallback 面积统计
差异热力图
```

质量评估属于内部测试系统，不属于 Renderer v0.1。

------

## 8. Renderer 与 DSL Schema 的关系

Renderer 应依赖 DSL Schema，但不负责完整 Schema 维护。

建议分工：

```text
packages/dsl-schema
→ 定义类型、默认值、校验规则

packages/image-to-figma-renderer
→ 消费 dsl-schema 类型并渲染
```

Renderer 可以复用：

```text
DesignDSL
Element
Asset
Style
Layout
```

但 Renderer 不应该把 Schema 定义散落在渲染文件中。

------

## 9. Renderer 与 Figma Plugin UI 的关系

Figma Plugin UI 负责：

```text
上传 PNG
预览确认
调用后端
显示进度
显示成功 / 失败
```

Renderer 负责：

```text
把 DSL 渲染到 Figma 画布
```

两者关系：

```text
UI 拿到 DSL
↓
发送消息给 plugin main
↓
main 调用 Renderer
↓
Renderer 创建 Figma 图层
↓
main 返回渲染结果给 UI
```

Renderer 不负责 UI 状态管理。

------

## 10. Renderer 与后端的关系

后端输出 DSL 和图片资源。

Renderer 消费：

```text
DSL JSON
assets.url
```

Renderer 不关心后端内部：

```text
OCR 用了什么
模型用了什么
如何裁切图片
如何打分
如何 fallback
```

只要 DSL 合法，Renderer 就按规则渲染。

------

## 11. Renderer 包建议目录

建议独立渲染包目录：

```text
packages/image-to-figma-renderer/
├─ src/
│  ├─ index.ts
│  ├─ renderDesign.ts
│  ├─ renderElement.ts
│  ├─ renderChildren.ts
│  ├─ renderFrame.ts
│  ├─ renderGroup.ts
│  ├─ renderText.ts
│  ├─ renderShape.ts
│  ├─ renderImage.ts
│  ├─ renderIcon.ts
│  ├─ renderLine.ts
│  ├─ renderReference.ts
│  ├─ applyLayout.ts
│  ├─ applyStyle.ts
│  ├─ applyTextStyle.ts
│  ├─ applyEffects.ts
│  ├─ applyGradient.ts
│  ├─ assetResolver.ts
│  ├─ imageLoader.ts
│  ├─ builtinIcons.ts
│  ├─ iconRenderer.ts
│  ├─ figmaPaint.ts
│  ├─ figmaEffects.ts
│  ├─ figmaFonts.ts
│  ├─ errors.ts
│  └─ logger.ts
├─ package.json
├─ tsconfig.json
└─ README.md
```

------

## 12. Renderer 核心文件职责

### 12.1 index.ts

对外导出 Renderer API：

```ts
export { renderDesign } from "./renderDesign"
```

------

### 12.2 renderDesign.ts

主入口。

职责：

```text
接收 DSL
校验版本
建立 assetMap
创建 root frame
递归渲染 children
返回渲染结果
```

------

### 12.3 renderElement.ts

按 element.type 分发：

```text
frame → renderFrame
group → renderGroup
text → renderText
shape → renderShape
image → renderImage
icon → renderIcon
line → renderLine
```

------

### 12.4 renderChildren.ts

递归渲染 children。

职责：

```text
按顺序渲染
捕获单个 child 错误
避免一个元素失败导致整页失败
```

------

### 12.5 applyLayout.ts

应用：

```text
x
y
width
height
```

------

### 12.6 applyStyle.ts

应用通用样式：

```text
fill
opacity
visible
radius
stroke
clipContent
shadow
```

------

### 12.7 assetResolver.ts

根据 assetId 查找资源。

职责：

```text
建立 assetMap
resolveAsset(assetId)
处理 source.url 优先级
```

------

### 12.8 imageLoader.ts

负责加载图片 URL 并转换成 Figma Image。

职责：

```text
fetch url
arrayBuffer
figma.createImage
缓存 image hash
处理加载错误
```

------

### 12.9 builtinIcons.ts

内置 SVG 图标表。

v0.1 只放高频图标：

```text
search
back
close
home
user
cart
category
plus
minus
heart
share
location
setting
arrow_right
check
warning
```

------

### 12.10 errors.ts

定义 Renderer 错误码。

------

## 13. Renderer 错误码

v0.1 建议错误码：

```text
UNSUPPORTED_DSL_VERSION
INVALID_DSL
INVALID_ELEMENT_TYPE
INVALID_LAYOUT
TEXT_CONTENT_MISSING
ASSET_NOT_FOUND
ASSET_LOAD_FAILED
ICON_NOT_FOUND
FONT_LOAD_FAILED
FIGMA_NODE_CREATE_FAILED
STYLE_APPLY_FAILED
UNKNOWN_RENDER_ERROR
```

错误不一定全部导致任务失败。

分级：

```text
fatal：root 无法创建、DSL 版本不支持
element_error：单个元素失败
asset_error：图片资源失败
style_warning：样式应用失败但图层存在
```

------

## 14. Renderer 成功返回结果

Renderer 完成后应返回：

```ts
{
  success: true,
  rootNodeId: string,
  renderedElementCount: number,
  skippedElementCount: number,
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
  "warnings": [
    {
      "elementId": "img_003",
      "code": "ASSET_LOAD_FAILED",
      "message": "Image asset failed to load"
    }
  ]
}
```

------

## 15. Renderer 失败返回结果

如果根级失败：

```ts
{
  success: false,
  errorCode: "UNSUPPORTED_DSL_VERSION",
  message: "DSL version 0.2 is not supported by renderer v0.1"
}
```

根级失败包括：

```text
DSL 版本不支持
root 缺失
page 尺寸无效
Figma 创建 root frame 失败
```

------

## 16. Renderer 性能边界

Renderer 应尽量快。

v0.1 建议边界：

```text
移动端页面节点数：100～300 个以内
复杂页面节点数：不建议超过 500
图片资源数量：不建议超过 30
单次图片并发加载：3～5 个
```

如果 DSL 节点数过多，后端应在生成阶段增加 fallback，而不是让 Renderer 硬扛。

------

## 17. Renderer 的 MVP 取舍

v0.1 Renderer 优先级：

```text
1. 先稳定创建 Figma 图层
2. 再保证文字可编辑
3. 再保证图片正常加载
4. 再保证基础样式接近
5. 最后再优化高级样式
```

不要一开始追求：

```text
完美渐变
完美阴影
复杂 SVG 完美变色
复杂字体完全一致
复杂 clip / mask 完美还原
```

这些都可以后续迭代。

------

## 18. Renderer 不应拖慢主链路

Renderer 不应该因为局部问题卡住整页生成。

原则：

```text
单个元素失败 → 跳过并记录
单个图片失败 → 显示占位或跳过
单个 icon 找不到 → 跳过或 fallback
单个 style 应用失败 → 忽略该 style
root 创建失败 → 整体失败
```

------

## 19. Renderer 与 fallback 的关系

Fallback 由后端决定，Renderer 只负责渲染。

如果元素是：

```text
type = image
role = fallback_region
meta.fallback = true
```

Renderer 按普通图片渲染。

Renderer 不判断这个区域是否应该 fallback。

------

## 20. Renderer 与 original reference 的关系

Original PNG Reference 是 Renderer 必须支持的特殊 role。

处理要求：

```text
创建图片图层
铺满 root frame
默认 hidden
设置 opacity 0.5
命名为 Original PNG Reference
放在 root children 最底部
```

如果 DSL 已经把 original_ref 放在 children 第一项，Renderer 按顺序渲染即可。

------

## 21. Renderer 与字体的关系

Figma 创建 Text 需要加载字体。

Renderer 应：

```text
根据 style.fontFamily / fontWeight 加载字体
如果加载失败，使用默认字体
记录 FONT_LOAD_FAILED warning
```

v0.1 推荐默认字体：

```text
PingFang SC
Inter
Arial
```

中文优先：

```text
PingFang SC
```

------

## 22. Renderer 与图标的关系

v0.1 图标只支持内置 SVG。

如果找不到 iconName：

```text
记录 ICON_NOT_FOUND
跳过该图标
或渲染一个透明占位
```

不在 Renderer 中调用外部图标 API。

------

## 23. Renderer 与图片加载失败的关系

图片加载失败时：

```text
记录 ASSET_LOAD_FAILED
不中断整页渲染
可选创建浅灰占位块
```

v0.1 建议：

```text
开发阶段创建占位块并命名 Missing Image
正式用户阶段可跳过或用占位块
```

------

## 24. Renderer 与坐标的关系

Renderer 直接使用 DSL layout。

不重新计算：

```text
不自动对齐
不自动吸附
不自动排版
不自动居中
```

如果 layout 异常：

```text
width / height <= 0 → 跳过元素
x / y 缺失 → 跳过元素
```

------

## 25. Renderer 与图层命名的关系

Renderer 应优先使用：

```text
element.name
```

如果没有 name，则生成：

```text
{role} / {type} / {id}
```

示例：

```text
Product Card
Search Icon
Text / txt_001
Image / img_001
```

良好的命名可以提高生成稿可用性。

------

## 26. Renderer 与图层顺序的关系

Renderer 按 children 顺序渲染。

规则：

```text
children[0] 最底层
children[n] 最上层
```

后端负责输出正确顺序。

Renderer 不重新推断 z-index。

------

## 27. Renderer 与可见性的关系

如果 style.visible 为 false：

```text
node.visible = false
```

用于：

```text
Original PNG Reference
隐藏参考层
后续调试层
```

------

## 28. Renderer 与 clipContent 的关系

如果元素支持裁切：

```text
node.clipsContent = true
```

适用：

```text
Frame
Image container
Rounded image
Avatar
Banner
```

如果节点类型不支持，则忽略并记录 warning。

------

## 29. Renderer 与日志的关系

Renderer 应提供开发日志接口。

建议日志级别：

```text
debug
info
warn
error
```

v0.1 可以简单实现为：

```ts
console.log
console.warn
console.error
```

后续再接入正式日志系统。

------

## 30. Renderer 验收标准

Renderer v0.1 验收标准：

```text
1. 能接收合法 DSL v0.1
2. 能创建 root frame
3. 能渲染 frame / group
4. 能渲染 text
5. 能渲染 shape
6. 能渲染 image
7. 能渲染 icon
8. 能渲染 line
9. 能应用基本布局
10. 能应用基础样式
11. 能加载图片资产
12. 能插入隐藏原图参考层
13. 单个元素失败不导致整页崩溃
14. 能返回渲染结果和 warning
```

------

## 31. v0.1 结论

Image-to-Figma Renderer v0.1 的职责边界可以总结为：

```text
只负责 DSL → Figma。
不负责 PNG → DSL。
不负责 AI。
不负责 OCR。
不负责质量评分。
不负责代码生成。
不负责组件化。
```

Renderer 的第一版目标是：

```text
简单
稳定
快速
可维护
```

只要 Renderer 能稳定消费 DSL v0.1 并生成 Figma 可编辑图层，就完成了 v0.1 的核心职责。

```
这就是第七份文档：

**`05_Image-to-Figma-Renderer渲染包/01_渲染包职责边界_v0.1.md`**

下一份建议继续输出：

**`05_Image-to-Figma-Renderer渲染包/02_渲染流程_v0.1.md`**
```