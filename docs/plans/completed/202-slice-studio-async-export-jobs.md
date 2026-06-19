# 202 Slice Studio 异步导出任务

## Summary

当前 `assets.zip`、当前页 `project.zip`、全项目 `project.zip` 的导出端点仍是同步长请求。缓存只能解决未变化内容的二次导出；第一次全项目项目包仍要在同一个 HTTP 请求里跑裁切、OCR、文本重建、remainder、Pencil 包校验和 zip 生成。大项目请求可能被浏览器、Cloudflare、反代或服务端 idle timeout 影响，用户体感也是按钮卡住。

本计划做最小正确修复：保留现有同步导出 API，不改 zip/schema/storage/download contract；新增进程内异步 export job 队列和轮询 API，让 Review Workbench 的三个导出按钮改走任务化路径。HTTP 请求只负责创建任务和查状态，真正生成 zip 在后台继续执行，完成后返回 signed download URL。

## Scope

新增/修改：

- `server/export-jobs.ts`
- `server/index.ts`
- `components/review/ReviewWorkbenchClient.tsx`
- `shared/types.ts`
- 测试和运行文档

不做：

- 不新增数据库表。
- 不引入 Redis/BullMQ/外部队列。
- 不改变 `assets.zip` / `project.zip` 内部结构。
- 不删除旧同步导出端点。
- 不改变 Caddy、systemd 或部署拓扑。

## Design

新增 API：

```text
POST /api/projects/:projectId/export-jobs
GET  /api/projects/:projectId/export-jobs/:jobId
```

创建请求：

```ts
{
  kind: "assets" | "project" | "page_project",
  pageId?: string
}
```

状态响应：

```ts
{
  ok: true,
  job: {
    id,
    projectId,
    kind,
    pageId,
    status: "queued" | "running" | "succeeded" | "failed",
    message,
    assetCount?,
    pageCount?,
    url?,
    cached?,
    error?,
    createdAt,
    updatedAt,
    finishedAt?
  }
}
```

进程内任务队列：

- 同一 Node/Bun API 进程内维护 `Map<jobId, ExportJob>`。
- 当前 API 进程最多同时跑一个导出任务；其余任务排队。
- 单任务执行旧有导出函数：`exportAssets`、`exportPencilProject`、`exportPencilProjectPage`。
- 导出函数内部已有 fingerprint cache；命中时任务会很快完成。
- 任务状态保留最近若干条，过期清理，避免内存无限增长。
- API 重启会丢失进行中的 job 状态；这轮接受，因为当前目标是切断长 HTTP 请求，不是做 durable worker。

## Acceptance

- 点击导出按钮后，创建 job 立即返回，不等待 zip 生成。
- 前端显示 queued/running/succeeded/failed 状态。
- job 成功后自动触发 signed URL 下载。
- 失败时用户看到错误，页面不丢失。
- 旧同步导出 API 仍可用。
- 缓存命中仍返回 `cached:true`。
- 大项目导出不再依赖一个长 POST 连接保持到完成。

## Validation

```bash
pnpm exec vitest run tests/export-jobs.test.ts tests/export-cache.test.ts
pnpm run check
pnpm run build
git diff --check
```

真实 API smoke：

```text
创建临时用户/项目
上传图片
保存 slice
创建 assets export job -> poll -> download
创建 project export job -> poll -> download
创建 page project export job -> poll -> download
重复创建项目包 job -> 应能走 cached:true
删除临时项目
```
