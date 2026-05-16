下面继续输出第十二份核心文档：

**`10_开发计划与任务拆分/01_MVP开发里程碑_v0.1.md`**

~~~markdown
# MVP 开发里程碑 v0.1

文档名称：MVP 开发里程碑  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 开发计划文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于定义 Image-to-Figma Design v0.1 的开发里程碑。

v0.1 的开发目标不是一次性做完整商业化产品，而是优先打通核心链路：

```text
单张 PNG 上传
→ 后端识别
→ 生成 DSL v0.1
→ Figma 插件渲染
→ Figma 可编辑设计稿
~~~

所有里程碑都围绕这条主链路展开。

------

## 2. MVP 开发总原则

v0.1 开发必须遵循以下原则：

```text
1. 先跑通 DSL → Figma
2. 再跑通 PNG → DSL
3. 最后跑通 PNG → DSL → Figma 全链路
4. 不把 P1 / P2 功能塞进 MVP
5. 复杂区域允许 fallback
6. 优先保证速度、稳定性和可编辑基础能力
```

核心判断标准：

```text
能不能生成出来
生成得像不像
主要内容能不能编辑
速度能不能接受
失败时能不能定位原因
```

------

## 3. MVP 里程碑总览

v0.1 建议拆成 7 个阶段：

```text
M0：文档与协议冻结
M1：DSL Schema 与示例 DSL
M2：Renderer 用假 DSL 渲染 Figma
M3：Figma 插件最小 UI + 假后端链路
M4：后端上传 / 任务 / 本地存储
M5：真实 PNG → OCR / AI → DSL
M6：图片资产裁切 + 完整链路联调
M7：样例验收与 MVP 收敛
```

推荐开发顺序：

```text
M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7
```

其中最重要的是：

```text
M1：DSL
M2：Renderer
M6：完整链路
```

------

## 4. M0：文档与协议冻结

### 4.1 阶段目标

确定 v0.1 开发边界，避免开发过程中需求失控。

### 4.2 输入

```text
已确认的产品决策
一期 MVP 范围
一期不做事项
DSL v0.1 设计原则
Renderer 职责边界
```

### 4.3 输出文档

M0 阶段至少完成：

```text
01_项目总览/03_一期MVP范围_v0.1.md
01_项目总览/04_一期不做事项_v0.1.md
02_PRD产品需求文档/01_PRD总文档_v0.1.md
03_DSL规范/01_DSL_v0.1_设计原则.md
03_DSL规范/02_DSL_v0.1_字段说明.md
05_Image-to-Figma-Renderer渲染包/01_渲染包职责边界_v0.1.md
04_技术架构文档/01_整体技术架构_v0.1.md
```

### 4.4 验收标准

```text
1. 开发团队明确 v0.1 做什么
2. 开发团队明确 v0.1 不做什么
3. DSL 顶层结构确定
4. Renderer 职责边界确定
5. API 主链路确定
```

------

## 5. M1：DSL Schema 与示例 DSL

### 5.1 阶段目标

先把 DSL v0.1 变成开发可用的协议。

### 5.2 核心任务

```text
定义 TypeScript DSL 类型
定义 JSON Schema
定义默认值规则
定义基础校验规则
定义示例 DSL
准备 3～5 个示例页面 DSL
```

### 5.3 重点文件

```text
packages/dsl-schema/src/types.ts
packages/dsl-schema/src/elementTypes.ts
packages/dsl-schema/src/styleTypes.ts
packages/dsl-schema/src/assetTypes.ts
packages/dsl-schema/src/defaults.ts
packages/dsl-schema/src/validator.ts
packages/dsl-schema/src/normalize.ts
packages/dsl-schema/src/repair.ts
packages/dsl-schema/schemas/dsl-v0.1.schema.json
packages/dsl-schema/examples/mobile-home.dsl.json
```

### 5.4 必须支持的元素类型

```text
frame
group
text
shape
image
icon
line
```

### 5.5 必须支持的字段

```text
version
taskId
page
assets
root
meta

