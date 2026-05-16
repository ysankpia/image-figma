下面继续输出第十三份核心文档：

**`10_开发计划与任务拆分/10_验收标准_v0.1.md`**

~~~markdown
# MVP 验收标准 v0.1

文档名称：MVP 验收标准  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 验收文档  
适用阶段：第一版核心链路开发 / 联调 / 内测  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于定义 Image-to-Figma Design v0.1 的 MVP 验收标准。

v0.1 的验收目标不是判断产品是否已经商业化成熟，而是判断第一版核心链路是否成立：

```text
单张 PNG 上传
→ 后端识别
→ 生成 DSL v0.1
→ Figma 插件渲染
→ Figma 可编辑设计稿
~~~

只要这条链路稳定跑通，并且生成结果达到基础可用水平，即可认为 MVP v0.1 验收通过。

------

## 2. 验收总原则

v0.1 验收围绕四个关键词：

```text
快
像
可编辑
稳定
```

解释：

```text
快：生成速度在可接受范围内
像：视觉整体接近原始 PNG
可编辑：主要文字、基础形状、主要结构可编辑
稳定：复杂区域可以 fallback，但不能整页崩溃
```

v0.1 不以以下内容作为验收目标：

```text
100% 可编辑
100% 像素级一致
100% 组件化
100% Auto Layout
100% 图标矢量化
100% 代码生成
完整商业化能力
```

------

## 3. 核心链路验收

### 3.1 必须跑通的主链路

必须能完成：

```text
打开 Figma 插件
↓
上传 PNG
↓
预览确认
↓
点击开始生成
↓
后端创建 taskId
↓
后端生成 DSL v0.1
↓
插件获取 DSL
↓
Renderer 渲染 Figma 图层
↓
Figma 当前画布出现完整页面 Frame
```

### 3.2 通过标准

```text
1. 插件可以正常打开
2. PNG 可以成功上传
3. 后端可以返回 taskId
4. 任务状态可以查询
5. 任务完成后可以获取 DSL
6. DSL 可以被 Renderer 消费
7. Figma 中生成 root Frame
8. root Frame 尺寸与页面尺寸一致
9. 生成结果不是空白
10. 插件显示生成完成
```

### 3.3 不通过标准

以下任一情况出现，即主链路不通过：

```text
插件无法打开
PNG 无法上传
后端无法创建任务
任务无法完成
无法获取 DSL
DSL 无法被 Renderer 解析
Figma 无法生成 root Frame
生成结果为空白
生成过程中插件崩溃
生成过程中 Figma 卡死
```

------

## 4. 输入验收标准

### 4.1 支持输入

v0.1 必须支持：

```text
PNG
单张上传
```

### 4.2 必须拒绝

以下输入必须拒绝或提示错误：

```text
非 PNG 文件
损坏图片
空文件
超过硬限制大小的图片
```

### 4.3 建议提示但允许继续

以下情况可以提示风险，但不强制拒绝：

```text
图片较模糊
图片尺寸较大
图片尺寸较小
长截图
非典型移动端尺寸
```

### 4.4 验收标准

```text
1. PNG 可以正常读取尺寸和大小
2. 非 PNG 有明确错误提示
3. 图片过大有明确错误提示
4. 低质量图片有风险提示或后端 qualityFlags
5. 插件不会因异常图片崩溃
```

------

## 5. 后端 API 验收标准

### 5.1 必须可用接口

```text
GET  /api/health
POST /api/upload
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/assets/{assetId}
```

### 5.2 health 接口

通过标准：

```text
返回 success = true
返回 status = ok
返回 api / service version
```

### 5.3 upload 接口

通过标准：

```text
可以接收 multipart PNG
可以保存原图
可以创建 taskId
可以返回图片基础信息
非 PNG 返回 INVALID_IMAGE_FORMAT
图片过大返回 IMAGE_TOO_LARGE
```

### 5.4 task 状态接口

通过标准：

```text
可以通过 taskId 查询状态
状态包含 pending / uploaded / processing / completed / failed
completed 时返回 dslUrl
failed 时返回 error.code 和 error.message
```

### 5.5 DSL 接口

通过标准：

```text
completed 任务可以获取 DSL
未完成任务返回 TASK_NOT_COMPLETED
不存在任务返回 TASK_NOT_FOUND
DSL 缺失返回 DSL_NOT_FOUND
```

### 5.6 Asset 接口

通过标准：

```text
assetId 可以查询到资源信息
asset.url 可以被 Figma 插件访问
不存在 asset 返回 ASSET_NOT_FOUND
```

------

## 6. DSL v0.1 验收标准

### 6.1 顶层结构

DSL 必须包含：

```text
version
taskId
page
assets
root
meta
```

### 6.2 version

必须满足：

```text
version = "0.1"
```

### 6.3 page

必须满足：

```text
page.width > 0
page.height > 0
page.name 存在或可默认生成
scaleFactor 存在或默认为 1
```

### 6.4 assets

必须满足：

```text
assets 是数组
每个 asset 有 assetId
每个图片 asset 有 url
每个图片 asset 有 format
assetId 唯一
```

### 6.5 root

必须满足：

```text
root 存在
root.type = frame
root.layout 存在
root.layout.width = page.width
root.layout.height = page.height
root.children 是数组
```

### 6.6 Element

每个 Element 必须满足：

```text
id 存在且唯一
type 属于 frame / group / text / shape / image / icon / line
layout 存在
layout.width > 0
layout.height > 0
children 如果存在必须为数组
```

### 6.7 Text 元素

必须满足：

```text
type = text
content.text 存在
content.text 为 string
style.fontSize 可缺省
style.color 可缺省
```

### 6.8 Image 元素

必须满足：

```text
type = image
source.assetId 或 source.url 至少一个存在
如果使用 assetId，必须能在 assets 中找到
```

### 6.9 Icon 元素

必须满足：

```text
type = icon
source.kind 存在
source.iconName 存在
iconName 在内置图标库中存在，或允许跳过并记录 warning
```

### 6.10 验收结论

DSL 验收通过条件：

```text
1. 示例 DSL 能通过 Schema 校验
2. 真实 PNG 生成的 DSL 能通过基础校验
3. Renderer 能消费 DSL
4. DSL 错误能返回明确错误信息
```

------

## 7. Renderer 验收标准

### 7.1 必须支持的元素

Renderer v0.1 必须能渲染：

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

### 7.2 Root Frame

通过标准：

```text
能创建 root Frame
root Frame 尺寸正确
root Frame 名称可读
root Frame 背景正确
渲染完成后选中 root Frame
视图定位到 root Frame
```

### 7.3 Text

通过标准：

```text
文字能显示
文字可编辑
字体大小基本正确
颜色基本正确
行高基本正确
对齐方式基本正确
中文可以显示
```

不要求：

```text
字体 100% 完全一致
字距完全一致
特殊字体完全还原
```

### 7.4 Shape

通过标准：

```text
矩形能显示
圆角能显示
纯色填充能显示
描边能显示
透明度能显示
```

不要求：

```text
复杂不规则 Shape 完美还原
复杂多层光效
```

### 7.5 Image

通过标准：

```text
图片 URL 能加载
图片能显示在正确位置
图片尺寸基本正确
圆角图片能显示
fallback 图片能显示
原图参考层能加载
```

### 7.6 Icon

通过标准：

```text
search / back / close / home / user / cart 等基础图标能显示
基础单色 SVG 图标能定位和缩放
icon 找不到时不导致整页失败
```

### 7.7 Line

通过标准：

```text
分割线能显示
0.5px / 1px 细线基本可用
颜色正确
```

### 7.8 错误处理

通过标准：

```text
单个元素失败不会导致整页失败
图片加载失败能记录 warning
字体加载失败能回退默认字体
不支持 type 能跳过并记录 warning
Renderer 能返回 RenderResult
```

------

## 8. Figma 插件验收标准

### 8.1 页面状态

v0.1 插件必须包含：

```text
UploadView
PreviewView
ProgressView
DoneView
ErrorView
```

### 8.2 UploadView

通过标准：

```text
可以选择 PNG
可以提示仅支持 PNG
可以进入 PreviewView
```

### 8.3 PreviewView

通过标准：

```text
能显示图片预览
能显示文件名
能显示图片尺寸
能显示文件大小
能点击开始生成
能点击重新上传
```

### 8.4 ProgressView

通过标准：

```text
显示进度条
显示非技术化状态文案
不会暴露 OCR / DSL / AI 等技术细节
```

### 8.5 DoneView

通过标准：

```text
生成成功后显示完成提示
用户能在 Figma 画布中看到结果
```

### 8.6 ErrorView

通过标准：

```text
错误时显示友好文案
至少支持重新上传
非 PNG / 图片过大 / 上传失败 / 生成失败有不同提示
```

------

## 9. 后端识别管线验收标准

### 9.1 图片预处理

通过标准：

```text
能读取 PNG 尺寸
能计算 scaleFactor
能记录 originalWidth / originalHeight
能生成目标 Figma width / height
能输出 qualityFlags
```

### 9.2 OCR

通过标准：

```text
能识别主要文字
能返回 bbox
能返回 confidence
能输出标准化 text blocks
```

### 9.3 AI / CV 分析

通过标准：

```text
能识别基础 UI 区域
能辅助判断元素归属
能输出结构化 JSON 或中间结果
异常 JSON 能进行一次修复或返回错误
```

### 9.4 DSL Builder

通过标准：

```text
能把 OCR / AI / asset 结果组装为 DSL
能生成 Text 元素
能生成基础 Frame / Shape
能生成 Image 元素
能生成 Fallback 元素
能生成 Original Reference 元素
```

### 9.5 DSL Validate / Repair

通过标准：

```text
能校验 DSL
能补默认值
能修复轻微字段问题
严重错误能标记任务失败
```

------

## 10. 图片资产验收标准

### 10.1 必须支持的资产

```text
原始 PNG
商品图
头像
Banner
Logo
fallback 区域
```

### 10.2 资产字段

每个 asset 必须有：

```text
assetId
url
format
width
height
```

### 10.3 开发阶段 URL

通过标准：

```text
本地 URL 可访问
Figma 插件能 fetch
URL 能写入 DSL assets
```

### 10.4 图片裁切

通过标准：

```text
裁切区域位置基本正确
裁切图片无明显丢边
复杂区域能整块 fallback
assetId 与元素引用一致
```

------

## 11. Original PNG Reference 验收标准

每个生成页面必须包含隐藏原图参考层。

通过标准：

```text
图层名为 Original PNG Reference
类型为 image
铺满 root Frame
默认 visible = false
opacity = 0.5
位于底层
用户可以手动打开对比
```

------

## 12. Fallback 验收标准

### 12.1 必须支持 fallback

Fallback 是 v0.1 的关键质量策略。

通过标准：

```text
复杂 Banner 可以 fallback
复杂图表可以 fallback
复杂插图可以 fallback
复杂多色图标可以 fallback
局部 fallback 不影响整页生成
fallback 元素能显示在正确位置
fallback 元素在 meta 中记录 reason
```

### 12.2 不通过情况

```text
局部复杂区域导致整页失败
fallback 图片无法加载且没有 warning
fallback 区域位置严重错误
```

------

## 13. 视觉还原验收标准

### 13.1 总体要求

v0.1 不要求像素级一致，但要求整体视觉接近。

检查项：

```text
页面尺寸
整体布局
主要模块位置
主要文字位置
主要图片位置
背景颜色
卡片圆角
按钮样式
TabBar / Header 位置
```

### 13.2 可接受偏差

v0.1 可接受：

```text
轻微字号差异
轻微行高差异
轻微颜色偏差
轻微坐标偏差
复杂区域图片 fallback
部分图标不完全一致
```

### 13.3 不可接受问题

```text
页面整体错位
主要模块缺失
大面积空白
主要文字缺失
主要图片缺失
文字严重错位
图层遮挡严重
TabBar / Header 位置严重错误
```

------

## 14. 可编辑性验收标准

### 14.1 必须可编辑

以下内容应尽量可编辑：

```text
标题文字
按钮文字
列表文字
价格文字
表单文字
TabBar 文字
普通段落文字
基础形状
按钮背景
卡片背景
```

### 14.2 可以不可编辑

以下内容可以作为图片保留：

```text
复杂 Banner
复杂插图
复杂图表
复杂 Logo
复杂多色图标
状态栏
复杂光效背景
```

### 14.3 通过标准

```text
主要文字大部分可编辑
主要基础形状可编辑
复杂区域 fallback 合理
用户能对生成稿进行基础修改
```

------

## 15. 性能验收标准

### 15.1 建议目标

```text
简单移动端页面：15～30 秒
中等复杂页面：30～60 秒
复杂页面：60～90 秒
```

### 15.2 超时标准

如果任务超过：

```text
120 秒
```

应返回超时或失败提示，而不是无限等待。

### 15.3 性能不通过情况

```text
简单页面经常超过 60 秒
中等页面经常超过 120 秒
插件长时间无响应
Figma 渲染导致明显卡死
AI 多轮调用导致不可接受等待
```

------

## 16. 错误处理验收标准

### 16.1 用户侧错误

必须有友好提示：

```text
当前仅支持 PNG 格式
图片过大，请压缩后重新上传
图片上传失败，请检查网络后重试
图片识别失败，请换一张更清晰的 PNG 截图
生成失败，请重试或重新上传
```

### 16.2 内部错误

必须记录：

```text
taskId
stage
errorCode
message
createdAt
必要上下文
```

### 16.3 错误码

必须至少支持：

```text
INVALID_IMAGE_FORMAT
IMAGE_TOO_LARGE
UPLOAD_FAILED
OCR_FAILED
AI_ANALYZE_FAILED
DSL_BUILD_FAILED
DSL_SCHEMA_ERROR
ASSET_NOT_FOUND
ASSET_LOAD_FAILED
FIGMA_RENDER_FAILED
UNKNOWN_ERROR
```

------

## 17. 日志验收标准

### 17.1 后端日志

必须记录：

```text
任务创建
上传成功
处理开始
OCR 结果摘要
AI 调用摘要
DSL 生成结果
DSL 校验结果
资产裁切结果
任务完成 / 失败
```

### 17.2 Renderer 日志

必须记录：

```text
renderedElementCount
skippedElementCount
warnings
asset load errors
font load errors
unsupported element type
```

### 17.3 模型调用日志

至少记录：

```text
model
promptVersion
durationMs
inputSummary
outputSummary
error
```

不强制保存完整原始输出，开发阶段可保存，后续再脱敏。

------

## 18. 测试样例验收

### 18.1 必测样例

至少准备：

```text
1. 简单 App 首页
2. 小程序首页
3. 商品列表页
4. 商品详情页
5. 登录 / 表单页
6. 带底部 TabBar 页面
7. 弹窗页面
8. 长截图页面
9. 简单后台页面
```

### 18.2 每张样例检查

```text
能否成功上传
能否生成 DSL
DSL 是否通过校验
Figma 是否生成 root Frame
主要文字是否可编辑
主要图片是否显示
布局是否接近
复杂区域是否 fallback
是否有隐藏原图层
生成时间是否可接受
失败时是否有日志
```

------

## 19. MVP 验收等级

### 19.1 P0 必须通过

```text
主链路跑通
DSL 能生成
Renderer 能渲染
Text / Shape / Image 可用
图片资产可加载
错误日志可查
```

### 19.2 P1 应该通过

```text
Icon 基础可用
Line 可用
Original Reference 可用
Fallback 可用
基础阴影 / 圆角 / 描边可用
```

### 19.3 P2 可后续优化

```text
复杂渐变
复杂阴影
SVG 精准改色
更多图标
更精细 OCR 纠错
更好视觉评分
```

------

## 20. 不作为 v0.1 验收项

以下内容不作为 v0.1 验收项：

```text
代码生成
真正 Figma Component
Auto Layout
一键组件化
批量上传
历史记录
质量报告
差异热力图
多模型对比
完整评分看板
账号系统
额度系统
支付系统
Web 深度支持
复杂图表结构化
复杂后台表格完美识别
```

------

## 21. 最终验收结论标准

v0.1 MVP 可通过验收，当满足：

```text
1. 主链路能稳定跑通
2. 8～10 张核心样例中，大部分能成功生成
3. 简单移动端页面生成速度可接受
4. 主要文字可编辑
5. 主要图片能正确回填
6. 基础 UI 结构能表达
7. 复杂区域能 fallback
8. 失败时能定位原因
9. 插件 UI 不复杂但可用
10. 后续扩展方向清晰
```

不要求第一版达到商业化完美水平。

------

## 22. 版本结论

v0.1 的验收核心是：

```text
PNG → DSL → Figma 可编辑稿
```

只要这条链路可用，并且生成效果达到基础可编辑、视觉接近、速度可接受，就可以认为 MVP 验收通过。

v0.1 验收不是终点，而是证明项目方向可继续投入的第一道关口。

```
这就是第十三份文档：

**`10_开发计划与任务拆分/10_验收标准_v0.1.md`**

到这里，第一批最关键的文档已经基本齐了：

```text
01_项目总览/03_一期MVP范围_v0.1.md
01_项目总览/04_一期不做事项_v0.1.md
02_PRD产品需求文档/01_PRD总文档_v0.1.md
03_DSL规范/01_DSL_v0.1_设计原则.md
03_DSL规范/02_DSL_v0.1_字段说明.md
03_DSL规范/12_DSL_v0.1_完整示例.md
05_Image-to-Figma-Renderer渲染包/01_渲染包职责边界_v0.1.md
05_Image-to-Figma-Renderer渲染包/02_渲染流程_v0.1.md
04_技术架构文档/01_整体技术架构_v0.1.md
06_Figma插件设计文档/01_插件MVP交互流程_v0.1.md
07_后端接口文档/01_API总览_v0.1.md
10_开发计划与任务拆分/01_MVP开发里程碑_v0.1.md
10_开发计划与任务拆分/10_验收标准_v0.1.md
```

下一步建议补两份更偏执行的：

```text
10_开发计划与任务拆分/03_DSL与Schema任务_v0.1.md
10_开发计划与任务拆分/04_Renderer渲染包任务_v0.1.md
```