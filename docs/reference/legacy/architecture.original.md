下面继续输出第九份核心文档：

**`04_技术架构文档/01_整体技术架构_v0.1.md`**

~~~markdown
# 整体技术架构 v0.1

文档名称：整体技术架构  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 核心架构设计文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于说明 Image-to-Figma Design v0.1 的整体技术架构。

v0.1 的核心目标是打通：

```text
PNG 上传
→ 后端识别
→ DSL v0.1
→ Figma 插件渲染
→ Figma 可编辑设计稿
~~~

第一版架构必须围绕核心链路设计，避免过度工程化。

------

## 2. 架构总原则

v0.1 架构原则：

```text
1. 先跑通核心链路
2. 后端先保持简单
3. Renderer 独立成包
4. DSL 作为后端和插件之间的稳定协议
5. 开发阶段优先本地存储
6. 生产阶段预留 OSS / 签名 URL
7. AI 调用不做复杂模型路由
8. 复杂功能后置
```

第一版不追求：

```text
复杂微服务
复杂缓存系统
复杂队列系统
复杂权限系统
复杂商业化系统
复杂模型对比平台
```

------

## 3. 系统核心链路

### 3.1 用户视角

```text
用户在 Figma 插件中上传 PNG
↓
插件显示预览确认
↓
用户点击开始生成
↓
后端处理图片并生成 DSL
↓
插件获取 DSL
↓
Renderer 在 Figma 画布中生成可编辑设计稿
```

### 3.2 系统视角

```text
Figma Plugin UI
↓
Figma Plugin Main
↓
Backend API
↓
Image Preprocess
↓
OCR Pipeline
↓
AI / CV Analyze
↓
Asset Cropper
↓
DSL Builder
↓
DSL Validator / Repair
↓
Task Result API
↓
Figma Renderer
↓
Figma Canvas
```

------

## 4. 总体架构图

```text
┌────────────────────────────────────────────┐
│                Figma Plugin                │
│                                            │
│  ┌──────────────┐      ┌────────────────┐  │
│  │ Plugin UI    │      │ Plugin Main    │  │
│  │              │      │                │  │
│  │ UploadView   │◄────►│ API Client     │  │
│  │ PreviewView  │      │ Renderer Call  │  │
│  │ ProgressView │      │ Figma API      │  │
│  └──────────────┘      └────────┬───────┘  │
│                                  │          │
│                                  ▼          │
│                     ┌────────────────────┐  │
│                     │ Image-to-Figma      │  │
│                     │ Renderer            │  │
│                     │ DSL → Figma Nodes   │  │
│                     └────────────────────┘  │
└──────────────────────────┬─────────────────┘
                           │ HTTP
                           ▼
