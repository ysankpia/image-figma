# 204 导出任务可观测与卡队列修复

## Summary

线上反馈“下载很慢”后实测发现：导出任务已经有 `job.id`，但不是完整任务系统。项目包 job 创建可以快速返回，可后续任务长期停在 `queued`，说明问题不是 signed URL 下载本身，而是进程内队列被前一个导出任务堵住。当前队列没有列表、取消、超时和足够的前端状态解释，用户只能看到“慢”。

## Scope

本轮补最小生产可用能力：

- `ExportJobRecord` 增加 `startedAt`，状态增加 `canceled`。
- 后端增加 `GET /api/projects/:projectId/export-jobs`。
- 后端增加 `DELETE /api/projects/:projectId/export-jobs/:jobId`，用于取消 queued job。
- running job 增加超时保护，默认 `SLICE_STUDIO_EXPORT_JOB_TIMEOUT_SECONDS=600`。
- 前端导出状态显示 job id 片段和等待/运行耗时。

不做：

- 不引入 Redis/BullMQ。
- 不新增数据库表。
- 不把导出拆成独立 worker process。
- 不改变 zip 格式、signed URL、同步导出兼容接口。

## Acceptance

- 用户可以通过 API 查到当前项目导出任务列表。
- 用户可以取消当前项目自己的 queued job。
- running job 不做假取消；当前进程内队列无法杀掉正在执行的导出函数，只能靠超时失败、进程重启或后续 worker 化解决。
- 队列中单个异步卡住任务不会在普通 async 情况下永久占住状态。
- 前端不再只显示“导出中”，而是显示 job id 和 elapsed time。

## Validation

```bash
pnpm exec vitest run tests/export-jobs.test.ts
pnpm run check
pnpm run build
git diff --check
```

线上验证：

- 部署会重启 API，清掉当前进程内卡住队列。
- 登录后创建项目包 job，应能看到 queued/running/succeeded，不应长期无解释停住。
