下面把剩下两份执行型文档都输出。

------

~~~markdown
# DSL 与 Schema 开发任务 v0.1

文档名称：DSL 与 Schema 开发任务  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 开发任务拆分文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于拆分 DSL v0.1 与 Schema 相关开发任务。

DSL 是后端识别管线与 Figma Renderer 之间的核心协议。

后端负责：

```text
PNG → OCR / AI / CV → DSL v0.1
~~~

Renderer 负责：

```text
DSL v0.1 → Figma 可编辑图层
```

因此，DSL 与 Schema 必须优先开发并相对冻结，否则后端和插件端会反复返工。

------

## 2. 开发目标

DSL 与 Schema v0.1 的目标：

```text
1. 定义 DSL v0.1 的 TypeScript 类型
2. 定义 JSON Schema 校验规则
3. 定义默认值补全规则
4. 定义轻量修复规则
5. 提供示例 DSL
6. 支撑 Renderer 使用假 DSL 先行开发
7. 支撑后端按统一协议生成 DSL
```

v0.1 不追求完整设计系统协议，只服务 MVP 主链路：

```text
PNG → DSL → Figma 可编辑稿
```

------

## 3. 建议目录结构

```text
packages/dsl-schema/
├─ src/
│  ├─ index.ts
│  ├─ types.ts
│  ├─ elementTypes.ts
│  ├─ styleTypes.ts
│  ├─ assetTypes.ts
│  ├─ pageTypes.ts
│  ├─ defaults.ts
│  ├─ validator.ts
│  ├─ normalize.ts
│  ├─ repair.ts
│  └─ errors.ts
│
├─ schemas/
│  └─ dsl-v0.1.schema.json
│
├─ examples/
│  ├─ mobile-home.dsl.json
│  ├─ mobile-list.dsl.json
│  ├─ mobile-detail.dsl.json
│  └─ simple-admin.dsl.json
│
├─ tests/
│  ├─ validator.test.ts
│  ├─ normalize.test.ts
│  └─ repair.test.ts
│
├─ package.json
├─ tsconfig.json
└─ README.md
```

------

## 4. P0 任务：定义 DSL 顶层类型

### 4.1 任务说明

定义 DSL v0.1 顶层结构。

### 4.2 目标文件

```text
packages/dsl-schema/src/types.ts
```

### 4.3 类型定义

```ts
export interface DesignDSL {
  version: "0.1"
  taskId: string
  page: DSLPage
  assets: DSLAsset[]
  root: DSLElement
  meta?: DSLMeta
}
```

### 4.4 验收标准

```text
1. DesignDSL 类型存在
2. version 固定为 "0.1"
3. page / assets / root 必填
4. meta 可选
5. Renderer 和后端都可引用该类型
```

------

## 5. P0 任务：定义 Page 类型

### 5.1 目标文件

```text
packages/dsl-schema/src/pageTypes.ts
```

### 5.2 类型定义

```ts
export interface DSLPage {
  name?: string
  width: number
  height: number
  originalWidth?: number
  originalHeight?: number
  scaleFactor?: number
  viewportHeight?: number
  isScrollable?: boolean
  background?: PageBackground
  safeArea?: SafeArea
}

export interface SafeArea {
  top?: number
  bottom?: number
}

export type PageBackground =
  | {
      type: "color"
      value: string
    }
  | {
      type: "gradient"
      gradient: DSLGradient
    }
  | {
      type: "image"
      assetId: string
    }
```

### 5.3 验收标准

```text
1. page.width / height 必填
2. originalWidth / originalHeight 可选
3. scaleFactor 可选，默认 1
4. background 支持 color / gradient / image
5. safeArea 支持 top / bottom
```

------

## 6. P0 任务：定义 Element 类型

### 6.1 目标文件

```text
packages/dsl-schema/src/elementTypes.ts
```

### 6.2 支持类型

```ts
export type DSLElementType =
  | "frame"
  | "group"
  | "text"
  | "shape"
  | "image"
  | "icon"
  | "line"