┌────────────────────────────────────────────┐
│                  Backend API               │
│                                            │
│  Upload API                                │
│  Task API                                  │
│  Asset API                                 │
│  DSL Result API                            │
└──────────────────────────┬─────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────┐
│                Processing Pipeline          │
│                                            │
│  Image Preprocess                          │
│  OCR Pipeline                              │
│  AI / CV Analyze                           │
│  Asset Cropper                             │
│  DSL Builder                               │
│  DSL Validator / Repair                    │
└──────────────────────────┬─────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────┐
│                  Storage                   │
│                                            │
│  uploads/                                  │
│  assets/                                   │
│  dsl/                                      │
│  logs/                                     │
│                                            │
│  v0.1: Local Storage                       │
│  future: OSS / Object Storage              │
└────────────────────────────────────────────┘
```

------

## 5. v0.1 技术栈建议

### 5.1 后端

推荐：

```text
Python
FastAPI
Pydantic
SQLite / PostgreSQL
Local File Storage
PaddleOCR
OpenAI / GPT 视觉模型
```

v0.1 可以先用：

```text
FastAPI + SQLite + 本地文件存储
```

后续再升级：

```text
PostgreSQL + OSS + Redis Queue
```

------

### 5.2 Figma 插件

推荐：

```text
TypeScript
React
Vite
Figma Plugin API
pnpm workspace
```

插件分两层：

```text
Plugin UI：React 页面
Plugin Main：Figma API 操作和 Renderer 调用
```

------

### 5.3 DSL / Renderer

推荐：

```text
TypeScript
独立 packages/dsl-schema
独立 packages/image-to-figma-renderer
```

原因：

```text
DSL 和 Renderer 是核心资产
不应和插件 UI 强耦合
后续可以单独测试、复用、版本化
```

------

## 6. 代码仓库建议结构

```text
image-to-figma-design/
├─ backend/
│  ├─ app/
│  ├─ storage/
│  ├─ tests/
│  └─ README.md
│
├─ figma-plugin/
│  ├─ src/
│  │  ├─ ui/
│  │  ├─ plugin/
│  │  ├─ renderer/
│  │  ├─ assets/
│  │  ├─ icons/
│  │  ├─ schema/
│  │  └─ utils/
│  ├─ manifest.json
│  └─ README.md
│
├─ packages/
│  ├─ dsl-schema/
│  └─ image-to-figma-renderer/
│
├─ docs/
├─ examples/
├─ scripts/
├─ .env.example
├─ package.json
├─ pnpm-workspace.yaml
└─ README.md
```

------

## 7. 核心模块划分

v0.1 主要模块：

```text
1. Figma Plugin UI
2. Figma Plugin Main
3. Image-to-Figma Renderer
4. DSL Schema
5. Backend API
6. Processing Pipeline
7. AI Client
8. OCR Pipeline
9. Asset Service
10. Storage Service
11. Task Service
```

------

## 8. Figma Plugin UI

### 8.1 职责

Plugin UI 负责用户交互：

```text
上传 PNG
预览图片
显示文件信息
显示风险提示
点击开始生成
显示简单进度
显示成功 / 失败
```

### 8.2 页面

v0.1 页面：

```text
UploadView
PreviewView
ProgressView
DoneView
ErrorView
```

### 8.3 不负责

Plugin UI 不负责：

```text
创建 Figma 图层
渲染 DSL
图片识别
OCR
AI 分析
DSL 生成
质量评分
```

------

## 9. Figma Plugin Main

### 9.1 职责

Plugin Main 运行在 Figma 插件主线程中。

负责：

```text
接收 UI 消息
调用后端 API
接收 DSL
调用 Renderer
使用 Figma Plugin API 创建图层
返回结果给 UI
```

### 9.2 消息流

```text
UI: uploadSelected
↓
Main: call Upload API
↓
UI: startGenerate
↓
Main: call Task API / Poll Status
↓
Main: fetch DSL
↓
Main: renderDesign(dsl)
↓
UI: done / error
```

------

## 10. Image-to-Figma Renderer

### 10.1 职责

Renderer 负责：

```text
DSL v0.1 → Figma 图层
```

支持：

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

### 10.2 不负责

Renderer 不负责：

```text
OCR
AI
图片裁切
DSL 生成
质量评分
代码生成
组件化
Auto Layout
```

### 10.3 设计原则

```text
简单
稳定
快速
单元素失败不影响整页
```

------

## 11. DSL Schema

### 11.1 职责

DSL Schema 包负责定义：

```text
DSL 类型
Element 类型
Style 类型
Asset 类型
默认值
校验规则
修复规则
示例 DSL
```

### 11.2 作用

DSL Schema 是后端和插件之间的合同。

后端按 Schema 生成 DSL。
插件按 Schema 消费 DSL。

------

## 12. Backend API

### 12.1 职责

后端 API 负责：

```text
接收上传
创建任务
查询任务状态
返回 DSL
返回图片资产
返回错误信息
健康检查
```

### 12.2 建议接口

```text
POST /api/upload
POST /api/tasks
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/assets/{assetId}
GET  /api/health
```

### 12.3 v0.1 API 特点

```text
简单
同步 / 半同步皆可
优先打通链路
不做复杂鉴权
不做复杂权限
不做支付 / 额度
```

------

## 13. Processing Pipeline

### 13.1 职责

Processing Pipeline 负责：

```text
原图预处理
OCR
AI / CV 分析
图片资产裁切
DSL 生成
DSL 校验
DSL 基础修复
```

### 13.2 流程

```text
run_pipeline(taskId)
↓
load original image
↓
preprocess image
↓
run OCR
↓
run AI / CV analysis
↓
crop assets
↓
build DSL
↓
validate DSL
↓
repair if needed
↓
save result
```

------

## 14. Image Preprocess

### 14.1 职责

图片预处理负责：

```text
读取图片尺寸
校验格式
校验大小
计算 scaleFactor
标准化坐标
检测低质量风险
```

### 14.2 v0.1 输入限制

```text
只支持 PNG
单张上传
文件大小建议不超过 10MB
移动端截图优先
```

### 14.3 输出

```text
image metadata
normalized size
scaleFactor
qualityFlags
```

------

## 15. OCR Pipeline

### 15.1 职责

OCR Pipeline 负责：

```text
识别文字
返回文本内容
返回 bbox
返回置信度
合并文本块
输出标准化 OCR blocks
```

### 15.2 推荐方案

```text
PaddleOCR
```

### 15.3 后续增强

```text
AI 文本纠错
数字敏感文本保护
文本角色判断
```

------

## 16. AI / CV Analyze

### 16.1 职责

AI / CV 负责：

```text
页面结构理解
组件区域判断
元素归属判断
图标候选判断
复杂区域 fallback 判断
DSL 中间结构补充
```

### 16.2 v0.1 调用策略

```text
普通页面尽量 1 次主模型调用
异常 JSON 最多 1 次 repair
不做多轮复杂分析
```

### 16.3 不做

```text
多模型对比
复杂模型路由
低分自动多轮修复
```

------

## 17. Asset Service

### 17.1 职责

Asset Service 负责：

```text
保存原图
裁切头像 / 商品图 / Banner / Logo / fallback 区域
生成 assetId
保存 asset 元数据
生成可访问 URL
```

### 17.2 开发阶段

开发阶段使用：

```text
本地文件存储
http://localhost:8000/files/...
```

### 17.3 生产阶段预留

生产阶段切换：

```text
OSS / 对象存储
短期签名 URL
CDN
```

但 v0.1 不强制实现完整生产存储。

------

## 18. Storage Service

### 18.1 开发阶段目录

```text
backend/storage/
├─ uploads/
├─ assets/
├─ dsl/
└─ logs/
```

### 18.2 存储内容

```text
原始 PNG
预处理图
裁切资产
DSL JSON
错误日志
任务结果
```

### 18.3 后续升级

```text
local → OSS
SQLite → PostgreSQL
local logs → logging service
```

------

## 19. Task Service

### 19.1 职责

Task Service 管理任务状态。

状态：

```text
pending
uploaded
processing
completed
failed
```

### 19.2 任务记录

任务至少包含：

```text
taskId
status
createdAt
updatedAt
originalImagePath
dslPath
errorCode
errorMessage
durationMs
```

### 19.3 v0.1 实现

v0.1 可以先简单实现：

```text
上传后立即处理
或后端后台线程处理
```

不强制引入复杂队列。

------

## 20. Worker / Queue 策略

### 20.1 v0.1 建议

v0.1 可以先不引入复杂队列系统。

可选实现：

```text
FastAPI BackgroundTasks
简单线程任务
本地任务状态表
```

### 20.2 后续升级

当任务量增加后再引入：

```text
Redis Queue
Celery
RQ
Dramatiq
云队列
```

第一版重点不是队列系统，而是识别和渲染效果。

------

## 21. 数据库策略

### 21.1 v0.1 开发阶段

推荐：

```text
SQLite
```

用途：

```text
任务记录
资产记录
错误记录
DSL 路径记录
```

### 21.2 后续生产阶段

升级：

```text
PostgreSQL
JSONB
```

用于：

```text
DSL 元数据查询
任务统计
错误分析
用户数据
```

------

## 22. AI Client

### 22.1 职责

AI Client 负责：

```text
封装模型调用
加载 prompt
结构化输出
JSON 修复
记录模型版本
记录耗时
记录摘要信息
```

### 22.2 v0.1 不做

```text
复杂 Model Router
多模型对比
自动模型选择
成本优化平台
```

### 22.3 Prompt 管理

Prompt 应配置化、版本化：

```text
semantic_analyzer_v0.1.md
text_corrector_v0.1.md
icon_matcher_v0.1.md
dsl_repair_v0.1.md
```

------

## 23. 错误处理架构

### 23.1 后端错误

后端记录：

```text
taskId
stage
errorCode
message
detail
createdAt
```

错误阶段：

```text
upload
preprocess
ocr
ai_analyze
asset_crop
dsl_build
dsl_validate
figma_render
```

### 23.2 插件错误

插件显示友好提示：

```text
上传失败
图片格式不支持
识别失败
生成失败
网络异常
```

开发阶段可查看详细错误。

------

## 24. 日志架构

v0.1 日志分三类：

```text
任务日志
模型调用日志
渲染日志
```

### 24.1 任务日志

记录任务整体生命周期。

### 24.2 模型调用日志

记录：

```text
模型名称
prompt 版本
调用时间
耗时
输入摘要
输出摘要
错误信息
```

### 24.3 渲染日志

记录：

```text
renderedElementCount
skippedElementCount
warnings
asset load errors
font load errors
```

------

## 25. 资源 URL 策略

### 25.1 开发阶段

```text
assetId + local URL
```

示例：

```json
{
  "assetId": "asset_product_001",
  "url": "http://localhost:8000/files/assets/product_001.jpg",
  "storage": "local"
}
```

### 25.2 生产阶段

```text
assetId + OSS objectKey + signed URL
```

示例：

```json
{
  "assetId": "asset_product_001",
  "objectKey": "tasks/task_001/assets/product_001.jpg",
  "url": "https://oss.example.com/xxx?signature=xxx",
  "storage": "oss",
  "expiresAt": "2026-05-16T12:00:00Z"
}
```

v0.1 架构预留字段即可。

------

## 26. 性能架构策略

v0.1 必须避免系统过慢。

### 26.1 控制 AI 调用

```text
普通页面：1 次主 AI 调用
异常 JSON：最多 1 次 repair
不做多轮分析
```

### 26.2 控制节点数

```text
移动端页面建议 100～300 节点
复杂区域 fallback
不强拆复杂 Banner / 图表
```

### 26.3 控制图片资产

```text
只裁切必要图片
头像 / 商品图 / Banner / Logo / fallback
不要裁切大量小碎图
```

### 26.4 控制插件渲染复杂度

```text
Renderer 只按 DSL 渲染
不做二次推理
图片加载做缓存
单元素失败不中断整页
```

------

## 27. 部署架构 v0.1

### 27.1 开发环境

```text
本地 FastAPI
本地 storage
Figma dev plugin
本地 SQLite
本地 PaddleOCR
模型 API
```

### 27.2 内测环境

```text
云服务器
FastAPI
本地磁盘或对象存储
SQLite / PostgreSQL
Figma 插件开发版
```

### 27.3 生产环境后续

```text
API Server
Worker
PostgreSQL
OSS / Object Storage
Redis Queue
日志服务
监控服务
```

v0.1 不要求一次性全部上齐。

------

## 28. 安全与隐私策略 v0.1

### 28.1 开发阶段

```text
保留原图
保留 DSL
保留模型输出摘要
保留错误日志
方便调试
```

### 28.2 商业化前

需要补充：

```text
30 天数据保留策略
用户手动删除
日志脱敏
OSS 签名 URL
隐私政策
```

v0.1 只预留架构，不做完整合规系统。

------

## 29. 模块依赖关系

```text
Figma Plugin UI
  depends on Plugin Main

