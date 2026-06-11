# 安全边界

v0.1 是 MVP 开发阶段，不伪装成完整商业化安全体系，但基本边界必须清楚。

## Input Safety

上传限制：

- 只接受 PNG。
- 限制文件大小。
- 校验 MIME 和文件头。
- 读取图片尺寸失败时拒绝。
- 不信任用户文件名。

路径处理：

- 服务端生成内部文件名。
- 禁止使用用户文件名拼接路径。
- 资产访问必须通过 `assetId` 映射。

## Error Safety

错误信息分层：

- 用户看到友好 message。
- 开发者日志记录 detail。
- API 不应向普通用户暴露堆栈、密钥、完整本地路径。

## Secret Handling

后续实现必须把模型 API Key、服务地址等放入环境变量。不得写入代码或文档示例中的真实值。

## CORS

Slice Studio 开发期默认通过 `SLICE_STUDIO_ALLOWED_ORIGIN=http://127.0.0.1:3010` 允许本地 Web 调用 API。进入内测或部署前必须收紧为明确域名。

历史 Figma plugin / Go Draft 路线可能使用 `CORS_ALLOW_ORIGINS=*` 方便 `https://www.figma.com` 调用本地服务；这不是当前 Slice Studio 默认配置。

## Storage Safety

本地存储阶段：

- 原图和裁切资产只用于当前任务。
- 生成 URL 必须可控。
- 删除策略后续在 runbook 中明确。

## Non-Goals

v0.1 不做：

- 用户认证。
- 多租户权限。
- 组织隔离。
- 完整合规系统。
- 审计后台。
- 支付安全。

这些只有在产品进入内测或商业化时才进入架构设计。
