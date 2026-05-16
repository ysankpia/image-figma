下面继续输出第十一份核心文档：

**`07_后端接口文档/01_API总览_v0.1.md`**

~~~markdown
# 后端 API 总览 v0.1

文档名称：后端 API 总览  
所属项目：Image-to-Figma Design  
当前版本：v0.1  
版本性质：MVP 后端接口设计文档  
适用阶段：第一版核心链路开发  
最后更新：2026-05-16  

---

## 1. 文档目的

本文档用于定义 Image-to-Figma Design v0.1 后端 API 的整体设计。

v0.1 后端 API 的核心目标是支撑：

```text
Figma 插件上传 PNG
→ 后端创建任务
→ 后端处理并生成 DSL
→ Figma 插件获取 DSL
→ Renderer 渲染到 Figma
~~~

API 设计必须简单、稳定、易调试，不做复杂商业化、权限、支付、额度、历史任务等外围能力。

------

## 2. API 设计原则

v0.1 API 遵循以下原则：

```text
1. 围绕单张 PNG → DSL → Figma 主链路设计
2. 接口数量尽量少
3. 返回结构清晰稳定
4. 所有任务必须有 taskId
5. 所有错误必须有 errorCode
6. 图片资产通过 assetId 管理
7. 开发阶段优先本地文件 URL
8. 生产阶段预留 OSS / 签名 URL
```

------

## 3. v0.1 API 范围

v0.1 必须包含以下接口：

```text
GET  /api/health
POST /api/upload
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/assets/{assetId}
```

可选接口：

```text
POST /api/tasks/{taskId}/retry
GET  /api/tasks/{taskId}/logs
```

v0.1 不做：

```text
用户注册 / 登录接口
支付接口
额度接口
历史记录接口
团队接口
权限管理接口
批量上传接口
质量评分报告接口
```

------

## 4. API 基础地址

开发环境示例：

```text
http://localhost:8000/api
```

内测环境示例：

```text
https://dev-api.example.com/api
```

生产环境后续示例：

```text
https://api.example.com/api
```

------

## 5. 通用返回结构

### 5.1 成功返回

```json
{
  "success": true,
  "data": {}
}
```

### 5.2 失败返回

```json
{
  "success": false,
  "error": {
    "code": "UPLOAD_FAILED",
    "message": "图片上传失败，请检查网络后重试。",
    "detail": "Internal debug detail",
    "stage": "upload",
    "taskId": "task_001"
  }
}
```

### 5.3 字段说明

| 字段            | 类型            | 必填     | 说明             |
| --------------- | --------------- | -------- | ---------------- |
| `success`       | boolean         | 是       | 请求是否成功     |
| `data`          | object          | 成功时是 | 成功数据         |
| `error`         | object          | 失败时是 | 错误信息         |
| `error.code`    | string          | 是       | 错误码           |
| `error.message` | string          | 是       | 用户友好错误信息 |
| `error.detail`  | string / object | 否       | 开发调试信息     |
| `error.stage`   | string          | 否       | 失败阶段         |
| `error.taskId`  | string          | 否       | 关联任务 ID      |

------

## 6. 任务状态

v0.1 任务状态：

```text
pending
uploaded
processing
completed
failed
```

### 6.1 状态说明

| 状态         | 说明                    |
| ------------ | ----------------------- |
| `pending`    | 任务已创建，等待处理    |
| `uploaded`   | 原图已上传完成          |
| `processing` | 后端正在识别 / 生成 DSL |
| `completed`  | DSL 已生成成功          |
| `failed`     | 任务失败                |

### 6.2 插件端展示映射

| 后端状态     | 插件展示 |
| ------------ | -------- |
| `pending`    | 准备中   |
| `uploaded`   | 上传完成 |
| `processing` | 生成中   |
| `completed`  | 生成完成 |
| `failed`     | 生成失败 |

------

## 7. 任务阶段 stage

内部阶段：

```text
upload
preprocess
ocr
ai_analyze
asset_crop
dsl_build
dsl_validate
completed
failed
```

这些阶段主要用于日志和开发调试。

普通用户插件 UI 不暴露这些技术阶段。

------

## 8. GET /api/health

### 8.1 用途

健康检查接口，用于确认后端服务是否运行。

### 8.2 请求

```http
GET /api/health
```

### 8.3 成功返回

```json
{
  "success": true,
  "data": {
    "status": "ok",
    "version": "0.1",
    "time": "2026-05-16T00:00:00Z"
  }
}
```

------

## 9. POST /api/upload

### 9.1 用途

上传 PNG，并创建识别任务。

v0.1 推荐上传即创建任务，减少接口复杂度。

核心流程：

```text
插件上传 PNG
→ 后端保存原图
→ 创建 taskId
→ 启动处理任务
→ 返回 taskId
```

### 9.2 请求

```http
POST /api/upload
Content-Type: multipart/form-data
```

表单字段：

| 字段            | 类型        | 必填 | 说明                      |
| --------------- | ----------- | ---- | ------------------------- |
| `file`          | file        | 是   | PNG 图片                  |
| `source`        | string      | 否   | 来源，默认 `figma_plugin` |
| `clientVersion` | string      | 否   | 插件版本                  |
| `options`       | string JSON | 否   | 可选配置，v0.1 可忽略     |

### 9.3 请求示例

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@home.png" \
  -F "source=figma_plugin" \
  -F "clientVersion=0.1.0"
```

