# Codia 真实输出逆向(.fig 解析)

> 来源:用腾讯动漫会员页截图(665×1440)在 Figma 跑 Codia 插件转换,导出 `.fig`,用 Evan Wallace 官方解析器(madebyevan.com/figma/fig-file-parser)解成 JSON。原始样本:`docs/reference/codia-samples/tencent-comic-018.canvas.json`(926KB)。
> 这是 Codia 输出的**最真实形态**,比逆向 SDK schema 更可信。零 API 额度。

## .fig 文件格式(供本地解析参考)

```
.fig = ZIP 容器:
  canvas.fig   ← 主数据,头 "fig-kiwi" + uint32版本(101) + 段[uint32 len][压缩数据]
                 seg0 = kiwi schema(deflate/inflateRaw, 615个类型定义)
                 seg1 = 节点数据(新版用 zstd 压缩,魔数 28 b5 2f fd,旧版用 deflate)
  images/      ← 切图资产(本样本 18 张)
  meta.json    ← 明文元信息
  thumbnail.png
```
解析最省事的路:Evan Wallace 在线解析器直接出 JSON(已验证)。本地代码可用 `fig-kiwi` 思路:archive 拆段 → kiwi-schema 解码,但新版数据段是 zstd,需 zstd 解压而非 pako。

## Codia 节点树真相(决定性发现)

**只用 4 种节点类型**(和我们 Go VisualTree 几乎同构,证明不引入语义节点的方向正确):
```
FRAME              容器/分组(命名一律 "Groups";可点组合命名 "Button")
TEXT               文字(节点名=文字内容)
ROUNDED_RECTANGLE  图片(名"Image")/ 背景色块(名"Background")
```
本样本统计:152 节点,最大深度 9,ROUNDED_RECTANGLE 58 / TEXT 48 / FRAME 43。
**没有 Card/Nav/List/Carousel/Search 等语义节点。**

**命名规则极机械(证明 Codia 不做语义理解,纯几何/视觉):**
- 容器=`Groups`,图片=`Image`,背景块=`Background`,文字=文字内容本身,可点组合=`Button`
- `pluginData.value` 暴露内部节点ID格式:`类型_x_y_序号`(如 `TextView_253_858_145`、`bg_Button_244_10_140`)→ 内部表示就是【带类型+坐标的扁平节点】,按坐标包含组装成树

**层级=空间聚类,不是语义识别:**
三个并排价格套餐 → 没识别成"价格卡",而是因空间并排+各自内部元素聚拢 → 嵌套成 `Groups` 里的三个 `Groups`。

**Button 模式是固定几何套路:**
```
FRAME "Button" (fillPaints透明, 纯容器)
  ├ TEXT "确认协议并支付"
  └ ROUNDED_RECTANGLE "Background" (圆角色块)
```
= "一个文字 + 一个包住它的圆角色块" → 命名 Button。纯几何(文字被色块包含),非理解。这正是 Python M29.6 想用手写规则做的事——Codia 证明方向对,只是要做干净。

## 样式字段精确格式(填我们 Go 空白的 Style)

```
TEXT:  fontSize:30  fontName:{family:"PingFang SC",style:"Medium"}
       lineHeight:{value:100,units:"PERCENT"}  letterSpacing
       fillPaints:[{type:"SOLID",color:{r,g,b,a 0~1},opacity}]  ← 文字色
       textData.characters = 文字  transform.m02/m12 = x/y
ROUNDED_RECTANGLE(Background):
       rectangleTopLeftCornerRadius:19 (四角独立, rectangleCornerRadiiIndependent)
       fillPaints(填充) strokePaints(描边) borderTop/Bottom/Left/RightWeight
       size:{x,y}  transform:{m02=x, m12=y}
FRAME(Button/Groups):
       fillPaints opacity:0 = 透明容器
坐标系: transform 是2x3仿射矩阵, m02=x偏移 m12=y偏移(相对父节点)
颜色: rgba 都是 0~1 浮点
```

## 对项目的结论

Codia 没有神秘大模型。它的 pipeline = **感知(切图Image/Background块 + OCR文字 + 元件定位)→ 编译(空间包含+聚类成Groups嵌套树,无语义)→ 机械命名 → 样式从像素测量**。我们和它的差距不是"缺AI",而是**编译层(干净的空间聚类)没做对**。M29.0已能出块、OCR已出文字,缺的就是中间这步。详见 [[image-figma-root-cause-and-route]]、[[codia-visualelement-schema-source]]。
