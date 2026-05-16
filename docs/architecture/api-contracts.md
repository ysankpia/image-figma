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
- M4 成功后立即返回 completed 假任务。
- 成功返回：`taskId`、文件信息、状态、阶段和进度。
- 必须拒绝非 PNG 和过大图片。
- 默认大小上限：10MB。

`GET /api/tasks/{taskId}`

- 用途：查询任务状态。
- 返回：`taskId`、`status`、`stage`、`progress`、`message`。

`GET /api/tasks/{taskId}/dsl`

- 用途：获取任务 DSL。
- 仅在任务 completed 后成功。
- 未完成时返回明确错误。

`GET /api/assets/{assetId}`

- 用途：获取资产信息或文件访问。
- M4 返回资产元信息，不直接返回文件 bytes。
- 开发阶段 URL 指向 `/files/uploads/...` 或 `/files/assets/...`。
- 如果多个任务有同名 `assetId`，M4 返回最新匹配资产。M5 前再决定是否引入 task-scoped asset API。

## Static Files

M4 后端挂载：

```text
/files/uploads
/files/assets
```

DSL 中的 asset URL 指向这些路径，方便 Figma Renderer 直接 fetch 图片。

## M4 Error Codes

- `INVALID_FILE_TYPE`
- `FILE_TOO_LARGE`
- `UPLOAD_FAILED`
- `TASK_NOT_FOUND`
- `DSL_NOT_READY`
- `DSL_NOT_FOUND`
- `ASSET_NOT_FOUND`
- `INTERNAL_ERROR`

## Plugin M5 Usage

M5 插件使用：

```text
POST /api/upload
GET /api/tasks/{taskId}
GET /api/tasks/{taskId}/dsl
```

即使 M4 后端当前立即返回 `completed`，插件仍按 task 查询流程实现，避免后续接真实异步处理时重写主链路。

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
