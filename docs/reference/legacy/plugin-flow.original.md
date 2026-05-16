下面继续输出第十份核心文档：

**`06_Figma插件设计文档/01_插件MVP交互流程_v0.1.md`**

~~~markdown
# Figma 插件 MVP 交互流程 v0.1

文档名称：Figma 插件 MVP 交互流程  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 插件交互设计文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于定义 Image-to-Figma Design v0.1 的 Figma 插件最小交互流程。

v0.1 插件的目标不是做完整正式产品 UI，而是服务核心链路：

```text
上传 PNG
→ 预览确认
→ 后端生成 DSL
→ Renderer 渲染到 Figma
→ 用户看到可编辑设计稿
~~~

插件 UI 必须保持克制，不把调试后台、质量评估、历史记录、对比工具等外围功能塞进第一版。

------

## 2. 插件 v0.1 核心原则

插件 v0.1 只追求：

```text
简单
直接
能跑通主链路
不暴露复杂技术细节
不拖慢开发
```

插件 v0.1 不追求：

```text
精美品牌 UI
复杂历史记录
质量评分展示
详细错误报告
插件内原图对比
插件内测试看板
多页面项目管理
复杂用户设置
```

------

## 3. 插件 v0.1 核心流程

用户流程：

```text
打开插件
↓
上传 PNG
↓
查看预览确认
↓
点击开始生成
↓
查看简单进度
↓
Figma 画布生成设计稿
↓
插件显示生成完成
```

系统流程：

```text
Plugin UI 选择 PNG
↓
Plugin Main / API Client 上传文件
↓
Backend 创建任务 taskId
↓
Backend 处理并生成 DSL
↓
Plugin 获取任务状态
↓
Plugin 获取 DSL
↓
Renderer 渲染 Figma 图层
↓
Plugin UI 显示完成
```

------

## 4. 插件页面范围

v0.1 插件只包含 5 个页面状态：

```text
UploadView
PreviewView
ProgressView
DoneView
ErrorView
```

不做：

```text
HistoryView
TaskListView
QualityReportView
CompareView
SettingsView
AccountView
BillingView
DebugDashboardView
```

开发阶段如果需要调试，可通过开发版插件、后端日志、浏览器控制台或内部测试后台处理，不进入正式 MVP 交互主线。

------

## 5. 页面状态流转

```text
UploadView
  ↓ 选择 PNG 成功
PreviewView
  ↓ 点击开始生成
ProgressView
  ↓ 生成成功
DoneView

UploadView / PreviewView / ProgressView
  ↓ 任意阶段失败
ErrorView
```

可选返回流：

```text
PreviewView
  ↓ 点击重新上传
UploadView

ErrorView
  ↓ 点击重新上传