```

### 6.3 Element 结构

```ts
export interface DSLElement {
  id: string
  type: DSLElementType
  role?: string
  name?: string
  layout: DSLLayout
  rawLayout?: DSLLayout
  style?: DSLStyle
  content?: DSLContent
  source?: DSLSource
  imageFill?: DSLImageFill
  children?: DSLElement[]
  meta?: DSLElementMeta
}
```

### 6.4 Layout 类型

```ts
export interface DSLLayout {
  x: number
  y: number
  width: number
  height: number
}
```

### 6.5 验收标准

```text
1. DSLElement 类型完整
2. type 只允许 frame / group / text / shape / image / icon / line
3. layout 必填
4. children 使用嵌套对象数组
5. role 不决定基础渲染类型
```

------

## 7. P0 任务：定义 Style 类型

### 7.1 目标文件

```text
packages/dsl-schema/src/styleTypes.ts
```

### 7.2 类型定义

```ts
export interface DSLStyle {
  fill?: string | DSLGradientFill
  color?: string
  opacity?: number
  visible?: boolean
  radius?: number | DSLRadius
  stroke?: DSLStroke
  shadow?: DSLShadow[]
  clipContent?: boolean

  fontFamily?: string
  fontSize?: number
  fontWeight?: number
  lineHeight?: number
  textAlign?: "left" | "center" | "right"
}

export interface DSLRadius {
  topLeft?: number
  topRight?: number
  bottomRight?: number
  bottomLeft?: number
}

export interface DSLStroke {
  color: string
  width: number
}

export interface DSLShadow {
  type: "drop_shadow"
  x: number
  y: number
  blur: number
  spread?: number
  color: string
}

export interface DSLGradientFill {
  type: "linear_gradient"
  angle: number
  stops: DSLGradientStop[]
}

export interface DSLGradientStop {
  color: string
  position: number
}
```

### 7.3 验收标准

```text
1. 支持 fill / color / opacity / visible
2. 支持 radius 单值和四角对象
3. 支持 stroke
4. 支持 shadow
5. 支持 text style 字段
6. 不包含业务语义字段
```

------

## 8. P0 任务：定义 Asset 类型

### 8.1 目标文件

```text
packages/dsl-schema/src/assetTypes.ts
```

### 8.2 类型定义

```ts
export interface DSLAsset {
  assetId: string
  type: "image"
  role?: string
  url: string
  format: "png" | "jpeg" | "jpg" | "webp"
  width?: number
  height?: number
  storage?: "local" | "oss"
  objectKey?: string
  expiresAt?: string
  meta?: Record<string, unknown>
}
```

### 8.3 验收标准

```text
1. assetId 必填
2. url 必填
3. format 必填
4. storage 支持 local / oss
5. 预留 objectKey / expiresAt
```

------

## 9. P0 任务：定义 Content / Source 类型

### 9.1 目标文件

```text
packages/dsl-schema/src/elementTypes.ts
```

### 9.2 类型定义

```ts
export interface DSLContent {
  text?: string
}

export type DSLSource =
  | {
      assetId: string
      url?: string
    }
  | {
      kind: "builtin_svg"
      iconName: string
    }

export interface DSLImageFill {
  mode: "fill" | "fit"
}
```

### 9.3 验收标准

```text
1. text 元素使用 content.text
2. image 元素支持 assetId / url
3. icon 元素支持 builtin_svg / iconName
4. imageFill.mode 支持 fill / fit
```

------

## 10. P0 任务：定义 Meta 类型

### 10.1 目标文件

```text
packages/dsl-schema/src/types.ts
packages/dsl-schema/src/elementTypes.ts
```

### 10.2 类型定义

```ts
export interface DSLMeta {
  createdAt?: string
  source?: "png"
  platformHint?: "mobile" | "desktop_web" | "admin_dashboard" | "unknown"
  qualityFlags?: string[]
  fallbackCount?: number
  elementCount?: number
  promptVersion?: string
  model?: string
  notes?: string
}

