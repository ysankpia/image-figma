# Codia VisualElement Schema(逆向参考)

> 来源:逆向自 Codia 官方 npm 包 `figma-image-to-design@0.0.3`(`DesignGenerator.generateFromVisualElement`)的 `dist/index.js`,以及 `developer.codia.ai` 的 `image_to_design` 接口文档。
> 用途:作为我们 Go VisualTree → DSL 链路的**目标 schema 对照**。这是参考资料,不是运行时合同。
> 零成本获得:不消耗 Codia API 额度。研究产物在 `backend/tmp/codia_study/`(未追踪)。

## 接口

```text
POST https://api.codia.ai/v1/open/image_to_design
Header: Authorization: Bearer {key}
Header: Content-Type: application/json
Body:   { "image_url": "公网可访问的图片URL" }   # 注意:要URL,不接受上传文件/base64
Resp:   { "code": 0, "message": "ok", "data": { "visualElement": {...} } }
错误码: 401 key错误 / 402 额度不足 / 429 频率超限
```

额度:当前 key 每月 5 次免费调用。**留作最终对照校准用,不要用于探索。**

## 核心结论(为什么这份 schema 重要)

1. **节点类型和我们 Go VisualTree 几乎完全一致**:Codia 用 `Body / Layer / Text / Image / Component`,我们用 `Body / Layer / Text / Image`。我们坚持不引入 Button/Card/Nav 语义节点的方向,和商业产品收敛一致。差距只多一个 `Component`。
2. **我们最大的空白是 `style` 和 `positionType`**,不是节点抽象。
3. **Codia 也分 `Absolute / Flex / Normal` 三种定位**,不强求一切都是 Auto Layout。拿不准就 Absolute 绝对定位,有把握才升级 Flex。可渐进式演进。

## VisualElement 结构

```text
VisualElement {
  id
  elementType        // Body | Layer | Text | Image | Component
  elementName / name

  layout {
    positionType     // Absolute | Flex | Normal
    coord {x, y}
    orginCoord
    width, height
    widthSpec, heightSpec        // FIXED | FILL | AUTO
    // --- Flex 专属 ---
    flexDirection / layoutMode    // HORIZONTAL | VERTICAL
    gap / itemSpacing
    padding / paddingValues
    primaryAxisAlignItems         // MIN | MAX | CENTER | SPACE_BETWEEN
    counterAxisAlignItems         // MIN | MAX | CENTER | STRETCH
    primaryAxisSizingMode         // FIXED | AUTO
    counterAxisSizingMode         // FIXED | AUTO
    constraints
  }

  style {                          // ← 我们 Go 当前完全空白的部分
    backgroundColor / background / backgrounds / fills
    border { borderColor, borderWidth, borderConfig }
    borderRadius / cornerRadius {
      topLeftRadius, topRightRadius, bottomLeftRadius, bottomRightRadius
    }
    opacity
    rotation
    strokes, strokeWeight
    color { rgb{r,g,b} | hex | hexCode }   // 颜色双表达
  }

  // --- Text 节点专属 ---
  text / textConfig {
    textValue / characters
    fontFamily
    fontSize
    fontWeight
    fontStyle        // Thin | Light | Regular | Medium | Semibold | Bold
    lineHeight
    textAlign        // LEFT | CENTER | RIGHT
    textAlignHorizontal, textAlignVertical
    textDecoration   // UNDERLINE | STRIKETHROUGH
    leadingTrim, textAutoResize
    color / textColor
  }

  // --- Image 节点专属 ---
  content { imageUrl, imageSource }

  // --- Component 节点专属 ---
  componentSpec { componentId, componentName, componentProperties }

  // --- 感知元数据 ---
  processingMeta { detectionScore, textDetection, textExtraction, ... }

  children[]    // 递归嵌套
}
```

## 我们的差距清单(VisualTree 当前 vs Codia)

| 维度 | 我们 Go 现状 | Codia | 差距 |
|------|-------------|-------|------|
| 节点类型 | Body/Layer/Text/Image | +Component | 基本对齐 |
| 定位 | bbox 绝对坐标 | Absolute/Flex/Normal | 缺 Flex 升级(可后做) |
| 样式 | 仅 BackgroundRef | 完整 style | **最大空白** |
| 颜色 | meanColor(已有数据源) | rgb+hex | 数据已有,缺结构 |
| 圆角/边框/阴影 | 无 | 完整 | **空白,但可从像素测量** |
| 字体 | 仅 text 文本 | 字号/字重/行高/对齐 | **空白,OCR+测量可补** |

## 关键判断:样式是"测量"出来的,不是"猜"出来的

`style` 里所有字段(背景色、圆角、边框、字号、字重)都能从 M29.0 的像素证据 + OCR 直接**测量**得到,属于确定性工作,不涉及视觉感知的猜测。这是我们离 Codia 最近、最容易见效的一环。
