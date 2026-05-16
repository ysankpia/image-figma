下面继续输出第三份核心文档：

**`02_PRD产品需求文档/01_PRD总文档_v0.1.md`**

~~~markdown
# PRD 总文档 v0.1

文档名称：PRD 产品需求文档  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 开发准备版  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 项目概述

Image-to-Figma Design 是一个将 PNG 截图 / 设计稿转换为 Figma 可编辑设计稿的工具。

用户上传一张 PNG 图片后，系统通过 OCR、图像识别、AI 结构分析和 DSL 渲染，将图片中的 UI 页面还原为 Figma 画布中的可编辑图层。

一期 MVP 的目标不是做完整商业化平台，而是验证核心链路：

```text
PNG 上传
→ 后端识别
→ 生成 DSL v0.1
→ Figma 插件渲染
→ Figma 可编辑设计稿
~~~

------

## 2. 产品目标

### 2.1 一期核心目标

一期 MVP 只关注四个目标：

```text
快
像
可编辑
稳定生成
```

解释：

```text
快：不能因为过度分析导致用户等待过久
像：生成结果整体视觉要接近原 PNG
可编辑：主要文字、基础形状、主要结构应可编辑
稳定生成：复杂区域可以 fallback，但不能整页崩溃
```

------

### 2.2 一期不追求的目标

一期不追求：

```text
100% 可编辑
100% 组件化
100% Auto Layout
100% 代码生成
100% 图标矢量化
100% 复杂图表结构化
100% 商业化闭环
```

一期更强调：

```text
主要内容可编辑
复杂内容图片兜底
整体视觉接近
生成速度可接受
```

------

## 3. 背景与问题

### 3.1 用户痛点

设计师、前端开发者、独立开发者经常遇到以下问题：

```text
只有 PNG / 截图，没有原始 Figma 文件
需要复刻某个 App / 小程序页面
需要把图片稿转为可编辑稿
需要快速搭建页面结构
需要从截图中提取可编辑文字和基础图层
```

手动重画成本高，尤其是：

```text
文字多
卡片多
列表多
图标多
页面结构复杂
```

------

### 3.2 现有方案问题

传统方式：

```text
直接把 PNG 拖入 Figma
```

缺点：

```text
不可编辑
不能改文字
不能改颜色
不能复用结构
不能继续设计
```

完全人工重画：

```text
耗时长
成本高
容易出错
```

竞品工具如 Codia 已经证明“图片转设计稿”方向可行，但本项目需要结合自身需求，做一个可控的、可迭代的 Image-to-Figma Design 链路。

------

## 4. 目标用户

一期主要面向：

```text
设计师
UI 设计工作室
前端开发者
独立开发者
产品原型人员
```

------

## 5. 典型使用场景

### 5.1 设计稿复刻

用户有一张移动端页面 PNG，希望快速变成 Figma 可编辑稿。

流程：

```text
上传 PNG
等待生成
在 Figma 画布中看到可编辑页面
修改文字 / 图片 / 颜色
```

------

### 5.2 App / 小程序截图还原

用户看到一个 App / 小程序页面，希望将截图转为可编辑设计稿，用于参考、二次设计或快速搭建页面结构。

------

### 5.3 前端辅助设计

前端开发者没有原始设计文件，只有截图，希望快速生成一个可参考的 Figma 页面，用于拆解布局和样式。

------

### 5.4 内部批量测试

开发阶段，团队使用一批 PNG 测试图验证识别效果，查看 DSL、错误日志、Figma 渲染结果，持续优化识别规则和渲染器。

------

## 6. 一期 MVP 范围

一期 MVP 只做单张 PNG 到 Figma 可编辑稿的核心链路。

### 6.1 一期支持

```text
单张 PNG 上传
图片预览确认
后端创建识别任务
OCR 文字识别
AI / CV 页面结构分析
图片资产裁切
生成 DSL v0.1
DSL 基础校验
Figma 插件渲染
生成 Figma 可编辑图层
隐藏原 PNG 参考层
复杂区域 fallback
基础错误提示和日志
```

------

### 6.2 一期不支持

```text
批量上传
历史记录
最近任务
代码生成
真正 Figma Component
Auto Layout
一键组件化
插件内质量报告
插件内原图对比
差异热力图
复杂图表结构化
复杂后台表格完美识别
用户账号系统
支付系统
额度系统
```

详细不做事项见：

```text
01_项目总览/04_一期不做事项_v0.1.md
```

------

## 7. 产品核心流程

### 7.1 用户侧流程

```text
打开 Figma 插件
↓
上传 PNG
↓
查看图片预览和基础信息
↓
点击开始生成
↓
等待处理中
↓
Figma 画布生成可编辑设计稿
↓
查看生成结果
```

------

### 7.2 系统侧流程

```text
插件上传 PNG
↓
后端保存原图
↓
创建 taskId
↓
图片预处理
↓
OCR 识别文字
↓
CV / AI 分析结构
↓
裁切图片资产
↓
生成 DSL v0.1
↓
DSL 校验 / 基础修复
↓
插件获取 DSL
↓
Renderer 渲染 Figma 图层
↓
完成
```

------

## 8. 插件端需求

### 8.1 插件页面

一期插件页面只包含：

```text
UploadView
PreviewView
ProgressView
DoneView
ErrorView
```

不做复杂插件 UI。

------

### 8.2 UploadView

功能：

```text
用户上传 PNG
显示基础说明
校验文件格式
```

基础文案：

```text
支持上传 App / 小程序移动端 PNG 截图。
建议上传清晰、高保真图片。
```

------

### 8.3 PreviewView

功能：

```text
展示图片预览
展示文件名
展示图片尺寸
展示文件大小
展示格式校验结果
展示风险提示
```

用户操作：

```text
开始生成
重新上传
```

风险提示包括：

```text
图片过大
图片过小
图片可能模糊
图片可能不是推荐尺寸
```

风险提示不阻止用户继续。

------

### 8.4 ProgressView

功能：

```text
显示简单进度条
显示非技术化阶段文案
```

允许展示：

```text
上传中
处理中
生成中
正在写入 Figma
```

不展示：

```text
OCR
DSL
AI 分析
Schema 校验
模型调用
```

------

### 8.5 DoneView

功能：

```text
提示生成完成
提示用户到 Figma 画布查看
```

一期不放复杂按钮。

建议文案：

```text
生成完成，请在当前 Figma 画布中查看结果。
```

------

### 8.6 ErrorView

功能：

```text
显示友好错误原因
允许重新上传
必要时允许重试
```

用户侧错误文案示例：

```text
图片上传失败，请检查网络后重试。
当前仅支持 PNG 格式。
图片过大，请压缩后重新上传。
识别失败，请换一张更清晰的截图。
生成失败，请重试。
```

开发阶段可以通过开发版 UI、后端日志或内部后台查看详细错误。

------

## 9. 后端需求

### 9.1 上传与任务

后端需要支持：

```text
接收 PNG 文件
生成 taskId
保存原图
创建任务记录
返回任务状态
```

------

### 9.2 图片预处理

后端需要处理：

```text
读取图片尺寸
判断图片格式
判断图片大小
计算 scaleFactor
标准化输出尺寸
检测低质量风险
```

------

### 9.3 OCR 文字识别

一期采用：

```text
PaddleOCR + 大模型辅助纠错
```

OCR 负责：

```text
识别文字内容
返回 bbox
返回置信度
返回行 / 段落信息
```

大模型辅助：

```text
文本纠错
文本角色判断
文本归属判断
```

数字类文本采用保守策略：

```text
价格
手机号
订单号
日期
百分比
```

不允许大模型自由改写。

------

### 9.4 AI / CV 结构分析

AI / CV 负责：

```text
识别页面基础区域
识别常见 UI 结构
判断元素归属关系
判断图标候选
辅助生成 DSL 所需结构
```

一期重点结构：

```text
Navigation Bar
SearchBar
TabBar
Button
Card
ListItem
FormItem
Modal
Image
Text
Icon
```

但这些结构不作为 DSL 独立 type，而是作为 role。

------

### 9.5 图片资产裁切

后端需要裁切：

```text
原图参考层
头像
商品图
Banner
Logo
插图
复杂 fallback 区域
复杂图标 fallback 区域
```

裁切策略：

```text
默认外扩 1～2px
商品图可外扩 2～4px
插图 / 运营图可外扩 4～8px
裁切后保存 assetId
```

开发阶段使用本地文件 URL。
生产阶段切换 OSS / 对象存储 + 签名 URL。

------

### 9.6 DSL 生成

后端最终输出：

```text
DSL v0.1
```

DSL 必须包含：

```text
page
assets
root
meta
```

root 内包含完整图层树。

------

### 9.7 错误日志

后端必须记录：

```text
taskId
失败阶段
错误码
错误信息
必要上下文
时间
```

常见错误码：

```text
UPLOAD_FAILED
INVALID_IMAGE_FORMAT
IMAGE_TOO_LARGE
OCR_FAILED
AI_ANALYZE_FAILED
DSL_BUILD_FAILED
DSL_SCHEMA_ERROR
ASSET_MISSING
FIGMA_RENDER_FAILED
```

------

## 10. DSL v0.1 需求

### 10.1 DSL 作用

DSL 是后端和 Figma 插件之间的数据协议。

后端负责：

```text
PNG → DSL
```

Figma Renderer 负责：

```text
DSL → Figma 图层
```

------

### 10.2 DSL 核心结构

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

------

### 10.3 DSL 元素类型

一期只支持：

```text
frame
group
text
shape
image
icon
line
```

所有复杂组件都通过 role 表示：

```text
button
card
search_bar
tab_bar
list_item
form_item
modal
```

------

### 10.4 DSL 布局原则

一期统一使用绝对定位：

```text
x
y
width
height
```

不做 Auto Layout。

------

### 10.5 DSL 样式范围

一期支持：

```text
fill
opacity
radius
stroke
shadow
gradient
clipContent
visible
```

------

## 11. Image-to-Figma Renderer 需求

### 11.1 Renderer 作用

Renderer 是 Figma 插件内的核心渲染包，负责：

```text
读取 DSL v0.1
创建 Figma 图层
应用布局和样式
插入图片
插入文本
插入图标
处理 fallback
```

------

### 11.2 Renderer 不负责

Renderer 不做：

```text
OCR
AI 分析
图片裁切
DSL 生成
质量评分
代码生成
组件化
Auto Layout 推断
```

------

### 11.3 Renderer 支持元素

一期 Renderer 支持：

```text
Frame
Group
Text
Shape
Image
Icon
Line
Original Reference
Fallback Region
```

------

## 12. 图片资产需求

### 12.1 资源字段

每个图片资产包含：

```text
assetId
type
role
url
format
width
height
```

开发阶段 URL 为本地文件 URL。
生产阶段 URL 为 OSS 签名 URL。

------

### 12.2 图片格式

一期插件加载资源时：

```text
照片类可使用 JPEG
透明 / 保真区域使用 PNG
后续再评估 WebP
```

------

### 12.3 原图参考层

每个生成页面必须包含隐藏原图参考层：

```text
Original PNG Reference
visible: false
opacity: 0.5
```

用于用户或开发者在 Figma 中手动对比。

------

## 13. 图标需求

一期支持：

```text
内置约 30 个高频线性 SVG 图标
单色图标用 SVG / Vector
复杂彩色图标 fallback 图片
低置信度图标 fallback 图片
```

一期不做完整外部图标库调用。

------

## 14. Fallback 需求

一期必须支持 fallback。

Fallback 用于：

```text
复杂 Banner
复杂插图
复杂图表
复杂运营图
复杂多色图标
无法稳定识别区域
```

Fallback 原则：

```text
局部失败不能导致整页失败
复杂区域可作为图片块回填
```

------

## 15. 任务状态需求

后端任务状态：

```text
pending
uploaded
processing
completed
failed
```

插件端展示：

```text
上传中
处理中
生成中
完成
失败
```

------

## 16. 性能需求

一期建议目标：

```text
简单移动端页面：15～30 秒
中等复杂页面：30～60 秒
复杂页面：60～90 秒
```

速度策略：

```text
普通页面尽量一次主 AI 调用
异常页面最多一次 JSON repair
复杂区域 fallback
控制节点数量
控制图片裁切数量
```

------

## 17. 测试需求

一期至少准备以下样例：

```text
简单 App 首页
小程序商品列表页
商品详情页
登录 / 表单页
带底部 TabBar 页面
弹窗页面
长截图页面
简单后台页面
```

每张图检查：

```text
页面尺寸是否正确
图层是否生成
主要文字是否可编辑
图片是否正确
主要布局是否接近
复杂区域是否 fallback
是否有明显遮挡错误
是否有隐藏原图参考层
```

------

## 18. 验收标准

一期 MVP 验收标准：

```text
1. 插件可上传 PNG
2. 插件可预览图片并开始生成
3. 后端可创建任务并返回 taskId
4. 后端可生成 DSL v0.1
5. DSL 可通过基础校验
6. 插件可获取 DSL
7. Renderer 可生成 Figma Frame
8. 主要文字可编辑
9. 主要图片位置正确
10. 常见图标可部分矢量化
11. 复杂区域 fallback 后不影响整页生成
12. 原图参考层默认隐藏保留
13. 失败时有明确错误日志
14. 生成速度在可接受范围内
```

------

## 19. 风险说明

### 19.1 识别效果风险

PNG 到可编辑设计稿本身存在不确定性，尤其是：

```text
复杂 Banner
复杂图表
复杂插图
特殊字体
低清晰度截图
多层视觉效果
```

应通过 fallback 保证整体可用。

------

### 19.2 速度风险

如果 AI 多轮调用过多、节点生成过细、图片资产过多，会导致整体变慢。

一期必须控制复杂度。

------

### 19.3 可编辑性与还原度冲突

越追求 100% 可编辑，越容易降低视觉还原和速度。

一期策略：

```text
主要内容可编辑
复杂区域图片兜底
```

------

## 20. 版本规划

### v0.1 MVP

```text
单张 PNG → DSL → Figma 可编辑设计稿
```

### v0.2 内测增强

```text
批量测试
错误分类
更稳定的 OCR / AI 管线
更多图标
更好的 fallback
```

### v0.3 质量评估

```text
评分系统
测试后台
低分样本分析
内部评测报告
```

### v1.0 Beta

```text
正式用户 UI
账号与权限
OSS 存储
隐私策略
商业化准备
```

------

## 21. PRD 结论

一期 PRD 的核心结论：

> 第一版只做 PNG 到 Figma 可编辑设计稿的核心链路，不做外围功能。

产品判断标准不是功能数量，而是：

```text
是否生成得出来
是否看起来像
是否主要内容可编辑
是否足够快
是否稳定
```

只要这条链路跑通，后续功能才有继续迭代的基础。

```
这就是第三份文档：

**`02_PRD产品需求文档/01_PRD总文档_v0.1.md`**

下一份建议继续输出：

**`03_DSL规范/01_DSL_v0.1_设计原则.md`**
```