export interface DSLElementMeta {
  confidence?: number
  ocrConfidence?: number
  semanticType?: string
  correctionPolicy?: "safe" | "no_free_rewrite"
  fallback?: boolean
  reason?: string
  sourceBBox?: [number, number, number, number]
  qualityFlags?: string[]
  componentSpec?: {
    kind: string
    variant?: string
    confidence?: number
  }
  [key: string]: unknown
}
```

### 10.3 验收标准

```text
1. meta 可选
2. Renderer 不强依赖 meta
3. fallback / reason 可记录
4. componentSpec 只做后续组件化提示
```

------

## 11. P0 任务：实现默认值规则

### 11.1 目标文件

```text
packages/dsl-schema/src/defaults.ts
```

### 11.2 默认值

```ts
export const DSL_DEFAULTS = {
  role: "unknown",
  style: {},
  children: [],
  meta: {},
  opacity: 1,
  visible: true,
  clipContent: false,
  fontFamily: "PingFang SC",
  fontSize: 14,
  fontWeight: 400,
  color: "#000000",
  textAlign: "left",
  imageFillMode: "fill"
}
```

### 11.3 验收标准

```text
1. 缺 role 时补 unknown
2. 缺 style 时补 {}
3. 缺 children 时补 []
4. 缺 visible 时补 true
5. 缺 opacity 时补 1
6. text 缺字号 / 颜色时有默认值
```

------

## 12. P0 任务：实现 Normalize

### 12.1 目标文件

```text
packages/dsl-schema/src/normalize.ts
```

### 12.2 职责

Normalize 用于生成稳定、便于 Renderer 消费的 DSL。

处理：

```text
补默认值
坐标归一
name 自动生成
children 补空数组
meta 补空对象
style 补空对象
```

### 12.3 示例

输入：

```json
{
  "id": "txt_001",
  "type": "text",
  "layout": {
    "x": 23.672,
    "y": 87.438,
    "width": 120.284,
    "height": 22.111
  },
  "content": {
    "text": "首页"
  }
}
```

输出：

```json
{
  "id": "txt_001",
  "type": "text",
  "role": "unknown",
  "name": "Text / txt_001",
  "layout": {
    "x": 23.5,
    "y": 87.5,
    "width": 120.5,
    "height": 22
  },
  "style": {},
  "content": {
    "text": "首页"
  },
  "children": [],
  "meta": {}
}
```

### 12.4 验收标准

```text
1. normalize 后 Renderer 可直接消费
2. 坐标可归一到 0.5 或整数
3. 不改变元素语义
4. 不做复杂重新排版
```

------

## 13. P0 任务：实现基础 Validator

### 13.1 目标文件

```text
packages/dsl-schema/src/validator.ts
```

### 13.2 校验内容

必须校验：

```text
version = 0.1
taskId 存在
page.width / height > 0
assets 是数组
root 存在
root.type = frame
element.id 存在
element.id 唯一
element.type 合法
layout 存在
layout.width / height > 0
text 元素 content.text 存在
image 元素 source.assetId 或 source.url 存在
icon 元素 source.kind / iconName 存在
image assetId 能在 assets 中找到
```

### 13.3 返回结构

```ts
export interface DSLValidationResult {
  valid: boolean
  errors: DSLValidationError[]
  warnings: DSLValidationWarning[]
}