Plugin Main
  depends on Backend API
  depends on Renderer

Renderer
  depends on DSL Schema
  depends on Figma Plugin API
  depends on Assets URL

Backend API
  depends on Task Service
  depends on Storage Service
  depends on Processing Pipeline

Processing Pipeline
  depends on OCR
  depends on AI Client
  depends on Asset Service
  depends on DSL Builder

DSL Builder
  depends on DSL Schema
```

------

## 30. v0.1 不进入架构的内容

以下不进入 v0.1 架构主线：

```text
代码生成服务
组件库服务
用户账号系统
支付系统
额度系统
多模型对比平台
完整评分看板
差异热力图服务
多页面项目管理
Web 深度识别引擎
复杂缓存系统
正式权限系统
```

这些全部后续再规划。

------

## 31. MVP 开发优先级

建议开发顺序：

```text
1. DSL Schema
2. Renderer 用假 DSL 渲染 Figma
3. Figma 插件最小 UI
4. 后端 API 返回假 DSL
5. 打通插件调用后端并渲染
6. 后端接入上传和本地存储
7. 后端接入 OCR
8. 后端接入 AI 分析
9. 后端生成真实 DSL
10. 后端接入图片裁切
11. 真实 PNG → Figma 测试
```

核心原则：

```text
先让 DSL → Figma 跑通
再让 PNG → DSL 跑通
```

------

## 32. 架构风险

### 32.1 识别效果风险

PNG 到结构化 DSL 本身存在不确定性。

解决策略：

```text
复杂区域 fallback
不要追求全可编辑
优先移动端页面
```

### 32.2 速度风险

AI 调用、OCR、图片加载、Figma 节点创建都可能变慢。

解决策略：

```text
限制 AI 轮次
控制节点数
控制图片数量
复杂区域 fallback
```

### 32.3 Renderer 稳定性风险

Figma API 对字体、图片、SVG 处理有约束。

解决策略：

```text
字体失败用默认字体
图片失败用占位
icon 找不到跳过
单元素失败不中断整页
```

### 32.4 范围膨胀风险

如果持续往 MVP 塞功能，第一版会无法落地。

解决策略：

```text
严格执行一期不做事项
所有非核心功能进入 P1 / P2
```

------

## 33. v0.1 架构验收标准

v0.1 架构可以认为通过，当满足：

```text
1. 插件能上传 PNG
2. 后端能保存原图
3. 后端能返回 taskId
4. 后端能生成或返回 DSL
5. 插件能获取 DSL
6. Renderer 能创建 Figma root Frame
7. Renderer 能渲染 Text / Shape / Image
8. 图片资产能通过 URL 加载
9. 原图参考层能隐藏插入
10. 复杂区域能 fallback
11. 后端有基础错误日志
12. 插件能显示成功 / 失败
```

------

## 34. 版本结论

Image-to-Figma Design v0.1 的整体架构必须围绕：

```text
PNG → DSL → Figma
```

所有架构设计都要服务这个目标：

```text
快
像
可编辑
稳定
```

第一版不追求大而全，而是追求核心链路可验证、可迭代、可继续扩展。

只要 v0.1 能稳定打通：

```text
单张 PNG → DSL v0.1 → Figma 可编辑设计稿
```

就完成了整体技术架构的第一阶段目标。

```
这就是第九份文档：

**`04_技术架构文档/01_整体技术架构_v0.1.md`**

下一份建议继续输出：

**`06_Figma插件设计文档/01_插件MVP交互流程_v0.1.md`**
```