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
- 成功返回：`taskId`、文件信息、初始状态。
- 必须拒绝非 PNG 和过大图片。

`GET /api/tasks/{taskId}`

- 用途：查询任务状态。
- 返回：`taskId`、`status`、`stage`、`progress`、`message`。

`GET /api/tasks/{taskId}/dsl`

- 用途：获取任务 DSL。
- 仅在任务 completed 后成功。
- 未完成时返回明确错误。

`GET /api/assets/{assetId}`

- 用途：获取资产信息或文件访问。
- 开发阶段可以返回本地可访问 URL。

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