export interface DSLValidationError {
  code: string
  message: string
  path?: string
  elementId?: string
}
```

### 13.4 验收标准

```text
1. 合法 DSL 返回 valid = true
2. 非法 type 能报错
3. 缺 layout 能报错
4. 缺 text content 能报错
5. image assetId 不存在能报错
6. 返回错误 path / elementId
```

------

## 14. P0 任务：实现 JSON Schema

### 14.1 目标文件

```text
packages/dsl-schema/schemas/dsl-v0.1.schema.json
```

### 14.2 说明

JSON Schema 用于：

```text
后端输出校验
测试样例校验
CI 校验
开发阶段快速定位字段错误
```

### 14.3 必须覆盖

```text
DesignDSL
DSLPage
DSLAsset
DSLElement
DSLLayout
DSLStyle
DSLContent
DSLSource
```

### 14.4 验收标准

```text
1. schema 文件存在
2. 示例 DSL 可通过 schema
3. 缺 version 会失败
4. 非法 type 会失败
5. layout 缺失会失败
6. text 缺 content.text 会失败
```

------

## 15. P1 任务：实现 Repair

### 15.1 目标文件

```text
packages/dsl-schema/src/repair.ts
```

### 15.2 修复范围

v0.1 只做轻量修复：

```text
缺 name → 自动补
缺 role → unknown
缺 style → {}
缺 children → []
缺 meta → {}
opacity 超范围 → clamp 到 0～1
radius 负数 → 0
width / height 小于等于 0 → 标记错误或剔除
children 非数组 → []
重复 id → 生成新 id 或报错
```

### 15.3 不做

```text
不重新理解页面
不重新排版
不重新归组
不调用 AI
不自动组件化
```

### 15.4 验收标准

```text
1. 常见缺省字段能修复
2. 修复后能再次 validate
3. 严重错误不能静默吞掉
4. repair 日志可返回
```

------

## 16. P0 任务：准备示例 DSL

### 16.1 目标目录

```text
packages/dsl-schema/examples/
```

### 16.2 必须准备

```text
mobile-home.dsl.json
mobile-list.dsl.json
mobile-detail.dsl.json
simple-admin.dsl.json
```

### 16.3 示例必须覆盖

```text
frame
group
text
shape
image
icon
line
original_reference
fallback_region
```

### 16.4 验收标准

```text
1. 每个示例可通过 validate
2. 每个示例可被 Renderer 渲染
3. 至少一个示例包含 fallback
4. 至少一个示例包含 TabBar
5. 至少一个示例包含商品图或头像
```

------

## 17. P0 任务：导出统一入口

### 17.1 目标文件

```text
packages/dsl-schema/src/index.ts
```

### 17.2 导出内容

```ts
export * from "./types"
export * from "./pageTypes"
export * from "./elementTypes"
export * from "./styleTypes"
export * from "./assetTypes"
export * from "./defaults"
export * from "./validator"
export * from "./normalize"
export * from "./repair"
export * from "./errors"
```

### 17.3 验收标准

```text
1. Renderer 可以从包入口导入类型
2. 插件可以从包入口导入类型
3. 后端如果使用 TS 工具也可复用
```

------

## 18. P1 任务：单元测试

### 18.1 目标目录

```text
packages/dsl-schema/tests/
```

### 18.2 测试文件

```text
validator.test.ts
normalize.test.ts
repair.test.ts
```

### 18.3 测试内容

```text
合法 DSL 通过
缺 version 失败
非法 type 失败
缺 root 失败
缺 layout 失败
text 缺 content.text 失败
image assetId 不存在失败
normalize 能补默认值
repair 能修轻微问题
```

### 18.4 验收标准

```text
1. npm test / pnpm test 可运行
2. 关键校验规则有覆盖
3. 示例 DSL 在测试中校验
```

------

## 19. P1 任务：Schema CLI 校验脚本

### 19.1 目标文件

```text
scripts/validate-dsl.ts
```

### 19.2 用途

允许开发人员在命令行校验 DSL：

```bash
pnpm validate-dsl examples/dsl/mobile-home.dsl.json
```

### 19.3 输出示例

成功：

```text
DSL valid: mobile-home.dsl.json
```

失败：

```text
DSL invalid:
- root.children[3].layout.width must be greater than 0
- image img_001 references missing assetId asset_product_001
```

### 19.4 验收标准

```text
1. 可读取 DSL JSON 文件
2. 可调用 validator
3. 可输出错误列表
4. 可用于开发调试
```

------

## 20. P0 / P1 / P2 优先级汇总

### P0 必须完成

```text
DesignDSL 类型
Page 类型
Element 类型
Style 类型
Asset 类型
默认值
Normalize
Validator
JSON Schema
至少 1 个完整示例 DSL
统一导出 index.ts
```

### P1 尽快完成

```text
Repair
3～4 个示例 DSL
单元测试
CLI 校验脚本
错误码定义
```

### P2 后续优化

```text
更完整 JSON Schema
更严格类型推导
DSL diff 工具
DSL formatter
DSL visual inspector
版本迁移工具 v0.1 → v0.2
```

------

## 21. 与其他模块的依赖关系

### 21.1 Renderer 依赖

Renderer 依赖：

```text
DesignDSL
DSLElement
DSLStyle
DSLAsset
Validator
Normalize
Defaults
```

### 21.2 后端依赖

后端应参考：

```text
DSL 字段说明
JSON Schema
示例 DSL
Validator 规则
```

如果后端是 Python，也应同步实现一份 Pydantic Schema 或 JSON Schema 校验。

### 21.3 插件 UI 依赖

插件 UI 不直接依赖 DSL 细节，只通过 Plugin Main 调用 Renderer。

------

## 22. 验收标准

DSL 与 Schema 开发完成标准：

```text
1. packages/dsl-schema 可以独立安装 / 引用
2. TypeScript 类型完整
3. JSON Schema 存在
4. 示例 DSL 能通过校验
5. Renderer 能使用示例 DSL 渲染
6. 后端可按字段说明生成 DSL
7. 常见错误能被 validator 捕获
8. Normalize 能补基础默认值
9. Repair 能处理轻微问题
10. 版本号固定为 0.1
```

------

## 23. 版本结论

DSL 与 Schema 是 v0.1 的第一优先级。

只要 DSL 不稳定，后端和 Renderer 都会反复返工。

因此 v0.1 开发必须先完成：

```text
DSL 类型
字段规则
示例 DSL
Schema 校验
```

再进入 Renderer 和后端真实识别开发。

一句话总结：

> 先把协议定住，再让所有模块围绕协议开发。

```
---