### 9.4 成功返回

```json
{
  "success": true,
  "data": {
    "taskId": "task_001",
    "status": "processing",
    "message": "图片已上传，正在生成设计稿。",
    "image": {
      "fileName": "home.png",
      "format": "png",
      "width": 390,
      "height": 844,
      "size": 1240000
    }
  }
}
```

### 9.5 失败返回示例

#### 非 PNG

```json
{
  "success": false,
  "error": {
    "code": "INVALID_IMAGE_FORMAT",
    "message": "当前仅支持 PNG 格式，请重新上传 PNG 图片。",
    "stage": "upload"
  }
}
```

#### 图片过大

```json
{
  "success": false,
  "error": {
    "code": "IMAGE_TOO_LARGE",
    "message": "图片过大，请压缩到 10MB 以内后重新上传。",
    "stage": "upload"
  }
}
```

------

## 10. GET /api/tasks/{taskId}

### 10.1 用途

查询任务状态。

插件在 ProgressView 中轮询该接口，直到任务 completed 或 failed。

### 10.2 请求

```http
GET /api/tasks/{taskId}
```

### 10.3 成功返回：处理中

```json
{
  "success": true,
  "data": {
    "taskId": "task_001",
    "status": "processing",
    "progress": 65,
    "message": "生成中",
    "stage": "ai_analyze",
    "createdAt": "2026-05-16T00:00:00Z",
    "updatedAt": "2026-05-16T00:00:12Z"
  }
}
```

### 10.4 成功返回：完成

```json
{
  "success": true,
  "data": {
    "taskId": "task_001",
    "status": "completed",
    "progress": 100,
    "message": "生成完成",
    "dslUrl": "/api/tasks/task_001/dsl",
    "createdAt": "2026-05-16T00:00:00Z",
    "updatedAt": "2026-05-16T00:00:30Z",
    "durationMs": 30000
  }
}
```

### 10.5 成功返回：失败

```json
{
  "success": true,
  "data": {
    "taskId": "task_001",
    "status": "failed",
    "progress": 100,
    "message": "生成失败，请重试或重新上传。",
    "error": {
      "code": "AI_ANALYZE_FAILED",
      "message": "图片识别失败，请换一张更清晰的 PNG 截图。",
      "stage": "ai_analyze"
    },
    "createdAt": "2026-05-16T00:00:00Z",
    "updatedAt": "2026-05-16T00:00:30Z",
    "durationMs": 30000
  }
}
```

### 10.6 stage 字段说明

`stage` 可以返回给插件，但普通用户 UI 不一定显示。

开发版可显示。

------

## 11. GET /api/tasks/{taskId}/dsl

### 11.1 用途

获取任务生成的 DSL v0.1。

插件在任务 completed 后调用该接口。

### 11.2 请求

