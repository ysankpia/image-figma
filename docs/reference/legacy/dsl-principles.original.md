下面继续输出第四份核心文档：

**`03_DSL规范/01_DSL_v0.1_设计原则.md`**

~~~markdown
# DSL v0.1 设计原则

文档名称：DSL v0.1 设计原则  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 核心协议设计文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于定义 Image-to-Figma Design 项目中 DSL v0.1 的设计原则。

DSL 是后端识别系统和 Figma 渲染器之间的数据协议。

后端负责：

```text
PNG → OCR / AI / CV → DSL v0.1
~~~

Figma 插件负责：

```text
DSL v0.1 → Figma 可编辑图层
```

DSL v0.1 的目标不是成为最终通用设计标准，而是服务第一版 MVP：

```text
快速、稳定地把 PNG 转成 Figma 可编辑设计稿
```

------

## 2. DSL v0.1 的核心定位

DSL v0.1 是一个中间表达层。

它不等于：

```text
Figma 文件格式
HTML / CSS
前端代码
设计系统规范
组件库协议
业务数据协议
```

它只表达：

```text
一个从 PNG 截图中识别出来的 UI 页面，应该如何在 Figma 中被重建。
```

DSL v0.1 的核心作用：

```text
1. 表达页面尺寸
2. 表达图层树
3. 表达元素类型
4. 表达布局坐标
5. 表达基础样式
6. 表达文本内容
7. 表达图片资源
8. 表达图标资源
9. 表达 fallback 区域
10. 表达必要调试信息
```

------

## 3. 第一原则：服务渲染，不服务完美建模

DSL v0.1 的第一原则是：

```text
优先服务 Figma 渲染成功，而不是追求完美语义建模。
```

因此，DSL v0.1 不追求：

```text
完整业务语义
完整组件体系
完整设计系统
完整代码生成能力
完整 Auto Layout 结构
```

它只需要让 Renderer 能稳定生成：

```text
Frame
Group
Text
Shape
Image
Icon
Line
```

例如，一个按钮不需要在 v0.1 中成为独立 `button` 类型。

推荐：

```json
{
  "type": "frame",
  "role": "button",
  "children": [
    {
      "type": "shape",
      "role": "button_background"
    },
    {
      "type": "text",
      "role": "button_label"
    }
  ]
}
```

不推荐：

```json
{
  "type": "button",
  "variant": "primary"
}
```

原因：

```text
Renderer 处理 frame + shape + text 更简单、更稳定。
button 语义可以通过 role / meta 保留，后续再升级。
```

------

## 4. 第二原则：类型少，role 多

DSL v0.1 中，`type` 必须少。

一期只允许以下基础类型：

```text
frame
group
text
shape
image
icon
line
```

复杂 UI 结构通过 `role` 表示。

例如：

```text
button
card
search_bar
tab_bar
tab_item
navigation_bar
form_item
modal
list
list_item
```

都不作为 `type`，只作为 `role`。

示例：

```json
{
  "id": "card_001",
  "type": "frame",
  "role": "card",
  "name": "Product Card"
}
```

这样做的好处：

```text
1. Renderer 逻辑简单
2. DSL 校验简单
3. 不会过早绑定复杂组件语义
4. 后续可以逐步扩展
5. 降低模型输出错误概率
```

------

## 5. 第三原则：绝对定位优先

DSL v0.1 统一使用绝对定位。

基础布局字段：

```json
{
  "layout": {
    "x": 24,
    "y": 88,
    "width": 342,
    "height": 48
  }
}
```

一期不做：

```text
Auto Layout
Constraints
Responsive Layout
Hug Content
Fill Container
Flex Layout
Grid Layout
```

原因：

```text
输入是 PNG，系统无法稳定判断设计师真实布局意图。
绝对定位更适合截图还原，稳定性最高。
```

后续版本可以在高置信度区域增加：

```text
autoLayoutHint
constraintsHint
responsiveHint
```

但 v0.1 不作为渲染主逻辑。

------

## 6. 第四原则：视觉还原优先于结构完美

DSL v0.1 的目标是让 Figma 生成结果看起来接近原图。

因此，在可编辑性和视觉还原冲突时，v0.1 优先保证视觉结果不崩。

处理原则：

```text
主要内容 → 尽量可编辑
复杂区域 → 图片 fallback
局部失败 → fallback，不影响整页
```

例如复杂 Banner：

```text
如果拆成 shape / text / image 风险很高，
则直接裁切为 fallback 图片块。
```

示例：

```json
{
  "id": "fallback_banner_001",
  "type": "image",
  "role": "fallback_region",
  "layout": {
    "x": 16,
    "y": 120,
    "width": 358,
    "height": 140
  },
  "source": {
    "assetId": "asset_fallback_banner_001"
  },
  "meta": {
    "fallback": true,
    "reason": "complex_banner"
  }
}
```

------

## 7. 第五原则：复杂内容允许 fallback

DSL v0.1 必须原生支持 fallback。

Fallback 不是失败，而是 MVP 质量策略的一部分。

以下内容允许 fallback：

```text
复杂 Banner
复杂插图
复杂运营图
复杂光效
复杂渐变背景
复杂图表
复杂多色图标
复杂不规则 Mask
识别置信度低的局部区域
```

Fallback 的目标：

```text
避免整页失败
保证视觉完整
保留后续优化空间
```

Fallback 必须记录原因：

```json
{
  "meta": {
    "fallback": true,
    "reason": "complex_chart",
    "confidence": 0.52
  }
}
```

------

## 8. 第六原则：DSL 必须可校验

DSL v0.1 必须有 Schema 校验。

每份 DSL 至少校验：

```text
version 是否存在
taskId 是否存在
page 是否存在
assets 是否为数组
root 是否存在
element id 是否唯一
element type 是否合法
layout 是否合法
children 是否引用有效
image assetId 是否存在
text content 是否存在
style 字段类型是否正确
```

不允许未校验的 DSL 直接进入 Renderer。

推荐流程：

```text
后端生成 DSL
↓
DSL Normalize
↓
DSL Validate
↓
DSL Repair
↓
再次 Validate
↓
返回插件
```

Renderer 端也应做轻量校验，避免异常 DSL 导致 Figma 插件崩溃。

------

## 9. 第七原则：DSL 必须可修复

DSL v0.1 允许做基础修复。

基础修复包括：

```text
缺 name → 自动补
缺 role → unknown
缺 style → {}
缺 children → []
缺 opacity → 1
缺 visible → true
坐标小数 → 归一
width / height 小于等于 0 → 修正或剔除
children 引用不存在 → 移除引用
asset 缺失 → fallback 或报错
```

修复不应改变核心识别结果。

修复目标是：

```text
避免小格式问题导致整页失败。
```

不做复杂修复：

```text
不重新理解页面
不重新生成整体布局
不多轮 AI 修复
不自动重新排版
```

------

## 10. 第八原则：字段命名稳定

DSL v0.1 字段命名必须稳定、明确、易读。

推荐使用：

```text
camelCase
```

例如：

```text
taskId
scaleFactor
viewportHeight
isScrollable
clipContent
fontSize
fontWeight
lineHeight
textAlign
assetId
```

不使用：

```text
task_id
scale_factor
viewport_height
font-size
font_weight
```

原因：

```text
Figma 插件和 TypeScript Renderer 更适合 camelCase。
```

------

## 11. 第九原则：style 不承载业务语义

`style` 只表达视觉样式。

style 可以包含：

```text
fill
opacity
radius
stroke
shadow
gradient
clipContent
visible
fontSize
fontWeight
lineHeight
color
textAlign
```

style 不应该包含：

```text
isProduct
isOrder
isUser
isVip
businessType
pageType
```

业务 / 语义信息放在：

```text
role
meta
semanticType
```

示例：

```json
{
  "type": "text",
  "role": "price_text",
  "style": {
    "fontSize": 18,
    "fontWeight": 700,
    "color": "#FF3D3D"
  },
  "meta": {
    "semanticType": "price"
  }
}
```

------

## 12. 第十原则：meta 只放辅助信息

`meta` 用于放辅助信息，不应该成为渲染主依赖。

meta 可以包含：

```text
confidence
fallback
reason
ocrConfidence
semanticType
componentSpec
sourceBBox
qualityFlags
```

Renderer 可以读取 meta，但不应该依赖 meta 才能完成基础渲染。

例如：

```json
{
  "meta": {
    "confidence": 0.88,
    "componentSpec": {
      "kind": "Button",
      "variant": "primary"
    }
  }
}
```

Renderer 应主要依赖：

```text
type
layout
style
content
source
children
```

而不是依赖：

```text
meta.componentSpec
```

------

## 13. 第十一原则：assets 独立管理

图片资产必须独立于元素树管理。

DSL 顶层包含：

```json
{
  "assets": []
}
```

元素通过 `assetId` 引用资源。

推荐：

```json
{
  "assets": [
    {
      "assetId": "asset_product_001",
      "type": "image",
      "url": "http://localhost:8000/files/assets/product_001.jpg",
      "format": "jpeg",
      "width": 96,
      "height": 96
    }
  ]
}
```

元素中引用：

```json
{
  "type": "image",
  "source": {
    "assetId": "asset_product_001"
  }
}
```

这样做的好处：

```text
1. 资产可复用
2. 资产可追踪
3. 后续可替换 URL
4. 后续可迁移 OSS
5. DSL 结构更清晰
```

------

## 14. 第十二原则：开发阶段本地 URL，生产阶段签名 URL

v0.1 开发阶段允许使用本地文件 URL。

例如：

```json
{
  "url": "http://localhost:8000/files/assets/product_001.jpg",
  "storage": "local"
}
```

生产阶段再使用 OSS / 对象存储：

```json
{
  "url": "https://oss.example.com/tasks/task_001/assets/product_001.jpg?signature=xxx",
  "storage": "oss",
  "expiresAt": "2026-05-16T12:00:00Z"
}
```

但 DSL 字段必须预留：

```text
assetId
objectKey
url
storage
expiresAt
```

以便后续迁移。

------

## 15. 第十三原则：原图参考层必须保留

每份 DSL 都应包含原 PNG 参考层。

该层默认：

```text
visible: false
opacity: 0.5
role: original_reference
```

作用：

```text
方便用户在 Figma 画布中手动对比
方便开发阶段调试视觉偏差
避免插件内做复杂对比 UI
```

示例：

```json
{
  "id": "original_ref",
  "type": "image",
  "role": "original_reference",
  "name": "Original PNG Reference",
  "layout": {
    "x": 0,
    "y": 0,
    "width": 390,
    "height": 844
  },
  "source": {
    "assetId": "asset_original"
  },
  "style": {
    "visible": false,
    "opacity": 0.5
  }
}
```

------

## 16. 第十四原则：层级不能过深

DSL v0.1 图层树应控制层级深度。

建议：

```text
3～4 层以内
```

推荐结构：

```text
Screen
├─ Original PNG Reference
├─ Header
├─ Content
│  ├─ Search Bar
│  └─ Card
└─ TabBar
```

避免：

```text
Screen / Content / List / ListItem / Card / TextGroup / TitleGroup / Title
```

原因：

```text
层级过深会影响 Figma 使用体验，也会增加 Renderer 复杂度。
```

------

## 17. 第十五原则：节点数量要控制

DSL v0.1 不应为了“全可编辑”生成过多节点。

建议单个移动端页面：

```text
100～300 个节点以内
```

如果复杂区域会导致大量节点，应 fallback。

例如：

```text
复杂插图不拆
复杂 Banner 不拆
复杂图表不拆
复杂光效不拆
```

原因：

```text
Figma 创建大量节点会变慢。
用户也不希望看到过多碎图层。
```

------

## 18. 第十六原则：不在 DSL v0.1 中设计代码生成字段

v0.1 不服务代码生成。

不加入：

```text
htmlTag
cssClass
reactComponent
vueComponent
tailwindClass
responsiveRules
```

原因：

```text
第一版只做 PNG → Figma。
代码生成会污染 DSL v0.1 的设计目标。
```

后续如果需要代码生成，可以在 DSL v0.2 / v0.3 中新增专门的 codeHints。

------

## 19. 第十七原则：不在 DSL v0.1 中绑定 Figma Component

v0.1 不生成真正 Figma Component / Instance。

DSL 可以保留：

```json
{
  "meta": {
    "componentSpec": {
      "kind": "Button",
      "variant": "primary",
      "confidence": 0.88
    }
  }
}
```

但 Renderer 不应自动调用：

```text
createComponent
createComponentFromNode
```

原因：

```text
PNG 输入无法稳定判断组件复用关系。
错误组件化会影响用户编辑。
```

后续可通过“一键组件化”功能处理。

------

## 20. 第十八原则：不做行业业务语义

v0.1 不做深度行业语义识别。

不强制判断：

```text
商品
订单
用户
课程
文章
优惠券
生鲜
外卖
教育
社交
```

可以保留少量基础 semanticType：

```text
price
phone
date
order_number
percentage
```

这些主要用于文本纠错保守策略，而不是业务建模。

------

## 21. 第十九原则：错误可追踪

DSL v0.1 中关键元素应保留必要调试信息。

推荐字段：

```json
{
  "meta": {
    "confidence": 0.86,
    "sourceBBox": [24, 88, 200, 112],
    "ocrConfidence": 0.93,
    "fallback": false
  }
}
```

目的：

```text
方便开发阶段定位错误
方便后续批量测试
方便低分样本分析
```

但调试信息不应影响基础渲染。

------

## 22. 第二十原则：版本必须显式声明

每份 DSL 必须包含：

```json
{
  "version": "0.1"
}
```

Renderer 必须检查版本。

如果版本不兼容，应返回错误：

```text
UNSUPPORTED_DSL_VERSION
```

原因：

```text
后续 DSL 可能升级到 v0.2 / v0.3。
版本字段是兼容性的基础。
```

------

## 23. DSL v0.1 推荐顶层结构

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

顶层字段说明：

```text
version：DSL 版本
taskId：任务 ID
page：页面信息
assets：图片 / 资源资产
root：根图层树
meta：辅助信息
```

------

## 24. DSL v0.1 最小 Element 结构

```json
{
  "id": "el_001",
  "type": "text",
  "role": "title_text",
  "name": "Title Text",
  "layout": {
    "x": 24,
    "y": 88,
    "width": 200,
    "height": 24
  },
  "style": {},
  "content": {},
  "children": [],
  "meta": {}
}
```

其中：

```text
id：必填，元素唯一标识
type：必填，基础元素类型
role：可选，语义角色
name：可选，Figma 图层名称
layout：必填，坐标和尺寸
style：可选，样式
content：文本等内容
source：图片 / 图标资源
children：子元素
meta：辅助信息
```

------

## 25. Renderer 使用原则

Renderer 渲染时应按以下优先级读取 DSL：

```text
1. type
2. layout
3. style
4. content / source
5. children
6. role
7. meta
```

Renderer 不应使用 AI 或业务逻辑重新判断元素。

Renderer 只做：

```text
DSL 说什么，就尽量按 DSL 渲染什么。
```

如果字段异常：

```text
轻微异常 → 默认值修复
严重异常 → 跳过元素 / fallback / 报错
```

------

## 26. DSL v0.1 成功标准

DSL v0.1 设计成功的标准：

```text
1. 后端能稳定生成
2. Renderer 能稳定消费
3. Schema 能校验
4. 错误能定位
5. 主要 UI 能表达
6. 复杂区域能 fallback
7. 字段结构不拖慢 MVP
8. 后续版本能扩展
```

------

## 27. DSL v0.1 不做事项

DSL v0.1 不做：

```text
代码生成字段
完整 Auto Layout
完整 Component / Instance
完整业务语义
复杂设计系统 token
完整响应式布局
复杂交互状态
动画
多页面项目管理
版本协作
评论
权限
```

这些全部留给后续版本。

------

## 28. 版本结论

DSL v0.1 的核心设计思想：

```text
少类型
轻语义
绝对定位
视觉优先
复杂 fallback
可校验
可修复
快速渲染
```

一句话总结：

> DSL v0.1 不是最终设计系统协议，而是第一版 PNG → Figma 可编辑设计稿的稳定中间层。

只要它能稳定支撑：

```text
PNG → DSL → Figma 可编辑稿
```

就达到了 v0.1 的设计目标。

```
这就是第四份文档：

**`03_DSL规范/01_DSL_v0.1_设计原则.md`**

下一份建议继续输出：

**`03_DSL规范/02_DSL_v0.1_字段说明.md`**
```