```markdown
# Renderer 渲染包开发任务 v0.1

文档名称：Renderer 渲染包开发任务  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 开发任务拆分文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于拆分 Image-to-Figma Renderer v0.1 的开发任务。

Renderer 是 Figma 插件内的核心渲染包，负责：

```text
DSL v0.1 → Figma 可编辑图层
```

Renderer 不负责：

```text
PNG 识别
OCR
AI 分析
图片裁切
DSL 生成
质量评分
代码生成
组件化
Auto Layout
```

------

## 2. 开发目标

Renderer v0.1 的目标：

```text
1. 能消费合法 DSL v0.1
2. 能创建 Figma root Frame
3. 能渲染 frame / group / text / shape / image / icon / line
4. 能应用基础 layout / style
5. 能加载图片资产
6. 能渲染隐藏原图参考层
7. 能渲染 fallback 图片区域
8. 单个元素失败不导致整页失败
9. 能返回 RenderResult 和 warnings
```

------

## 3. 建议目录结构

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
│  ├─ applyVisibility.ts
│  ├─ assetResolver.ts
│  ├─ imageLoader.ts
│  ├─ builtinIcons.ts
│  ├─ iconRenderer.ts
│  ├─ figmaPaint.ts
│  ├─ figmaEffects.ts
│  ├─ figmaFonts.ts
│  ├─ errors.ts
│  ├─ logger.ts
│  └─ types.ts
│
├─ tests/
│  ├─ renderDesign.test.ts
│  ├─ assetResolver.test.ts
│  └─ styleConverter.test.ts
│
├─ package.json
├─ tsconfig.json
└─ README.md
```

------

## 4. P0 任务：定义 Renderer 类型

### 4.1 目标文件

```text
packages/image-to-figma-renderer/src/types.ts
```

### 4.2 类型定义

```ts
export interface RenderOptions {
  selectAfterRender?: boolean
  scrollIntoView?: boolean
  createMissingImagePlaceholder?: boolean
  imageConcurrency?: number
  logger?: RendererLogger
}

export type RenderResult = RenderSuccessResult | RenderFailedResult

export interface RenderSuccessResult {
  success: true
  rootNodeId: string
  renderedElementCount: number
  skippedElementCount: number
  warningCount: number
  warnings: RenderWarning[]
}

export interface RenderFailedResult {
  success: false
  errorCode: string
  message: string
  warnings?: RenderWarning[]
}

export interface RenderWarning {
  elementId?: string
  elementType?: string
  code: string
  message: string
  stage?: string
  assetId?: string
}
```

### 4.3 验收标准

```text
1. RenderOptions 类型存在
2. RenderResult 类型存在
3. RenderWarning 类型存在
4. 后续所有渲染函数统一使用这些类型
```

------

## 5. P0 任务：实现 Renderer 入口

### 5.1 目标文件

```text
packages/image-to-figma-renderer/src/index.ts
packages/image-to-figma-renderer/src/renderDesign.ts
```

### 5.2 入口 API

```ts
export async function renderDesign(
  dsl: DesignDSL,
  options?: RenderOptions
): Promise<RenderResult>
```

### 5.3 renderDesign 职责

```text
检查 DSL version
基础校验 root / page
normalize DSL
建立 assetMap
创建 root Frame
递归渲染 children
选中 root Frame
定位到 root Frame
返回 RenderResult
```

### 5.4 验收标准

```text
1. renderDesign 可被插件 main 调用
2. 合法 DSL 能返回 success = true
3. root 级错误能返回 success = false
4. 渲染完成后返回 rootNodeId
5. 返回 renderedElementCount / skippedElementCount / warnings
```

------

## 6. P0 任务：实现 RenderContext

### 6.1 目标文件

```text
packages/image-to-figma-renderer/src/types.ts
packages/image-to-figma-renderer/src/renderDesign.ts
```

### 6.2 RenderContext

```ts
export interface RenderContext {
  dsl: DesignDSL
  options: RenderOptions
  assetMap: Map<string, DSLAsset>
  imageCache: Map<string, string>
  warnings: RenderWarning[]
  renderedElementCount: number
  skippedElementCount: number
  logger: RendererLogger
}
```

### 6.3 验收标准

```text
1. 渲染过程中共享 assetMap
2. 渲染过程中共享 imageCache
3. 能累计 warnings
4. 能累计 rendered / skipped 数量
```

------

## 7. P0 任务：实现元素分发

### 7.1 目标文件

```text
packages/image-to-figma-renderer/src/renderElement.ts
```

### 7.2 逻辑

```ts
export async function renderElement(element: DSLElement, ctx: RenderContext) {
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
      throw new RendererError("INVALID_ELEMENT_TYPE", `Unsupported type`)
  }
}
```

### 7.3 验收标准

```text
1. 支持 7 种 type 分发
2. 不支持 type 能抛出明确错误
3. 不在这里做业务语义判断
```

------

## 8. P0 任务：实现 children 递归渲染