```http
GET /api/tasks/{taskId}/dsl
```

### 11.3 成功返回

```json
{
  "success": true,
  "data": {
    "dsl": {
      "version": "0.1",
      "taskId": "task_001",
      "page": {},
      "assets": [],
      "root": {},
      "meta": {}
    }
  }
}
```

### 11.4 可选简化返回

也可以直接返回 DSL：

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

v0.1 推荐统一包一层：

```json
{
  "success": true,
  "data": {
    "dsl": {}
  }
}
```

这样错误结构统一。

### 11.5 失败返回

#### 任务不存在

```json
{
  "success": false,
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "任务不存在。",
    "stage": "task"
  }
}
```

#### 任务未完成

```json
{
  "success": false,
  "error": {
    "code": "TASK_NOT_COMPLETED",
    "message": "任务尚未完成，请稍后再试。",
    "stage": "task",
    "taskId": "task_001"
  }
}
```

#### DSL 不存在

```json
{
  "success": false,
  "error": {
    "code": "DSL_NOT_FOUND",
    "message": "生成结果不存在，请重新生成。",
    "stage": "dsl",
    "taskId": "task_001"
  }
}
```

------

## 12. GET /api/assets/{assetId}

### 12.1 用途

获取图片资产。

v0.1 有两种实现方式：

```text
方式 A：直接返回图片二进制
方式 B：返回资源信息和 url
```

为了 Figma 插件加载图片更简单，推荐：

```text
DSL assets 中直接提供 url
/api/assets/{assetId} 作为备用接口
```

### 12.2 请求

```http
GET /api/assets/{assetId}
```

### 12.3 成功返回：资源信息

```json
{
  "success": true,
  "data": {
    "assetId": "asset_product_001",
    "type": "image",
    "role": "product_image",
    "url": "http://localhost:8000/files/assets/task_001/product_001.jpg",
    "format": "jpeg",
    "width": 96,
    "height": 96,
    "storage": "local"
  }
}
```

### 12.4 失败返回

```json
{
  "success": false,
  "error": {
    "code": "ASSET_NOT_FOUND",
    "message": "图片资源不存在。",
    "stage": "asset"
  }
}
```

------

## 13. 静态文件访问

开发阶段可以提供静态文件访问：

```text
/files/uploads/{taskId}/original.png
/files/assets/{taskId}/{assetName}
```

示例：

```text
http://localhost:8000/files/uploads/task_001/original.png
http://localhost:8000/files/assets/task_001/product_001.jpg
```

这些 URL 会写入 DSL assets 中。

生产阶段替换为 OSS 签名 URL。

------

## 14. 可选接口：POST /api/tasks/{taskId}/retry

### 14.1 用途

重试失败任务。

v0.1 可以先不做。
如果实现成本低，可以作为开发版能力。

### 14.2 请求

```http
POST /api/tasks/{taskId}/retry
```

### 14.3 成功返回

```json
{
  "success": true,
  "data": {
    "taskId": "task_001_retry_001",
    "status": "processing",
    "message": "已重新开始生成。"
  }
}
```

### 14.4 说明

正式用户版插件 v0.1 不强依赖该接口。

------

## 15. 可选接口：GET /api/tasks/{taskId}/logs

### 15.1 用途

获取任务日志。

仅用于开发版 / 内部测试。

v0.1 正式用户插件不使用。

### 15.2 请求

```http
GET /api/tasks/{taskId}/logs
```

### 15.3 成功返回

```json
{
  "success": true,
  "data": {
    "taskId": "task_001",
    "logs": [
      {
        "time": "2026-05-16T00:00:01Z",
        "stage": "upload",
        "level": "info",
        "message": "Upload completed"
      },
      {
        "time": "2026-05-16T00:00:10Z",
        "stage": "ocr",
        "level": "info",
        "message": "OCR completed",
        "data": {
          "textBlocks": 42
        }
      }
    ]
  }
}
```

------

## 16. 任务创建策略

v0.1 推荐：

```text
POST /api/upload
→ 保存图片
→ 创建 taskId
→ 直接启动处理
→ 返回 taskId
```

不推荐第一版拆太复杂：

