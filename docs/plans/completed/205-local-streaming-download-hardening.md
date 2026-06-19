# 205 本地流式下载加固

## Summary

当前暂不上 OSS。代码事实显示下载路径已经通过 `new Response(Bun.file(filePath))` 流式返回，下载请求没有进入 export job queue；线上“等很久才开始”主要仍来自首次 zip 生成，而不是下载接口排队。

本轮只补本地下载层的生产基本能力：明确 `Content-Length`、`Accept-Ranges`，并支持单段 `Range` 请求，让 40-50MB 本地文件下载可以被浏览器/代理正确续传。暂不改 zip 格式、不引入 OSS/CDN、不引入 Nginx/Caddy 大改。

## Scope

- `server/storage.ts` 的 `response()` 增加文件大小头和单段 byte range 响应。
- 所有调用 `storage.response()` 的下载/图片路由把请求的 `Range` header 传入。
- 补存储单测覆盖普通下载头、部分下载、后缀 range、非法 range。
- 更新 runtime 文档说明：当前本地下载是流式响应，不进队列；首次导出慢点在 zip 生成。

## Non-goals

- 不上 OSS。
- 不做 CDN。
- 不把 zip 生成改成 streaming zip writer。
- 不改变 signed URL token 合同。
- 不删除 export job queue；导出生成仍然需要异步任务。

## Validation

```bash
pnpm exec vitest run tests/storage.test.ts
pnpm run check
pnpm run build
git diff --check
```