UploadView
```

v0.1 不强制做“重试当前任务”按钮。
如果开发成本低，可以在 ErrorView 中提供重试；如果影响进度，先只做重新上传。

------

## 6. UploadView

### 6.1 页面目标

UploadView 的目标是让用户选择一张 PNG 图片。

### 6.2 页面内容

UploadView 包含：

```text
标题
上传区域
格式说明
图片质量建议
```

### 6.3 推荐文案

标题：

```text
上传 PNG 生成 Figma
```

说明：

```text
支持 App / 小程序移动端 PNG 截图。
建议上传清晰、高保真的设计稿或截图。
```

上传按钮：

```text
选择 PNG 图片
```

格式提示：

```text
当前仅支持 PNG。
```

### 6.4 交互规则

用户点击上传区域后，选择本地图片。

插件应校验：

```text
是否选择文件
是否为 PNG
文件大小是否超限
图片是否可读取
```

如果校验通过，进入 PreviewView。

如果校验失败，进入 ErrorView 或在当前页面显示错误提示。

------

## 7. PreviewView

### 7.1 页面目标

PreviewView 让用户在正式消耗生成任务前确认图片。

### 7.2 页面内容

PreviewView 包含：

```text
图片预览
文件名
文件大小
图片尺寸
格式信息
风险提示
开始生成按钮
重新上传按钮
```

### 7.3 显示字段

```text
文件名：home.png
格式：PNG
尺寸：390 × 844
大小：1.2 MB
```

### 7.4 风险提示

如果检测到风险，显示非阻断提示。

风险包括：

```text
图片过大
图片过小
图片较模糊
文字可能不清晰
图片尺寸不常见
图片为长截图
```

推荐文案：

```text
当前图片可能较模糊，生成结果可能不够准确，你仍然可以继续。
当前图片尺寸较大，处理时间可能更长。
```

### 7.5 按钮

主按钮：

```text
开始生成
```

次按钮：

```text
重新上传
```

### 7.6 交互规则

点击「开始生成」后：

```text
进入 ProgressView
上传文件到后端
创建任务
等待任务结果
```

点击「重新上传」后：

```text
回到 UploadView
清空当前选择
```

------

## 8. ProgressView

### 8.1 页面目标

ProgressView 让用户知道任务正在处理。

v0.1 不展示内部技术细节。

### 8.2 页面内容

```text
进度条
简单状态文案
可选小提示
```

### 8.3 状态文案

允许展示：

```text
上传中…
处理中…
生成中…
正在写入 Figma…
```

不展示：

```text
OCR 中
AI 分析中
DSL 生成中
Schema 校验中
模型调用中
图片裁切中
```

原因：

```text
普通用户不需要理解内部阶段。
技术细节会增加理解成本。
```

### 8.4 进度条策略

v0.1 可以使用伪进度。

建议：

```text
上传阶段：0% → 20%
后端处理：20% → 80%
Figma 渲染：80% → 100%
```

如果后端能返回真实状态，可以映射为简单阶段。

### 8.5 禁止操作

ProgressView 中不建议提供复杂操作。

v0.1 不做：

```text
取消任务
查看日志
切换模型
打开报告
```

------

## 9. DoneView

### 9.1 页面目标

DoneView 只告诉用户生成完成。

### 9.2 页面内容

```text
生成完成
请在当前 Figma 画布中查看结果
```

### 9.3 推荐文案

```text
生成完成，请在当前 Figma 画布中查看结果。
```

### 9.4 不做复杂按钮

v0.1 不做：

```text
查看结果按钮
重新生成按钮
查看质量报告按钮
下载 DSL 按钮
历史记录按钮
```

原因：

```text
MVP 阶段先保证生成链路，不增加外围交互。
```

如果 Figma 插件主线程已经执行：

```text
figma.viewport.scrollAndZoomIntoView([rootFrame])
```

用户会自动看到生成结果。

------

## 10. ErrorView

### 10.1 页面目标

ErrorView 告诉用户失败原因，并提供简单下一步。

### 10.2 页面内容

```text
错误标题
友好错误原因
重新上传按钮
可选重试按钮
```

### 10.3 用户侧错误文案

#### 图片格式错误

```text
当前仅支持 PNG 格式，请重新上传 PNG 图片。
```

#### 图片过大

```text
图片过大，请压缩到 10MB 以内后重新上传。
```

#### 上传失败

```text
图片上传失败，请检查网络后重试。
```

#### 识别失败

```text
图片识别失败，请换一张更清晰的 PNG 截图。
```

#### 生成失败

```text
生成失败，请重试或重新上传。
```

#### 图片资源加载失败

```text
部分图片资源加载失败，请重新生成。
```

### 10.4 开发阶段错误

开发阶段需要保留详细错误信息，但不和正式用户 UI 混在一起。

开发阶段可查看：

```text
taskId
failedStage
errorCode
errorMessage
stack / detail
DSL 校验错误
assetId
elementId
```

正式版插件不直接展示这些技术信息。

### 10.5 按钮策略

v0.1 必须有：

```text
重新上传
```

可选：

```text
重试
```

如果「重试」实现会增加后端和插件复杂度，可以先不做。

------

## 11. 插件和后端的交互流程

### 11.1 上传流程

```text
用户选择 PNG
↓
Plugin UI 读取文件信息
↓
Plugin Main 上传到 Backend
↓
Backend 返回 uploadId / taskId
```

### 11.2 创建任务

可以设计为两种方式。

方案 A：上传即创建任务。

```text
POST /api/upload
→ 返回 taskId
```

方案 B：上传和创建任务分离。

```text
POST /api/upload
→ uploadId

POST /api/tasks
→ taskId
```

v0.1 推荐方案 A，简单。

### 11.3 查询任务

```text
GET /api/tasks/{taskId}
```

返回：

```json
{
  "taskId": "task_001",
  "status": "processing",
  "progress": 60,
  "message": "处理中"
}
```

### 11.4 获取 DSL

```text
GET /api/tasks/{taskId}/dsl
```

返回完整 DSL v0.1。

### 11.5 渲染

Plugin Main 收到 DSL 后调用：

```ts
await renderDesign(dsl)
```

------

## 12. 插件内部消息流

Figma 插件通常有 UI 线程和 Main 线程。

### 12.1 UI → Main

消息类型建议：

```text
SELECT_FILE
START_GENERATE
REUPLOAD
```

### 12.2 Main → UI

消息类型建议：

```text
UPLOAD_PROGRESS
TASK_PROGRESS
RENDER_PROGRESS
DONE
ERROR
```

### 12.3 示例

```ts
// UI → Main
parent.postMessage({
  pluginMessage: {
    type: "START_GENERATE",
    payload: {
      fileName: "home.png",
      bytes: imageBytes
    }
  }
}, "*")
// Main → UI
figma.ui.postMessage({
  type: "DONE",
  payload: {
    taskId: "task_001"
  }
})
```

------

## 13. 插件 v0.1 状态机

### 13.1 状态枚举

```ts
type PluginViewState =
  | "upload"
  | "preview"
  | "progress"
  | "done"
  | "error"
