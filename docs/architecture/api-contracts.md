# API Contracts

API v0.1 只服务单张 PNG -> DSL -> Figma 主链路。

## Contract Ownership

API 合同由后端和 Figma 插件共同遵守。任何接口路径、请求体、响应结构、错误码、任务状态变更，必须同步更新本文档和相关实现计划。

## Base URL

开发环境默认：

```text
http://localhost:8000/api
```

## Response Shape

成功：

```json
{
  "success": true,
  "data": {}
}
```

失败：

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

## Required Endpoints

`GET /api/health`

- 用途：确认后端服务运行。
- 返回：`status`、`version`、`time`。

`POST /api/upload`

- 用途：上传 PNG 并创建任务。
- 请求：multipart file。
- M9 成功后立即返回 completed deterministic region + hidden OCR candidate 任务。
- 成功返回：`taskId`、文件信息、状态、阶段和进度。
- 必须拒绝非 PNG、无法读取尺寸的 PNG 和过大图片。
- 默认大小上限：10MB。
- 返回 DSL 时，portrait/mobile-like PNG 默认包含 `fallback_region_header`、`fallback_region_content`、`fallback_region_bottom` 三个 region fallback。
- 如果 cropper 不支持该 PNG 格式，任务仍可 completed，DSL 退回整图 fallback 并带 `qualityFlags`。
- 上传链路会生成 visual primitives、OCR 和 DSL patch 调试结果。默认 `debug` 模式会在 DSL 中加入 hidden text candidates，但不改变 Figma 可见输出。

`GET /api/tasks/{taskId}`

- 用途：查询任务状态。
- 返回：`taskId`、`status`、`stage`、`progress`、`message`。

`GET /api/tasks/{taskId}/dsl`

- 用途：获取任务 DSL。
- 仅在任务 completed 后成功。
- 未完成时返回明确错误。
- 默认 `DSL_PATCH_MODE=debug` 时返回 enhanced DSL，包含 hidden `candidate_text`。
- `DSL_PATCH_MODE=off` 时返回 M7 base DSL。
- patch build 或 validation 失败时返回 base DSL。

`GET /api/tasks/{taskId}/primitives`

- 用途：获取 M8 visual primitive candidate 结果。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- primitive result 不存在返回 `PRIMITIVE_NOT_FOUND`。
- extraction 失败时仍返回 `success: true`，但 `data.status` 为 `failed`，并带 `error` 摘要。
- 返回的 `bbox` 使用整图像素坐标 `[x, y, width, height]`。

`GET /api/tasks/{taskId}/ocr`

- 用途：获取 M9 OCR candidate 结果。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- OCR result 不存在返回 `OCR_NOT_FOUND`。
- OCR failed 时仍返回 `success: true`，但 `data.status` 为 `failed`，并带 `error`。
- 返回的 `bbox` 使用整图像素坐标 `[x, y, width, height]`。

`GET /api/tasks/{taskId}/dsl-patch`

- 用途：获取 M9 DSL patch 结果。
- 只读调试接口，不被插件主流程依赖。
- task 不存在返回 `TASK_NOT_FOUND`。
- patch result 不存在返回 `DSL_PATCH_NOT_FOUND`。
- patch failed 时仍返回 `success: true`，但 `data.status` 为 `failed`，并带 `error`。
- M9 patch 只允许添加 hidden `candidate_text`。

`GET /api/assets/{assetId}`

- 用途：获取资产信息或文件访问。
- 后端返回资产元信息，不直接返回文件 bytes。
- 开发阶段 URL 指向 `/files/uploads/...` 或 `/files/assets/...`。
- 如果多个任务有同名 `assetId`，当前返回最新匹配资产。后续再决定是否引入 task-scoped asset API。

## Static Files

后端挂载：

```text
/files/uploads
/files/assets
```

DSL 中的 asset URL 指向这些路径，方便 Figma Renderer 直接 fetch 图片。

## Error Codes

- `INVALID_FILE_TYPE`
- `INVALID_IMAGE_DIMENSIONS`
- `FILE_TOO_LARGE`
- `UPLOAD_FAILED`
- `TASK_NOT_FOUND`
- `DSL_NOT_READY`
- `DSL_NOT_FOUND`
- `ASSET_NOT_FOUND`
- `PRIMITIVE_NOT_FOUND`
- `PRIMITIVE_EXTRACTION_FAILED`
- `OCR_NOT_FOUND`
- `OCR_EXTRACTION_FAILED`
- `DSL_PATCH_NOT_FOUND`
- `DSL_PATCH_BUILD_FAILED`
- `DSL_PATCH_VALIDATION_FAILED`
- `INTERNAL_ERROR`

## Plugin M5 Usage

M5 插件使用：

```text
POST /api/upload
GET /api/tasks/{taskId}
GET /api/tasks/{taskId}/dsl
```

即使后端当前立即返回 `completed`，插件仍按 task 查询流程实现，避免后续接真实异步处理时重写主链路。

M9 仍不改插件调用路径。插件不调用 OCR、primitives 或 dsl-patch endpoint。

## Optional Endpoints

以下接口不进入 P0：

- `POST /api/tasks/{taskId}/retry`
- `GET /api/tasks/{taskId}/logs`

## Contract Change Rules

- 不兼容字段变更必须升级 DSL 或 API 版本。
- 不允许插件依赖未文档化字段。
- 不允许后端返回未校验 DSL。
- 错误必须包含稳定 `code`。
- 普通用户文案和开发 detail 要分层。