element.id
element.type
element.role
element.name
element.layout
element.style
element.content
element.source
element.children
element.meta
```

### 5.6 验收标准

```text
1. 有完整 DSL TypeScript 类型
2. 有 dsl-v0.1.schema.json
3. 示例 DSL 能通过校验
4. 错误 DSL 能返回明确错误
5. 默认值补全能正常工作
6. 后端和 Renderer 都能引用同一套类型定义
```

### 5.7 阶段结论

M1 完成后，团队应能拿着假 DSL 开始开发 Renderer。

------

## 6. M2：Renderer 用假 DSL 渲染 Figma

### 6.1 阶段目标

不等后端识别完成，先让 Figma Renderer 能消费假 DSL 并生成图层。

这是整个项目的核心里程碑之一。

### 6.2 核心任务

```text
实现 renderDesign 主入口
实现 root frame 创建
实现 frame / group 渲染
实现 text 渲染
实现 shape 渲染
实现 image 渲染
实现 line 渲染
实现基础 icon 渲染
实现 original_reference 隐藏图层
实现 fallback image 渲染
实现错误 warning 收集
```

### 6.3 重点文件

```text
packages/image-to-figma-renderer/src/renderDesign.ts
packages/image-to-figma-renderer/src/renderElement.ts
packages/image-to-figma-renderer/src/renderChildren.ts
packages/image-to-figma-renderer/src/renderFrame.ts
packages/image-to-figma-renderer/src/renderText.ts
packages/image-to-figma-renderer/src/renderShape.ts
packages/image-to-figma-renderer/src/renderImage.ts
packages/image-to-figma-renderer/src/renderIcon.ts
packages/image-to-figma-renderer/src/renderLine.ts
packages/image-to-figma-renderer/src/renderReference.ts
packages/image-to-figma-renderer/src/applyLayout.ts
packages/image-to-figma-renderer/src/applyStyle.ts
packages/image-to-figma-renderer/src/assetResolver.ts
packages/image-to-figma-renderer/src/imageLoader.ts
```

### 6.4 第一版渲染优先级

P0：

```text
root frame
text
shape
image
layout
fill
radius
opacity
visible
```

P1：

```text
icon
line
shadow
stroke
font loading
original reference
fallback
```

P2：

```text
gradient
复杂 SVG 改色
图片并发加载
高级 effects
```

### 6.5 验收标准

```text
1. 假 DSL 能在 Figma 中生成 root Frame
2. Text 能正确显示且可编辑
3. Shape 能显示颜色和圆角
4. Image 能通过 URL 加载并显示
5. Icon 能渲染至少 search / home / user / cart
6. Line 能显示 0.5px / 1px 分割线
7. Original PNG Reference 默认隐藏
8. 单个元素失败不影响整页
9. Renderer 返回 renderedElementCount 和 warnings
```

### 6.6 阶段结论

M2 完成后，即使后端还没做好，也能证明：

```text
DSL → Figma 可编辑稿
```

这条核心链路是可行的。

------

## 7. M3：Figma 插件最小 UI + 假后端链路

### 7.1 阶段目标

把插件 UI、Plugin Main、Renderer 串起来。

先不接真实 AI 后端，可以使用假 DSL 或 mock API。

### 7.2 核心任务

```text
实现 UploadView
实现 PreviewView
实现 ProgressView
实现 DoneView
实现 ErrorView
实现 UI ↔ Main 消息通信
实现 mock 获取 DSL
调用 renderDesign
生成结果后定位 Figma 画布
```

### 7.3 重点文件

```text
figma-plugin/src/ui/App.tsx
figma-plugin/src/ui/views/UploadView.tsx
figma-plugin/src/ui/views/PreviewView.tsx
figma-plugin/src/ui/views/ProgressView.tsx
figma-plugin/src/ui/views/DoneView.tsx
figma-plugin/src/ui/views/ErrorView.tsx
figma-plugin/src/plugin/main.ts
figma-plugin/src/plugin/controller.ts
figma-plugin/src/plugin/messageTypes.ts
figma-plugin/src/plugin/figmaBridge.ts
```

### 7.4 插件 UI 范围

只做：

```text
上传
预览
生成中
完成
失败
```

不做：

```text
历史记录
质量报告
插件内对比
设置页
账号页
批量上传
```

### 7.5 验收标准

```text
1. 插件能打开
2. 能选择 PNG
3. 能进入预览页
4. 点击开始生成后进入进度页
5. 能使用假 DSL 调用 Renderer
6. Figma 画布能出现生成 Frame
7. 完成后显示 DoneView
8. 出错后显示 ErrorView
```

### 7.6 阶段结论

M3 完成后，插件端主体验跑通。

------

## 8. M4：后端上传 / 任务 / 本地存储

### 8.1 阶段目标

搭建后端最小 API，支持插件真实上传 PNG，并返回 taskId 和假 DSL。

### 8.2 核心任务

```text
搭建 FastAPI
实现 health 接口
实现 upload 接口
实现 task 状态接口
实现 task DSL 接口
实现本地文件存储
实现任务记录
实现基础错误返回
```

### 8.3 重点文件

```text
backend/app/main.py
backend/app/api/routes_health.py
backend/app/api/routes_upload.py
backend/app/api/routes_tasks.py
backend/app/api/routes_assets.py
backend/app/services/upload_service.py
backend/app/services/task_service.py
backend/app/services/storage_service.py
backend/app/storage/local_storage.py
backend/app/models/task.py
backend/app/models/asset.py
```

### 8.4 接口范围

必须实现：

```text
GET  /api/health
POST /api/upload
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/assets/{assetId}
```

### 8.5 存储结构

```text
backend/storage/
├─ uploads/
├─ assets/
├─ dsl/
└─ logs/
```

### 8.6 验收标准

```text
1. POST /api/upload 能接收 PNG
2. 非 PNG 会拒绝
3. 图片过大会拒绝
4. 上传成功后返回 taskId
5. task 状态可查询
6. completed 后可获取假 DSL
7. DSL 中 asset URL 可访问
8. 插件能通过真实后端拿 DSL 并渲染
```

### 8.7 阶段结论

M4 完成后，插件和后端 API 链路跑通，但 DSL 仍可是假数据。

------

## 9. M5：真实 PNG → OCR / AI → DSL

### 9.1 阶段目标

让后端开始从真实 PNG 中生成 DSL，而不是返回假 DSL。

这是第二个核心里程碑。

### 9.2 核心任务

```text
图片预处理
PaddleOCR 接入
OCR block 标准化
基础 CV 区域检测
AI 结构分析
AI 输出结构化 JSON
DSL Builder 组装 DSL
DSL Validator 校验
基础 DSL Repair
```

### 9.3 重点文件

```text
backend/app/pipeline/image_preprocess.py
backend/app/pipeline/ocr_pipeline.py
backend/app/ocr/paddle_ocr_client.py
backend/app/ocr/ocr_normalizer.py
backend/app/ocr/text_block_merger.py
backend/app/pipeline/cv_detect.py
backend/app/pipeline/ai_analyze.py
backend/app/ai/ai_client.py
backend/app/ai/prompt_loader.py
backend/app/ai/structured_output.py
backend/app/ai/json_repair.py
backend/app/pipeline/dsl_builder.py
backend/app/dsl/dsl_validator.py
backend/app/dsl/dsl_normalizer.py
backend/app/dsl/dsl_defaults.py
backend/app/pipeline/dsl_repair.py
```

### 9.4 AI 调用原则

v0.1 只做：

```text
普通页面：1 次主 AI 结构分析
异常 JSON：最多 1 次 JSON repair
```

不做：

```text
多轮复杂分析
多模型对比
低分自动修复
完整质量评分闭环
```

### 9.5 OCR 输出标准

OCR 至少输出：

```text
text
bbox
confidence
lineId
blockId
```

### 9.6 DSL Builder 输出

至少能生成：

```text
page
assets
root
text elements
shape elements
image elements
fallback elements
meta
```

### 9.7 验收标准

```text
1. 上传真实 PNG 后能运行 OCR
2. 能识别主要文字
3. 能生成 Text 元素
4. 能生成 root Frame
5. 能生成基础 Shape / Frame
6. 能生成 fallback 区域
7. 生成 DSL 能通过校验
8. 插件能渲染真实 DSL
9. 主要文字在 Figma 中可编辑
```

### 9.8 阶段结论

M5 完成后，系统初步具备真实 PNG → DSL 能力。

------

## 10. M6：图片资产裁切 + 完整链路联调

### 10.1 阶段目标

补齐图片资产裁切，让真实页面中的头像、商品图、Banner、fallback 区域能回到 Figma 对应位置。

### 10.2 核心任务

```text
保存原始 PNG
生成 original reference asset
裁切商品图
裁切头像
裁切 Banner
裁切 fallback 区域
生成 assetId
保存 asset metadata
DSL assets 写入资源
Figma 插件通过 URL 加载图片
```

### 10.3 重点文件

```text
backend/app/pipeline/asset_cropper.py
backend/app/services/asset_service.py
backend/app/storage/local_storage.py
backend/app/api/routes_assets.py
backend/app/pipeline/dsl_builder.py
packages/image-to-figma-renderer/src/assetResolver.ts
packages/image-to-figma-renderer/src/imageLoader.ts
packages/image-to-figma-renderer/src/renderImage.ts
```

### 10.4 裁切策略

```text
默认外扩 1～2px
商品图外扩 2～4px
插图 / 运营图外扩 4～8px
Logo 保真
复杂区域 fallback 整块裁切
```

### 10.5 图片格式

开发阶段可简单处理：

```text
原图：PNG
裁切透明 / fallback：PNG
照片类：JPEG
```

WebP 后续再评估。

### 10.6 验收标准

```text
1. original_ref 能加载并隐藏
2. 商品图能裁切并显示
3. Banner 能裁切并显示
4. fallback 区域能显示
5. assetId 和 URL 对应正确
6. 图片加载失败不会导致整页失败
7. 真实 PNG → DSL → Figma 全链路跑通
```

### 10.7 阶段结论

M6 完成后，核心链路基本完整。

------

## 11. M7：样例验收与 MVP 收敛

### 11.1 阶段目标

用固定样例验证 MVP 是否达到第一版可用标准，并修复关键问题。

### 11.2 样例范围

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

### 11.3 每张图检查项

```text
页面尺寸是否正确
root Frame 是否生成
主要文字是否可编辑
主要图片是否在对应位置
主要布局是否接近
TabBar / Header 是否基本正确
复杂区域是否 fallback
是否出现严重遮挡
是否有隐藏原图参考层
生成速度是否可接受
失败时是否有错误日志
```

### 11.4 不要求

M7 不要求：

```text
1000 张自动测试
完整评分看板
像素级热力图
低分自动修复
100% 可编辑
100% 图标矢量化
```

### 11.5 验收标准

```text
1. 8～10 张核心样例中，大部分能成功生成
2. 简单移动端页面能在 15～30 秒左右生成
3. 中等复杂页面能在 30～60 秒左右生成
4. 复杂区域 fallback 后整页不崩
5. 主要文字可编辑
6. 图片资产能显示
7. Figma 图层命名基本可读
8. 开发人员能定位失败原因
```

### 11.6 阶段结论

M7 完成后，可以认为 v0.1 MVP 核心链路完成。

------

## 12. 建议排期方式

由于开发资源未知，本文档不强制固定天数，只给相对阶段顺序。

如果是小团队，可以按以下节奏估算：

```text
第 1 阶段：M0 / M1
文档冻结 + DSL Schema

