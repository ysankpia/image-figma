下面继续输出第五份核心文档：

**`03_DSL规范/02_DSL_v0.1_字段说明.md`**

~~~markdown
# DSL v0.1 字段说明

文档名称：DSL v0.1 字段说明  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 核心协议字段文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于定义 DSL v0.1 的字段结构、字段类型、是否必填、默认值和使用说明。

DSL v0.1 是后端和 Figma 插件 Renderer 之间的数据协议：

```text
后端：PNG → OCR / AI / CV → DSL v0.1
插件：DSL v0.1 → Figma 可编辑图层
~~~

v0.1 的设计目标是：

```text
结构简单
字段稳定
Renderer 易消费
后端易生成
支持基础校验
支持后续扩展
```

------

## 2. DSL 顶层结构

DSL v0.1 顶层结构如下：

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

顶层字段：

| 字段      | 类型    | 必填 | 默认值 | 说明                          |
| --------- | ------- | ---- | ------ | ----------------------------- |
| `version` | string  | 是   | 无     | DSL 版本，v0.1 固定为 `"0.1"` |
| `taskId`  | string  | 是   | 无     | 后端任务 ID                   |
| `page`    | object  | 是   | 无     | 页面基础信息                  |
| `assets`  | array   | 是   | `[]`   | 图片等资源列表                |
| `root`    | Element | 是   | 无     | 根图层节点                    |
| `meta`    | object  | 否   | `{}`   | 辅助信息，不作为渲染强依赖    |

------

## 3. version 字段

### 3.1 字段定义

```json
{
  "version": "0.1"
}
```

| 字段      | 类型   | 必填 | 说明       |
| --------- | ------ | ---- | ---------- |
| `version` | string | 是   | DSL 版本号 |

### 3.2 规则

v0.1 中固定为：

```text
0.1
```

Renderer 必须检查版本。

如果版本不支持，应报错：

```text
UNSUPPORTED_DSL_VERSION
```

------

## 4. taskId 字段

### 4.1 字段定义

```json
{
  "taskId": "task_001"
}
```

| 字段     | 类型   | 必填 | 说明            |
| -------- | ------ | ---- | --------------- |
| `taskId` | string | 是   | 后端生成任务 ID |

### 4.2 用途

`taskId` 用于：

```text
任务追踪
错误日志关联
图片资产归属
DSL 文件归属
内部测试后台查询
```

------

## 5. page 字段

### 5.1 Page 结构

```json
{
  "page": {
    "name": "home",
    "width": 390,
    "height": 844,
    "originalWidth": 780,
    "originalHeight": 1688,
    "scaleFactor": 2,
    "viewportHeight": 844,
    "isScrollable": false,
    "background": {
      "type": "color",
      "value": "#F7F8FA"
    },
    "safeArea": {
      "top": 44,
      "bottom": 34
    }
  }
}
```

### 5.2 Page 字段说明

| 字段             | 类型           | 必填 | 默认值                                | 说明                                   |
| ---------------- | -------------- | ---- | ------------------------------------- | -------------------------------------- |
| `name`           | string         | 否   | `"Generated Screen"`                  | 页面名称，也是 Figma 根 Frame 名称来源 |
| `width`          | number         | 是   | 无                                    | Figma 页面宽度，单位 px                |
| `height`         | number         | 是   | 无                                    | Figma 页面高度，单位 px                |
| `originalWidth`  | number         | 否   | 同 `width`                            | 原始 PNG 宽度                          |
| `originalHeight` | number         | 否   | 同 `height`                           | 原始 PNG 高度                          |
| `scaleFactor`    | number         | 否   | `1`                                   | 原图到 Figma 坐标的缩放比例            |
| `viewportHeight` | number         | 否   | 同 `height`                           | 首屏高度                               |
| `isScrollable`   | boolean        | 否   | `false`                               | 是否为长页面 / 可滚动页面              |
| `background`     | PageBackground | 否   | `{ type: "color", value: "#FFFFFF" }` | 页面背景                               |
| `safeArea`       | SafeArea       | 否   | `{ top: 0, bottom: 0 }`               | 安全区信息                             |

------

## 6. page.background 字段

### 6.1 纯色背景

```json
{
  "background": {
    "type": "color",
    "value": "#F7F8FA"
  }
}
```

| 字段    | 类型   | 必填                   | 说明                                               |
| ------- | ------ | ---------------------- | -------------------------------------------------- |
| `type`  | string | 是                     | 背景类型，v0.1 支持 `color` / `gradient` / `image` |
| `value` | string | 当 `type=color` 时必填 | 颜色值                                             |

### 6.2 渐变背景

```json
{
  "background": {
    "type": "gradient",
    "gradient": {
      "type": "linear",
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
}
```

v0.1 只支持简单线性渐变。复杂渐变建议 fallback 为图片。

### 6.3 图片背景

```json
{
  "background": {
    "type": "image",
    "assetId": "asset_bg_001"
  }
}
```

图片背景通过 `assetId` 引用 `assets` 中的图片资源。

------

## 7. safeArea 字段

### 7.1 字段结构

```json
{
  "safeArea": {
    "top": 44,
    "bottom": 34
  }
}
```

| 字段     | 类型   | 必填 | 默认值 | 说明           |
| -------- | ------ | ---- | ------ | -------------- |
| `top`    | number | 否   | `0`    | 顶部安全区高度 |
| `bottom` | number | 否   | `0`    | 底部安全区高度 |

### 7.2 用途

`safeArea` 主要用于：

```text
记录状态栏区域
记录底部 Home Indicator 区域
后续代码生成 / 滚动结构优化预留
```

v0.1 Renderer 不强依赖该字段。

------

## 8. assets 字段

### 8.1 assets 结构

```json
{
  "assets": [
    {
      "assetId": "asset_original",
      "type": "image",
      "role": "original",
      "url": "http://localhost:8000/files/uploads/original.png",
      "format": "png",
      "width": 390,
      "height": 844,
      "storage": "local"
    }
  ]
}
```

### 8.2 Asset 字段说明

| 字段        | 类型   | 必填 | 默认值    | 说明                          |
| ----------- | ------ | ---- | --------- | ----------------------------- |
| `assetId`   | string | 是   | 无        | 资源唯一 ID                   |
| `type`      | string | 是   | `"image"` | 资源类型，v0.1 主要为 `image` |
| `role`      | string | 否   | `"asset"` | 资源角色                      |
| `url`       | string | 是   | 无        | 插件可访问的资源 URL          |
| `format`    | string | 是   | 无        | 图片格式，如 `png` / `jpeg`   |
| `width`     | number | 否   | 无        | 资源宽度                      |
| `height`    | number | 否   | 无        | 资源高度                      |
| `storage`   | string | 否   | `"local"` | 存储类型，`local` / `oss`     |
| `objectKey` | string | 否   | 无        | OSS / 对象存储路径            |
| `expiresAt` | string | 否   | 无        | 签名 URL 过期时间             |
| `meta`      | object | 否   | `{}`      | 辅助信息                      |

------

## 9. root 字段

### 9.1 root 结构

`root` 是页面根节点，类型必须是 `frame`。

```json
{
  "root": {
    "id": "root",
    "type": "frame",
    "role": "screen",
    "name": "Generated Screen",
    "layout": {
      "x": 0,
      "y": 0,
      "width": 390,
      "height": 844
    },
    "style": {
      "fill": "#F7F8FA"
    },
    "children": []
  }
}
```

### 9.2 root 要求

| 要求            | 说明                        |
| --------------- | --------------------------- |
| `id`            | 必须唯一，推荐固定为 `root` |
| `type`          | 必须为 `frame`              |
| `role`          | 推荐为 `screen`             |
| `layout.x`      | 应为 `0`                    |
| `layout.y`      | 应为 `0`                    |
| `layout.width`  | 应等于 `page.width`         |
| `layout.height` | 应等于 `page.height`        |
| `children`      | 页面所有顶层图层            |

------

## 10. Element 通用结构

### 10.1 Element 示例

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
  "source": {},
  "children": [],
  "meta": {}
}
```

### 10.2 Element 字段说明

| 字段       | 类型   | 必填 | 默认值                        | 说明                |
| ---------- | ------ | ---- | ----------------------------- | ------------------- |
| `id`       | string | 是   | 无                            | 元素唯一 ID         |
| `type`     | string | 是   | 无                            | 元素基础类型        |
| `role`     | string | 否   | `"unknown"`                   | 元素语义角色        |
| `name`     | string | 否   | 根据 `type` / `role` 自动生成 | Figma 图层名称      |
| `layout`   | Layout | 是   | 无                            | 元素坐标和尺寸      |
| `style`    | Style  | 否   | `{}`                          | 元素样式            |
| `content`  | object | 否   | `{}`                          | 文本等内容          |
| `source`   | object | 否   | `{}`                          | 图片 / 图标资源来源 |
| `children` | array  | 否   | `[]`                          | 子元素数组          |
| `meta`     | object | 否   | `{}`                          | 辅助信息            |

------

## 11. Element.type 字段

### 11.1 支持类型

v0.1 只支持以下类型：

```text
frame
group
text
shape
image
icon
line
```

### 11.2 类型说明

| type    | 说明          | Figma 对应                     |
| ------- | ------------- | ------------------------------ |
| `frame` | 容器或模块    | FrameNode                      |
| `group` | 逻辑分组      | GroupNode 或 FrameNode         |
| `text`  | 文本          | TextNode                       |
| `shape` | 基础形状      | RectangleNode / EllipseNode    |
| `image` | 图片          | RectangleNode + ImagePaint     |
| `icon`  | 内置 SVG 图标 | VectorNode / SVG imported node |
| `line`  | 分割线 / 细线 | RectangleNode 或 LineNode      |

------

## 12. Element.role 字段

### 12.1 role 用途

`role` 表示元素语义，但不决定基础渲染类型。

例如：

```json
{
  "type": "frame",
  "role": "button"
}
```

Renderer 仍然按 `frame` 渲染，`button` 只用于命名、分组和后续扩展。

### 12.2 常见 role

```text
screen
original_reference
status_bar
navigation_bar
content
tab_bar
tab_item
search_bar
button
button_background
button_label
card
list
list_item
form
form_item
modal
toast
image
product_image
avatar
banner_image
icon
search_icon
back_icon
text
title_text
body_text
price_text
placeholder_text
divider
fallback_region
```

### 12.3 规则

如果无法判断 role：

```json
{
  "role": "unknown"
}
```

不要因为 role 不确定导致生成失败。

------

## 13. layout 字段

### 13.1 Layout 结构

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

### 13.2 Layout 字段说明

| 字段     | 类型   | 必填 | 说明              |
| -------- | ------ | ---- | ----------------- |
| `x`      | number | 是   | 元素左上角 x 坐标 |
| `y`      | number | 是   | 元素左上角 y 坐标 |
| `width`  | number | 是   | 元素宽度          |
| `height` | number | 是   | 元素高度          |

### 13.3 规则

```text
x / y / width / height 单位均为 px
坐标基于 root 左上角
width / height 必须大于 0
坐标建议归一到 0.5 或整数
```

------

## 14. rawLayout 字段

### 14.1 结构

```json
{
  "rawLayout": {
    "x": 23.6721,
    "y": 87.4388,
    "width": 342.2941,
    "height": 47.9122
  }
}
```

### 14.2 说明

`rawLayout` 可选，用于记录算法原始坐标。

Renderer 默认使用 `layout`，不使用 `rawLayout`。

用途：

```text
调试坐标归一
内部评估
后续优化
```

------

## 15. style 字段

### 15.1 Style 通用结构

```json
{
  "style": {
    "fill": "#FFFFFF",
    "opacity": 1,
    "visible": true,
    "radius": 12,
    "stroke": {
      "color": "#EEEEEE",
      "width": 1
    },
    "shadow": [],
    "clipContent": false
  }
}
```

### 15.2 Style 字段说明

| 字段          | 类型            | 必填      | 默认值   | 说明              |
| ------------- | --------------- | --------- | -------- | ----------------- |
| `fill`        | string / object | 否        | 无       | 填充色或渐变      |
| `color`       | string          | 否        | 无       | 文本 / 图标颜色   |
| `opacity`     | number          | 否        | `1`      | 透明度，范围 0～1 |
| `visible`     | boolean         | 否        | `true`   | 是否显示          |
| `radius`      | number / object | 否        | `0`      | 圆角              |
| `stroke`      | object          | 否        | 无       | 描边              |
| `shadow`      | array           | 否        | `[]`     | 阴影              |
| `clipContent` | boolean         | 否        | `false`  | 是否裁切内容      |
| `fontFamily`  | string          | text 专用 | 默认字体 | 字体              |
| `fontSize`    | number          | text 专用 | 14       | 字号              |
| `fontWeight`  | number          | text 专用 | 400      | 字重              |
| `lineHeight`  | number          | text 专用 | 自动     | 行高              |
| `textAlign`   | string          | text 专用 | `left`   | 对齐方式          |

------

## 16. fill 字段

### 16.1 纯色填充

```json
{
  "fill": "#FFFFFF"
}
```

### 16.2 渐变填充

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

### 16.3 规则

v0.1 支持：

```text
纯色
简单线性渐变
```

复杂渐变建议 fallback 为图片。

------

## 17. stroke 字段

### 17.1 结构

```json
{
  "stroke": {
    "color": "#EEEEEE",
    "width": 1
  }
}
```

### 17.2 字段说明

| 字段    | 类型   | 必填 | 默认值 | 说明     |
| ------- | ------ | ---- | ------ | -------- |
| `color` | string | 是   | 无     | 描边颜色 |
| `width` | number | 是   | `1`    | 描边宽度 |

### 17.3 规则

支持 0.5px 细线：

```json
{
  "width": 0.5
}
```

------

## 18. radius 字段

### 18.1 单一圆角

```json
{
  "radius": 12
}
```

### 18.2 多角圆角

```json
{
  "radius": {
    "topLeft": 12,
    "topRight": 12,
    "bottomRight": 0,
    "bottomLeft": 0
  }
}
```

### 18.3 规则

常见归一值：

```text
2 / 4 / 6 / 8 / 10 / 12 / 16 / 20 / 24 / 999
```

`999` 可表示圆形或胶囊形。

------

## 19. shadow 字段

### 19.1 结构

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

### 19.2 字段说明

| 字段     | 类型   | 必填 | 说明                    |
| -------- | ------ | ---- | ----------------------- |
| `type`   | string | 是   | v0.1 支持 `drop_shadow` |
| `x`      | number | 是   | x 偏移                  |
| `y`      | number | 是   | y 偏移                  |
| `blur`   | number | 是   | 模糊值                  |
| `spread` | number | 否   | 扩展值                  |
| `color`  | string | 是   | 阴影颜色                |

v0.1 只重点支持常见单层阴影。

------

## 20. content 字段

### 20.1 文本内容

Text 元素使用：

```json
{
  "content": {
    "text": "搜索商品"
  }
}
```

| 字段   | 类型   | 必填      | 说明     |
| ------ | ------ | --------- | -------- |
| `text` | string | text 必填 | 文本内容 |

### 20.2 规则

数字敏感文本应在 meta 中标记：

```json
{
  "meta": {
    "semanticType": "price",
    "correctionPolicy": "no_free_rewrite"
  }
}
```

------

## 21. Text style 字段

Text 元素样式示例：

```json
{
  "style": {
    "fontFamily": "PingFang SC",
    "fontSize": 16,
    "fontWeight": 500,
    "lineHeight": 22,
    "color": "#111111",
    "textAlign": "left"
  }
}
```

### 21.1 字段说明

| 字段         | 类型   | 必填 | 默认值       | 说明     |
| ------------ | ------ | ---- | ------------ | -------- |
| `fontFamily` | string | 否   | 系统默认字体 | 字体     |
| `fontSize`   | number | 否   | `14`         | 字号     |
| `fontWeight` | number | 否   | `400`        | 字重     |
| `lineHeight` | number | 否   | 自动         | 行高     |
| `color`      | string | 否   | `#000000`    | 文字颜色 |
| `textAlign`  | string | 否   | `left`       | 对齐方式 |

### 21.2 textAlign 取值

```text
left
center
right
```

------

## 22. source 字段

`source` 用于 image / icon 等资源型元素。

### 22.1 图片 source

```json
{
  "source": {
    "assetId": "asset_product_001"
  }
}
```

### 22.2 图片 source 直接带 URL

不推荐，但允许开发调试时使用：

```json
{
  "source": {
    "assetId": "asset_product_001",
    "url": "http://localhost:8000/files/assets/product_001.jpg"
  }
}
```

优先级：

```text
source.url > assets 中 assetId 对应 url
```

------

## 23. imageFill 字段

### 23.1 结构

```json
{
  "imageFill": {
    "mode": "fit"
  }
}
```

### 23.2 支持值

```text
fill
fit
```

| mode   | 说明                   |
| ------ | ---------------------- |
| `fill` | 类似 cover，填满容器   |
| `fit`  | 类似 contain，完整显示 |

### 23.3 默认策略

```text
头像 / Banner / 背景图：偏 fill
商品图 / Logo / 插图：偏 fit
```

------

## 24. icon source 字段

### 24.1 内置 SVG 图标

```json
{
  "type": "icon",
  "source": {
    "kind": "builtin_svg",
    "iconName": "search"
  }
}
```

### 24.2 字段说明

| 字段       | 类型   | 必填 | 说明                    |
| ---------- | ------ | ---- | ----------------------- |
| `kind`     | string | 是   | v0.1 支持 `builtin_svg` |
| `iconName` | string | 是   | 内置图标名              |

### 24.3 图标颜色

```json
{
  "style": {
    "color": "#999999"
  }
}
```

------

## 25. children 字段

### 25.1 嵌套对象方式

v0.1 推荐 children 直接嵌套 Element 对象：

```json
{
  "children": [
    {
      "id": "txt_001",
      "type": "text"
    }
  ]
}
```

原因：

```text
Renderer 递归渲染更简单
便于调试完整图层树
```

### 25.2 ID 引用方式

后续版本可以考虑：

```json
{
  "children": ["txt_001", "img_001"]
}
```

v0.1 不推荐作为主结构。

------

## 26. meta 字段

### 26.1 meta 示例

```json
{
  "meta": {
    "confidence": 0.88,
    "ocrConfidence": 0.94,
    "semanticType": "price",
    "correctionPolicy": "no_free_rewrite",
    "fallback": false,
    "sourceBBox": [24, 88, 200, 112],
    "qualityFlags": []
  }
}
```

### 26.2 meta 常用字段

| 字段               | 类型    | 说明                |
| ------------------ | ------- | ------------------- |
| `confidence`       | number  | 综合置信度          |
| `ocrConfidence`    | number  | OCR 置信度          |
| `semanticType`     | string  | 语义类型            |
| `correctionPolicy` | string  | 文本纠错策略        |
| `fallback`         | boolean | 是否为 fallback     |
| `reason`           | string  | fallback 或异常原因 |
| `sourceBBox`       | array   | 原图中的 bbox       |
| `qualityFlags`     | array   | 质量标记            |
| `componentSpec`    | object  | 后续组件化信息      |
| `stage`            | string  | 生成阶段            |
| `notes`            | string  | 调试说明            |

### 26.3 规则

Renderer 不应强依赖 meta。

meta 主要服务：

```text
调试
内部测试
后续优化
日志追踪
```

------

## 27. componentSpec 字段

### 27.1 结构

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

### 27.2 说明

`componentSpec` 只记录后续可组件化信息。

v0.1 Renderer 不根据该字段创建真正 Figma Component。

------

## 28. fallback 字段

### 28.1 fallback 标记

```json
{
  "meta": {
    "fallback": true,
    "reason": "complex_banner",
    "confidence": 0.52
  }
}
```

### 28.2 fallback 元素推荐结构

```json
{
  "id": "fallback_001",
  "type": "image",
  "role": "fallback_region",
  "name": "Fallback Region",
  "layout": {
    "x": 0,
    "y": 120,
    "width": 390,
    "height": 160
  },
  "source": {
    "assetId": "asset_fallback_001"
  },
  "meta": {
    "fallback": true,
    "reason": "complex_banner"
  }
}
```

------

## 29. Original Reference 字段

### 29.1 结构

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

### 29.2 规则

每份 DSL 推荐包含原图参考层。

默认：

```text
visible = false
opacity = 0.5
```

------

## 30. meta 顶层字段

顶层 `meta` 示例：

```json
{
  "meta": {
    "createdAt": "2026-05-16T00:00:00Z",
    "source": "png",
    "platformHint": "mobile",
    "qualityFlags": [],
    "fallbackCount": 2,
    "elementCount": 128,
    "promptVersion": "semantic_analyzer_v0.1",
    "model": "gpt-5.5"
  }
}
```

### 30.1 字段说明

| 字段            | 类型   | 说明                        |
| --------------- | ------ | --------------------------- |
| `createdAt`     | string | DSL 创建时间                |
| `source`        | string | 来源类型，v0.1 通常为 `png` |
| `platformHint`  | string | 页面类型提示                |
| `qualityFlags`  | array  | 质量风险                    |
| `fallbackCount` | number | fallback 数量               |
| `elementCount`  | number | 元素数量                    |
| `promptVersion` | string | 使用的提示词版本            |
| `model`         | string | 使用的主模型                |

------

## 31. platformHint 字段

### 31.1 支持值

```text
mobile
desktop_web
admin_dashboard
unknown
```

### 31.2 说明

`platformHint` 只作为辅助信息，不影响 Renderer 主逻辑。

------

## 32. qualityFlags 字段

### 32.1 支持值示例

```text
low_resolution
blurred
too_large
too_small
long_screenshot
low_contrast_text
many_fallback_regions
```

### 32.2 示例

```json
{
  "qualityFlags": ["blurred", "low_contrast_text"]
}
```

------

## 33. 完整最小 DSL 示例

```json
{
  "version": "0.1",
  "taskId": "task_001",
  "page": {
    "name": "home",
    "width": 390,
    "height": 844,
    "originalWidth": 780,
    "originalHeight": 1688,
    "scaleFactor": 2,
    "viewportHeight": 844,
    "isScrollable": false,
    "background": {
      "type": "color",
      "value": "#F7F8FA"
    },
    "safeArea": {
      "top": 44,
      "bottom": 34
    }
  },
  "assets": [
    {
      "assetId": "asset_original",
      "type": "image",
      "role": "original",
      "url": "http://localhost:8000/files/uploads/original.png",
      "format": "png",
      "width": 390,
      "height": 844,
      "storage": "local"
    }
  ],
  "root": {
    "id": "root",
    "type": "frame",
    "role": "screen",
    "name": "home",
    "layout": {
      "x": 0,
      "y": 0,
      "width": 390,
      "height": 844
    },
    "style": {
      "fill": "#F7F8FA"
    },
    "children": [
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
      },
      {
        "id": "title_001",
        "type": "text",
        "role": "title_text",
        "name": "Title Text",
        "layout": {
          "x": 164,
          "y": 54,
          "width": 62,
          "height": 22
        },
        "content": {
          "text": "首页"
        },
        "style": {
          "fontFamily": "PingFang SC",
          "fontSize": 17,
          "fontWeight": 600,
          "lineHeight": 22,
          "color": "#111111",
          "textAlign": "center"
        },
        "meta": {
          "confidence": 0.94,
          "ocrConfidence": 0.96
        }
      }
    ]
  },
  "meta": {
    "createdAt": "2026-05-16T00:00:00Z",
    "source": "png",
    "platformHint": "mobile",
    "qualityFlags": [],
    "fallbackCount": 0,
    "elementCount": 2,
    "promptVersion": "semantic_analyzer_v0.1",
    "model": "gpt-5.5"
  }
}
```

------

## 34. 字段默认值规则

当字段缺失时，允许按以下规则补默认值：

| 字段             | 默认值                        |
| ---------------- | ----------------------------- |
| `role`           | `"unknown"`                   |
| `name`           | 根据 `type` / `role` 自动生成 |
| `style`          | `{}`                          |
| `children`       | `[]`                          |
| `meta`           | `{}`                          |
| `opacity`        | `1`                           |
| `visible`        | `true`                        |
| `clipContent`    | `false`                       |
| `fontSize`       | `14`                          |
| `fontWeight`     | `400`                         |
| `color`          | `#000000`                     |
| `textAlign`      | `left`                        |
| `imageFill.mode` | `fill`                        |

------

## 35. 字段校验基本规则

DSL v0.1 至少需要校验：

```text
version 必须为 0.1
taskId 必须存在
page.width / page.height 必须大于 0
assets 必须为数组
root 必须存在
root.type 必须为 frame
所有 element.id 必须唯一
所有 element.type 必须合法
所有 layout.width / height 必须大于 0
text 元素必须有 content.text
image 元素必须有 source.assetId 或 source.url
icon 元素必须有 source.kind 和 iconName
children 必须是数组
```

------

## 36. Renderer 使用字段优先级

Renderer 使用字段的优先级：

```text
type
layout
style
content / source
children
role
meta
```

其中：

```text
type 决定创建什么 Figma 节点
layout 决定位置和大小
style 决定视觉样式
content/source 决定内容资源
children 决定层级
role/name 决定命名和辅助处理
meta 只做辅助
```

------

## 37. 版本结论

DSL v0.1 字段设计应保持克制。

核心目标是：

```text
让后端能生成
让 Renderer 能消费
让 Figma 能稳定创建图层
让复杂区域能 fallback
让错误能追踪
```

v0.1 不追求完整设计系统，不追求代码生成，不追求真正组件化。

一句话总结：

> DSL v0.1 是 PNG → Figma 可编辑稿的最小稳定协议。

```
这就是第五份文档：

**`03_DSL规范/02_DSL_v0.1_字段说明.md`**

下一份建议继续输出：

**`03_DSL规范/12_DSL_v0.1_完整示例.md`**
```