### 8.1 目标文件

```text
packages/image-to-figma-renderer/src/renderChildren.ts
```

### 8.2 逻辑

```text
按 children 顺序渲染
单个 child 失败时记录 warning
不中断兄弟节点渲染
成功节点 append 到 parent
```

### 8.3 验收标准

```text
1. 能递归渲染多层 children
2. children 顺序决定图层顺序
3. 单个 child 失败不影响整页
4. skippedElementCount 正确增加
```

------

## 9. P0 任务：实现 Frame 渲染

### 9.1 目标文件

```text
packages/image-to-figma-renderer/src/renderFrame.ts
```

### 9.2 职责

```text
figma.createFrame
applyName
applyLayout
applyStyle
renderChildren
return FrameNode
```

### 9.3 验收标准

```text
1. frame 能生成 Figma Frame
2. layout 正确
3. fill / radius / opacity / visible 生效
4. children 能正常渲染到 frame 内
```

------

## 10. P0 任务：实现 Group 渲染

### 10.1 目标文件

```text
packages/image-to-figma-renderer/src/renderGroup.ts
```

### 10.2 v0.1 策略

v0.1 中 group 可直接渲染为 Frame。

```text
type = group → figma.createFrame()
```

### 10.3 默认样式

```text
无填充
不裁切
只作为逻辑容器
```

### 10.4 验收标准

```text
1. group 能作为容器渲染
2. group children 能正常渲染
3. group 不产生多余背景色
```

------

## 11. P0 任务：实现 Text 渲染

### 11.1 目标文件

```text
packages/image-to-figma-renderer/src/renderText.ts
packages/image-to-figma-renderer/src/applyTextStyle.ts
packages/image-to-figma-renderer/src/figmaFonts.ts
```

### 11.2 职责

```text
校验 content.text
加载字体
figma.createText
设置 characters
应用 layout
应用 fontSize / fontWeight / lineHeight / color / textAlign
```

### 11.3 字体策略

优先使用：

```text
style.fontFamily
```

失败后回退：

```text
PingFang SC
Inter
Arial
```

### 11.4 验收标准

```text
1. 中文能显示
2. 文本可编辑
3. 字号生效
4. 颜色生效
5. 对齐生效
6. 字体加载失败不导致整页失败
7. 缺 content.text 时跳过并记录 warning
```

------

## 12. P0 任务：实现 Shape 渲染

### 12.1 目标文件

```text
packages/image-to-figma-renderer/src/renderShape.ts
```

### 12.2 职责

```text
figma.createRectangle
applyName
applyLayout
applyStyle
return RectangleNode
```

### 12.3 支持

```text
纯色 fill
opacity
radius
stroke
shadow
visible
```

### 12.4 验收标准

```text
1. 普通矩形可显示
2. 圆角矩形可显示
3. 按钮背景可显示
4. 卡片背景可显示
5. 描边可显示
```

------

## 13. P0 任务：实现 Image 渲染

### 13.1 目标文件

```text
packages/image-to-figma-renderer/src/renderImage.ts
packages/image-to-figma-renderer/src/imageLoader.ts
packages/image-to-figma-renderer/src/assetResolver.ts
```

### 13.2 职责

```text
resolve asset
fetch image URL
figma.createImage
createRectangle
apply layout
apply style
apply ImagePaint
```

### 13.3 图片模式

```text
imageFill.mode = fill → Figma FILL
imageFill.mode = fit → Figma FIT
```

### 13.4 图片缓存

同一个 URL 不重复 createImage。

```ts
imageCache: Map<string, string>
```

### 13.5 验收标准

```text
1. image 元素能加载 URL
2. 图片能显示在正确位置
3. fill / fit 可用
4. 圆角图片可用
5. 图片加载失败不导致整页失败
6. 能创建 Missing Image 占位或记录 warning
```

------

## 14. P1 任务：实现 Icon 渲染

### 14.1 目标文件

```text
packages/image-to-figma-renderer/src/renderIcon.ts
packages/image-to-figma-renderer/src/builtinIcons.ts
packages/image-to-figma-renderer/src/iconRenderer.ts
```

### 14.2 支持方式

v0.1 只支持：

```text
builtin_svg
```

### 14.3 首批内置图标

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

### 14.4 验收标准

```text
1. search 图标可渲染
2. home 图标可渲染
3. user 图标可渲染
4. cart 图标可渲染
5. iconName 找不到时不导致整页失败
6. 图标能 resize 到 layout 尺寸
```

------

## 15. P1 任务：实现 Line 渲染

### 15.1 目标文件