```text
先 upload
再 create task
再 start task
再 confirm task
```

原因：

```text
MVP 阶段要减少接口数量
插件端逻辑更简单
更容易调通主链路
```

------

## 17. 插件轮询策略

### 17.1 轮询接口

```text
GET /api/tasks/{taskId}
```

### 17.2 建议轮询间隔

```text
1s～2s
```

### 17.3 超时策略

建议插件端设置超时：

```text
简单页面：90s
复杂页面：120s
```

如果超时：

```json
{
  "code": "TASK_TIMEOUT",
  "message": "生成时间较长，请稍后重试。"
}
```

------

## 18. progress 字段

### 18.1 返回示例

```json
{
  "progress": 65
}
```

### 18.2 progress 映射建议

| 阶段         | progress |
| ------------ | -------- |
| uploaded     | 10       |
| preprocess   | 20       |
| ocr          | 35       |
| ai_analyze   | 60       |
| asset_crop   | 75       |
| dsl_build    | 85       |
| dsl_validate | 95       |
| completed    | 100      |

### 18.3 插件展示

插件可以只显示进度条，不显示内部阶段名。

------

## 19. message 字段

`message` 返回给插件端展示。

后端可以返回非技术化文案：

```text
上传完成
处理中
生成中
正在写入 Figma
生成完成
生成失败
```

不要返回：

```text
OCR 中
AI 分析中
DSL 校验中
```

技术阶段放在 `stage` 字段，开发版使用。

------

## 20. 错误码规范

### 20.1 通用错误码

```text
UNKNOWN_ERROR
VALIDATION_ERROR
INTERNAL_SERVER_ERROR
```

### 20.2 上传错误

```text
UPLOAD_FAILED
INVALID_IMAGE_FORMAT
IMAGE_TOO_LARGE
IMAGE_READ_FAILED
```

### 20.3 处理错误

```text
PREPROCESS_FAILED
OCR_FAILED
AI_ANALYZE_FAILED
ASSET_CROP_FAILED
DSL_BUILD_FAILED
DSL_SCHEMA_ERROR
DSL_REPAIR_FAILED
```

### 20.4 任务错误

```text
TASK_NOT_FOUND
TASK_NOT_COMPLETED
TASK_FAILED
TASK_TIMEOUT
```

### 20.5 资源错误

```text
ASSET_NOT_FOUND
ASSET_URL_EXPIRED
ASSET_LOAD_FAILED
```

------

## 21. 错误阶段 stage

支持：

```text
upload
preprocess
ocr
ai_analyze
asset_crop
dsl_build
dsl_validate
dsl_repair
task
asset
unknown
```

------

## 22. 前端错误文案映射

插件端不直接展示 error.code。

建议映射：

| error.code             | 用户文案                                   |
| ---------------------- | ------------------------------------------ |
| `INVALID_IMAGE_FORMAT` | 当前仅支持 PNG 格式，请重新上传 PNG 图片。 |
| `IMAGE_TOO_LARGE`      | 图片过大，请压缩后重新上传。               |
| `UPLOAD_FAILED`        | 图片上传失败，请检查网络后重试。           |
| `OCR_FAILED`           | 图片文字识别失败，请换一张更清晰的截图。   |
| `AI_ANALYZE_FAILED`    | 图片识别失败，请换一张更清晰的 PNG 截图。  |
| `DSL_BUILD_FAILED`     | 生成失败，请重试。                         |
| `ASSET_LOAD_FAILED`    | 部分图片资源加载失败，请重新生成。         |
| `TASK_TIMEOUT`         | 生成时间较长，请稍后重试。                 |
| `UNKNOWN_ERROR`        | 生成失败，请稍后重试。                     |

------

## 23. 图片上传限制

v0.1 建议：

```text
格式：PNG
大小：≤ 10MB
宽度：建议 320～1080px
高度：建议 ≤ 5000px
```

超过建议尺寸：

```text
可以提示风险
不一定拒绝
```

超过硬限制：

```text
直接拒绝
```

------

## 24. DSL 返回要求

后端返回的 DSL 必须满足：

