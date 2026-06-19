# 201 Slice Studio 导出缓存与下载反馈

## Summary

当前 Slice Studio 已经走正确的服务端 zip 导出方向：`assets.zip` 和 `project.zip/design.pen` 由后端生成，再返回 signed download URL。慢点不在最终文件下载，而在导出请求同步执行了裁切、OCR、remainder、Pencil 包生成和内存 zip。

本计划先做最小生产收口：保留现有公开 API，不新增数据库表，不引入异步 job 系统；在 zip 旁边增加文件级 fingerprint cache，项目未变化时直接复用已有 zip 并返回新的 signed URL。前端改成明确的导出状态和隐藏链接下载，避免 `window.location.href` 打断页面。

## Scope

改动范围：

- `server/export-cache.ts`
- `server/exporter.ts`
- `server/pencil-exporter.ts`
- `components/review/ReviewWorkbenchClient.tsx`
- 相关测试和文档

不做：

- 不把另一个项目的浏览器多文件下载导出搬进来。
- 不新增 `/export-jobs/*` API。
- 不改数据库 schema。
- 不改 zip 文件外部结构。
- 不改 Pencil `.pen` schema。
- 不改生产 Caddy、systemd、Postgres、YOLO 配置。

## Design

导出 fingerprint 直接由导出语义字段生成：

- export kind：`assets`、`pencil-project`、`pencil-page`
- exporter version
- project id/name/counts
- page id/index/name/size
- page original storage key, byte size, and modified time
- slice id/index/name/kind/cutMode/bbox

命中条件：

```text
zip file exists
cache metadata file exists
cache.exporterVersion matches
cache.fingerprint matches current fingerprint
cache.assetCount/pageCount matches current request
```

命中后不重新裁图、不重新 OCR、不重新 zip，只返回新的 signed URL。

缓存元数据写在 zip 旁边：

```text
assets.zip.cache.json
project.zip.cache.json
exports/pages/{pageId}/project.zip.cache.json
```

## Acceptance

- 第一次导出仍生成完整 zip。
- 第二次导出在项目未变化时复用 zip。
- 修改 slice bbox/name/cutMode、页面顺序、页面名、原图大小后 fingerprint 变化并重新生成。
- `assets.zip`、整项目 `project.zip`、单页 `project.zip` 都有缓存判断。
- 前端导出过程有明确状态，不再通过 `window.location.href` 跳走。
- 现有下载 URL 仍是 `/api/storage-download?token=...`。

## Validation

运行：

```bash
pnpm exec vitest run tests/export-cache.test.ts
pnpm run check
pnpm run build
git diff --check
git status --short --branch
```

如本地服务可用，再跑一次真实项目导出 smoke，确认二次导出命中缓存并能下载 zip。