```text
packages/image-to-figma-renderer/src/renderLine.ts
```

### 15.2 v0.1 策略

用 Rectangle 渲染 line。

```text
width = layout.width
height = max(layout.height, 0.5)
fill = style.fill
```

### 15.3 验收标准

```text
1. 0.5px 分割线能显示
2. 1px 分割线能显示
3. 颜色正确
4. 横线可用
```

------

## 16. P0 任务：实现 applyLayout

### 16.1 目标文件

```text
packages/image-to-figma-renderer/src/applyLayout.ts
```

### 16.2 职责

```text
校验 x / y / width / height
设置 node.x
设置 node.y
调用 node.resize
```

### 16.3 验收标准

```text
1. x / y 正确
2. width / height 正确
3. width / height <= 0 抛出 INVALID_LAYOUT
4. 支持 0.5px
```

------

## 17. P0 任务：实现 applyStyle

### 17.1 目标文件

```text
packages/image-to-figma-renderer/src/applyStyle.ts
```

### 17.2 支持字段

```text
fill
opacity
visible
radius
stroke
shadow
clipContent
```

### 17.3 验收标准

```text
1. fill 生效
2. opacity 生效
3. visible 生效
4. radius 生效
5. stroke 生效
6. clipContent 对 Frame 生效
7. 单个样式失败不影响节点创建
```

------

## 18. P1 任务：实现 applyEffects

### 18.1 目标文件

```text
packages/image-to-figma-renderer/src/applyEffects.ts
packages/image-to-figma-renderer/src/figmaEffects.ts
```

### 18.2 支持

```text
drop_shadow
```

### 18.3 验收标准

```text
1. 单层阴影可用
2. 多层阴影最多支持 2 层
3. 不支持 shadow 类型时记录 warning
```

------

## 19. P2 任务：实现 applyGradient

### 19.1 目标文件

```text
packages/image-to-figma-renderer/src/applyGradient.ts
```

### 19.2 支持

```text
linear_gradient
2～3 个 stops
angle
```

### 19.3 验收标准

```text
1. 简单线性渐变可显示
2. 复杂渐变不影响整体渲染
3. 不支持时 fallback 为第一个颜色或记录 warning
```

------

## 20. P0 任务：实现 Asset Resolver

### 20.1 目标文件

```text
packages/image-to-figma-renderer/src/assetResolver.ts
```

### 20.2 职责

```text
建立 assetMap
根据 source.assetId 找 asset
source.url 优先于 assets.url
asset 找不到返回错误
```

### 20.3 规则

优先级：

```text
source.url > assetMap[assetId].url
```

### 20.4 验收标准

```text
1. assetId 能解析到 asset
2. source.url 能直接使用
3. assetId 不存在能返回 ASSET_NOT_FOUND
4. 重复 assetId 有 warning
```

------

## 21. P0 任务：实现 Image Loader

### 21.1 目标文件

```text
packages/image-to-figma-renderer/src/imageLoader.ts
```

### 21.2 职责

```text
fetch image url
arrayBuffer
Uint8Array
figma.createImage
返回 imageHash
写入 imageCache
```

### 21.3 验收标准

```text
1. 能加载本地 URL 图片
2. 能创建 Figma Image
3. 相同 URL 命中缓存
4. fetch 失败返回 ASSET_LOAD_FAILED
```

------

## 22. P1 任务：Missing Image 占位

### 22.1 目标文件

```text
packages/image-to-figma-renderer/src/renderImage.ts
```

### 22.2 占位样式

```text
fill = #F2F2F2
stroke = #FF4D4F
name = Missing Image / {element.id}
```

### 22.3 验收标准

```text
1. asset 缺失时创建占位
2. 图片加载失败时创建占位
3. 占位不导致整页失败
4. warnings 中记录错误
```

------

## 23. P0 任务：错误类与错误码

### 23.1 目标文件

```text
packages/image-to-figma-renderer/src/errors.ts
```

### 23.2 错误码