第 2 阶段：M2
Renderer 假 DSL 渲染

第 3 阶段：M3 / M4
插件 UI + 后端 API 打通

第 4 阶段：M5
真实 PNG → DSL

第 5 阶段：M6 / M7
图片资产 + 完整链路验收
```

推荐开发判断：

```text
任何时候只要 DSL → Figma 没跑通，就不要投入太多后端 AI 复杂优化。
任何时候只要 PNG → DSL 不稳定，就不要做插件历史记录、质量报告等外围功能。
```

------

## 13. 每阶段 Go / No-Go 判断

### 13.1 M1 Go / No-Go

Go 条件：

```text
DSL 类型和示例稳定
Renderer 可以开始开发
```

No-Go：

```text
DSL 顶层结构还在频繁变化
Element type 未确定
```

------

### 13.2 M2 Go / No-Go

Go 条件：

```text
假 DSL 能成功渲染 Figma
Text / Shape / Image 可用
```

No-Go：

```text
Renderer 无法稳定生成 root Frame
图片加载不通
字体渲染不通
```

------

### 13.3 M4 Go / No-Go

Go 条件：

```text
插件能通过后端拿假 DSL 并渲染
```

No-Go：

```text
上传接口不稳定
task 状态不稳定
DSL 获取不稳定
```

------

### 13.4 M5 Go / No-Go

Go 条件：

```text
真实 PNG 能生成可校验 DSL
```

No-Go：

```text
OCR 输出不可用
AI 输出不可控
DSL Builder 无法生成稳定结构
```

------

### 13.5 M6 Go / No-Go

Go 条件：

```text
真实 PNG 完整链路可跑
图片资产能显示
```

No-Go：

```text
assetId 和 URL 经常失配
图片加载严重失败
DSL 和 Renderer 不兼容
```

------

## 14. 关键风险与应对

### 14.1 风险：生成效果差

应对：

```text
优先修 DSL Builder
优先修 Renderer 显示
复杂区域 fallback
不要追求全可编辑
```

### 14.2 风险：速度太慢

应对：

```text
减少 AI 调用轮次
减少节点数量
减少图片裁切数量
复杂区域 fallback
不要接入自动评分闭环
```

### 14.3 风险：开发范围膨胀

应对：

```text
严格执行一期不做事项
所有非核心需求进入 P1 / P2
```

### 14.4 风险：Renderer 与 DSL 反复不匹配

应对：

```text
先冻结 DSL v0.1
所有字段变更走版本记录
示例 DSL 作为回归样例
```

------

## 15. MVP 必须先完成的 10 件事

按优先级排序：

```text
1. DSL v0.1 类型和 Schema
2. 示例 DSL
3. Renderer 渲染 root / text / shape / image
4. Figma 插件调用 Renderer
5. 后端 upload / task / dsl API
6. 本地文件存储
7. OCR 接入
8. AI 结构分析
9. DSL Builder
10. 图片资产裁切
```

这 10 件事之外的功能，默认不进入 v0.1 核心优先级。

------

## 16. MVP 结束后再考虑的内容

MVP 核心链路完成后，再考虑：

```text
批量上传
历史记录
测试后台
质量评分
错误分类看板
多模型对比
代码生成
组件化
Auto Layout
商业化账号 / 额度 / 支付
```

------

## 17. 里程碑交付物汇总

| 里程碑 | 主要交付物                   |
| ------ | ---------------------------- |
| M0     | 文档冻结、MVP 范围、不做事项 |
| M1     | DSL Schema、类型、示例 DSL   |
| M2     | Renderer 可用，假 DSL 能渲染 |
| M3     | 插件最小 UI，可调用 Renderer |
| M4     | 后端 API，可上传并返回假 DSL |
| M5     | 真实 PNG 可生成 DSL          |
| M6     | 图片资产裁切，完整链路跑通   |
| M7     | 样例验收，MVP 收敛           |

------

## 18. 版本结论

v0.1 开发里程碑的核心逻辑是：

```text
先协议
再渲染
再插件
再后端
再识别
再联调
再验收
```

第一版开发必须始终围绕：

```text
PNG → DSL → Figma
```

只要这条链路稳定跑通，v0.1 就达到了 MVP 目标。

```
这就是第十二份文档：

**`10_开发计划与任务拆分/01_MVP开发里程碑_v0.1.md`**

下一份建议继续输出：

**`10_开发计划与任务拆分/10_验收标准_v0.1.md`**
```