```text
version = 0.1
taskId 与任务一致
page.width / height 有效
assets 是数组
root 存在
root.type = frame
root.children 是数组
所有 element.id 唯一
所有 image source.assetId 可在 assets 中找到
```

如果 DSL 校验失败，任务应标记为 failed，并返回：

```text
DSL_SCHEMA_ERROR
```

------

## 25. Asset URL 要求

DSL 中每个 asset 必须提供插件可访问的 URL：

```json
{
  "assetId": "asset_product_001",
  "url": "http://localhost:8000/files/assets/task_001/product_001.jpg"
}
```

开发阶段：

```text
local URL
```

生产阶段：

```text
signed OSS URL
```

------

## 26. 安全策略 v0.1

v0.1 开发阶段可暂时简化鉴权。

建议：

```text
本地开发：无鉴权
内测环境：简单 token
生产环境：正式账号 / 权限 / 签名 URL
```

v0.1 接口结构应预留：

```text
Authorization Header
```

但不强制复杂实现。

------

## 27. 请求头建议

插件请求可带：

```http
Authorization: Bearer <token>
X-Client-Version: 0.1.0
X-Client-Source: figma_plugin
```

v0.1 开发阶段可忽略 Authorization。

------

## 28. 版本字段

所有关键响应建议包含版本信息：

```json
{
  "apiVersion": "0.1"
}
```

或者在 health 中返回。

DSL 自身必须包含：

```json
{
  "version": "0.1"
}
```

------

## 29. 后端目录映射建议

API 文件建议：

```text
backend/app/api/
├─ routes_health.py
├─ routes_upload.py
├─ routes_tasks.py
└─ routes_assets.py
```

服务文件：

```text
backend/app/services/
├─ upload_service.py
├─ task_service.py
├─ asset_service.py
└─ storage_service.py
```

------

## 30. API 调用主流程示例

### 30.1 插件上传

```http
POST /api/upload
```

返回：

```json
{
  "success": true,
  "data": {
    "taskId": "task_001",
    "status": "processing"
  }
}
```

### 30.2 插件轮询

```http
GET /api/tasks/task_001
```

返回：

```json
{
  "success": true,
  "data": {
    "taskId": "task_001",
    "status": "completed",
    "progress": 100,
    "dslUrl": "/api/tasks/task_001/dsl"
  }
}
```

### 30.3 插件获取 DSL

```http
GET /api/tasks/task_001/dsl
```

返回：

```json
{
  "success": true,
  "data": {
    "dsl": {
      "version": "0.1",
      "taskId": "task_001",
      "page": {},
      "assets": [],
      "root": {},
      "meta": {}
    }
  }
}
```

### 30.4 插件渲染

```text
renderDesign(dsl)
```

------

## 31. v0.1 不提供的 API

以下接口不进入 v0.1：

```text
POST /api/auth/login
POST /api/auth/register
GET  /api/user/me
GET  /api/tasks/history
GET  /api/reports/{taskId}
GET  /api/quality/{taskId}
POST /api/batch-upload
POST /api/codegen
POST /api/componentize
POST /api/payment
GET  /api/billing
GET  /api/usage
```

------

## 32. API 验收标准

v0.1 API 可以认为完成，当满足：

```text
1. health 接口可用
2. upload 接口可上传 PNG 并返回 taskId
3. task 接口可查询任务状态
4. task completed 后可获取 DSL
5. DSL 中图片资源 URL 可访问
6. 错误返回包含 error.code 和 message
7. 非 PNG 会被拒绝
8. 图片过大会被拒绝
9. 任务失败时可返回明确错误
10. 插件端可基于这些接口完成主链路
```

------

## 33. 版本结论

v0.1 API 的目标不是完整平台接口，而是支撑第一版主链路：

```text
上传 PNG
→ 查询任务
→ 获取 DSL
→ 获取图片资源
```

接口必须保持简单、稳定、易调试。

所有和主链路无关的接口，统一后置。

```
这就是第十一份文档：

**`07_后端接口文档/01_API总览_v0.1.md`**

下一份建议继续输出：

**`10_开发计划与任务拆分/01_MVP开发里程碑_v0.1.md`**
```