```text
UNSUPPORTED_DSL_VERSION
INVALID_DSL
INVALID_PAGE
ROOT_MISSING
INVALID_ROOT_TYPE
INVALID_ROOT_LAYOUT
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

### 23.3 验收标准

```text
1. RendererError 类存在
2. 错误包含 code / message / elementId
3. fatal error 和 element error 可区分
4. 可转换为 RenderWarning
```

------

## 24. P1 任务：Logger

### 24.1 目标文件

```text
packages/image-to-figma-renderer/src/logger.ts
```

### 24.2 日志级别

```text
debug
info
warn
error
```

### 24.3 v0.1 实现

可以先简单映射：

```ts
console.log
console.warn
console.error
```

### 24.4 验收标准

```text
1. RenderOptions 可传入 logger
2. 默认 logger 可用
3. 渲染开始 / 结束有日志
4. warning / error 有日志
```

------

## 25. P0 任务：渲染完成处理

### 25.1 目标文件

```text
packages/image-to-figma-renderer/src/renderDesign.ts
```

### 25.2 处理

```text
选中 root Frame
滚动视图到 root Frame
返回 RenderResult
```

### 25.3 代码

```ts
figma.currentPage.selection = [rootFrame]
figma.viewport.scrollAndZoomIntoView([rootFrame])
```

### 25.4 验收标准

```text
1. 渲染完成后用户能看到结果
2. root Frame 被选中
3. options 可关闭 select / scroll
```

------

## 26. P0 任务：与 Figma 插件 Main 集成

### 26.1 目标文件

```text
figma-plugin/src/plugin/main.ts
figma-plugin/src/plugin/controller.ts
```

### 26.2 流程

```text
Plugin Main 收到 DSL
↓
调用 renderDesign(dsl)
↓
根据 RenderResult 给 UI 发 DONE / ERROR
```

### 26.3 验收标准

```text
1. Plugin Main 可以调用 Renderer
2. Renderer 成功后 UI 进入 DoneView
3. Renderer 失败后 UI 进入 ErrorView
4. warnings 可在开发阶段打印
```

------

## 27. P1 任务：用示例 DSL 做回归测试

### 27.1 目标

每次 Renderer 修改后，用示例 DSL 验证不破坏基础渲染。

### 27.2 示例

```text
mobile-home.dsl.json
mobile-list.dsl.json
mobile-detail.dsl.json
simple-admin.dsl.json
```

### 27.3 验收标准

```text
1. 示例 DSL 都能渲染 root Frame
2. 不出现 fatal error
3. renderedElementCount 大于 0
4. warnings 可接受
```

------

## 28. P0 / P1 / P2 优先级汇总

### P0 必须完成

```text
Renderer 类型
renderDesign
RenderContext
renderElement
renderChildren
renderFrame
renderGroup
renderText
renderShape
renderImage
applyLayout
applyStyle
assetResolver
imageLoader
errors
渲染完成选中 root
插件 Main 集成
```

### P1 尽快完成

```text
renderIcon
renderLine
renderReference
applyTextStyle
figmaFonts
applyEffects
Missing Image 占位
logger
示例 DSL 回归
```

### P2 后续优化

```text
applyGradient
图片并发加载
SVG 精准改色
更完整阴影
更多图标
更好的占位样式
渲染性能统计
```

------

## 29. 开发顺序建议

推荐顺序：

```text
1. RenderResult / RenderOptions / RenderContext
2. renderDesign 创建 root Frame
3. applyLayout / applyStyle
4. renderFrame / renderChildren
5. renderText
6. renderShape
7. assetResolver / imageLoader
8. renderImage
9. renderLine
10. renderIcon
11. original_reference / fallback
12. 错误 warnings
13. 插件 Main 集成
14. 示例 DSL 回归测试
```

核心原则：

```text
先让假 DSL 能生成 Figma，再追求样式细节。
```

------

## 30. 验收标准

Renderer v0.1 完成标准：

```text
1. 合法 DSL v0.1 可被 renderDesign 接收
2. 能创建 root Frame
3. 能递归渲染 children
4. Text 可编辑
5. Shape 可显示
6. Image 可加载
7. Icon 基础可用
8. Line 基础可用
9. Original Reference 默认隐藏
10. Fallback 图片可显示
11. 单元素失败不影响整页
12. 返回 RenderResult
13. warnings 可追踪
14. 插件 Main 能集成调用
```

------

## 31. 明确不做

Renderer v0.1 不做：

```text
Auto Layout
真正 Figma Component
代码生成
OCR
AI 分析
图片裁切
DSL 生成
质量评分
复杂业务语义判断
复杂图表结构化
复杂 SVG 完美矢量化
```

------

## 32. 版本结论

Renderer 是 v0.1 的核心技术包之一。

它的开发必须克制：

```text
只做 DSL → Figma
不做 PNG → DSL
不做 AI
不做外围产品功能
```

第一版只要能稳定把 DSL v0.1 渲染成 Figma 可编辑图层，就完成 Renderer 的核心任务。

```
这两份就是：

```text
10_开发计划与任务拆分/03_DSL与Schema任务_v0.1.md
10_开发计划与任务拆分/04_Renderer渲染包任务_v0.1.md
```