```

### 13.2 状态数据

```ts
interface PluginState {
  view: PluginViewState
  selectedFile?: SelectedFileInfo
  taskId?: string
  progress?: number
  message?: string
  error?: PluginError
}
```

------

## 14. 文件校验规则

v0.1 插件端先做基础校验。

### 14.1 格式

只允许：

```text
PNG
```

### 14.2 大小

建议限制：

```text
≤ 10MB
```

### 14.3 尺寸

建议提示范围：

```text
移动端宽度：320～1080px
高度：不超过 5000px
```

不强制拒绝异常尺寸，只提示风险。

### 14.4 质量风险

插件端可做轻量判断：

```text
尺寸过小
文件过大
长截图
```

模糊检测可由后端处理，插件端不强制实现。

------

## 15. 插件 UI 不暴露的内容

v0.1 用户侧插件不暴露：

```text
OCR 结果
AI 模型名称
Prompt 版本
DSL JSON
Schema 校验细节
Fallback 数量
质量评分
错误 elementId
错误 assetId
模型耗时
token 成本
```

这些全部属于内部开发 / 测试信息。

------

## 16. 开发版插件说明

开发阶段可以有一个独立 Dev UI，但不要和正式 UI 混在一起。

Dev UI 可以支持：

```text
显示 taskId
显示 errorCode
显示 failedStage
复制错误日志
查看 DSL 摘要
复制 DSL
下载 DSL
```

但正式用户版不展示。

v0.1 开发可以先用 Dev UI 辅助，但 PRD 中正式插件交互只按 Upload / Preview / Progress / Done / Error 设计。

------

## 17. 原图对比策略

插件面板内不做原图 / 生成结果对比。

v0.1 使用：

```text
Figma 画布中的 Original PNG Reference 隐藏图层
```

用户或开发人员可以：

```text
打开隐藏原图参考层
手动调整透明度
使用 Figma 画布对比
使用外部贴图工具辅助对比
```

内部批量对比放到测试后台，不放在插件 UI 里。

------

## 18. 生成结果位置

Renderer 渲染完成后应：

```text
在当前 Figma 页面创建 root Frame
选中 root Frame
滚动并缩放到 root Frame
```

这样 DoneView 不需要提供“查看结果”按钮。

------

## 19. 图层命名要求

虽然插件 UI 不展示图层结构，但生成后的 Figma 图层需要可读。

命名建议：

```text
Original PNG Reference
Navigation Bar
Search Bar
Product Card
Product Image
Product Title
Product Price
TabBar
Tab Item - Home
Fallback Region
```

不要生成大量无意义名称：

```text
Layer 1
Group 2
Rectangle 999
```

------

## 20. 插件 MVP 成功标准

插件 v0.1 可以认为成功，当满足：

```text
1. 用户能选择 PNG
2. 插件能显示预览
3. 插件能发起生成
4. 插件能显示简单进度
5. 插件能从后端拿到 DSL
6. 插件能调用 Renderer
7. Figma 画布能生成完整 root Frame
8. 生成完成后能提示用户
9. 失败时能显示友好错误
10. 不需要用户理解内部技术细节
```

------

## 21. 插件 v0.1 明确不做

```text
历史记录
最近任务
插件内质量分
插件内详细报告
插件内原图对比
插件内热力图
用户账号
额度展示
支付
设置页
模型选择
批量上传
多页面管理
一键组件化
代码生成
```

------

## 22. 风险与取舍

### 22.1 速度风险

如果插件端承担太多逻辑，会拖慢主链路。

处理：

```text
识别逻辑放后端
Renderer 只渲染
插件 UI 保持简单
```

### 22.2 UI 膨胀风险

如果加入历史记录、质量报告、对比工具，MVP 会变重。

处理：

```text
所有非核心 UI 后置
```

### 22.3 用户预期风险

用户可能认为所有内容都能 100% 编辑。

处理：

```text
在说明文案中强调“生成可编辑设计稿”
复杂图片区域可能以图片形式保留
```

可选轻量文案：

```text
复杂图片区域可能会作为图片保留，以保证整体还原效果。
```

------

## 23. v0.1 结论

Figma 插件 v0.1 的交互流程必须极简：

```text
上传
预览
生成
完成
失败
```

第一版不要把插件做成完整产品后台。

插件的唯一目标是服务：

```text
PNG → DSL → Figma 可编辑稿
```

只要用户能顺利上传 PNG，并在 Figma 画布中看到生成结果，插件 v0.1 就完成了核心任务。

```
这就是第十份文档：

**`06_Figma插件设计文档/01_插件MVP交互流程_v0.1.md`**

下一份建议继续输出：

**`07_后端接口文档/01_API总览_v0.1.md`**
```