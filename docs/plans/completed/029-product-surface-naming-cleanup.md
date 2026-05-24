# M29 Product Surface Naming Cleanup

- 状态：completed
- 创建日期：2026-05-24
- 完成日期：2026-05-24
- 负责人：未指定

## Goal

把当前产品路径里的历史 M30 命名清掉，让 API、后端编排、storage/report、插件调用和当前文档使用产品语义。

本阶段只做机械命名迁移，不改变 M29 source truth、M29.5 replay plan、plan-driven materializer、DSL schema、Renderer 或插件交互行为。

## Scope

包含：

- 新正式上传入口为 `POST /api/upload-preview`。
- 正式 DSL 入口保持 `GET /api/tasks/{taskId}/dsl`。
- materialization diagnostics 入口为 `GET /api/tasks/{taskId}/materialization`。
- 后端编排文件、route 文件、pipeline 类型、profile 类型和测试文件改为 upload preview 命名。
- storage task root 改为 `storage/upload_previews/{taskId}`。
- materialized output 目录改为 `materialized_design/`，DSL 文件改为 `design.dsl.json`，report 文件改为 `materialization_report.json`。
- 插件 API client 改为 `uploadPngPreview`，上传路径改为 `/upload-preview`。
- 文档、AGENTS、README、API contract、testing strategy、code map 和 env vars 同步当前产品语义。

不包含：

- 不改 owner/relation/replay/materialization 算法。
- 不重写 plan materializer。
- 不恢复 compare UI 或 M29 Direct product route。
- 不保留旧 upload preview env/route/storage alias；项目未上线，没有兼容包袱。
- 不删除历史 ADR、completed plans 或 git history 中的旧阶段记录。

## Changes

- `backend/app/m30_upload_pipeline.py` 重命名为 `backend/app/upload_preview_pipeline.py`。
- `backend/app/routes/upload_m30_preview.py` 重命名为 `backend/app/routes/upload_preview.py`。
- `run_m30_preview_pipeline` 改为 `run_upload_preview_pipeline`。
- `M30UploadPipelineError` 改为 `UploadPreviewPipelineError`。
- `M30PipelinePaths` 改为 `UploadPreviewPaths`。
- `M30ArtifactPolicy` 改为 `UploadPreviewArtifactPolicy`。
- `M30PreviewProfile` 改为 `UploadPreviewProfile`。
- 配置只读取 `UPLOAD_PREVIEW_PROFILE`。
- route `/api/tasks/{taskId}/m29-materialization` 替换为 `/api/tasks/{taskId}/materialization`。
- 插件从 `uploadPngM30Preview` 改为 `uploadPngPreview`。
- 测试文件从 `test_m30_upload_pipeline.py` 改为 `test_upload_preview_pipeline.py`。

## Acceptance

- `/api/upload-preview -> /api/tasks/{taskId}/dsl` 主流程保持不变。
- `/api/tasks/{taskId}/materialization` 返回当前 materialization report。
- 旧 `/api/upload-m30-preview` 和 `/api/tasks/{taskId}/m29-materialization` 不再是 route。
- 已下线的 compare/legacy diagnostics route 继续返回 404。
- 当前产品 API、后端编排、插件调用、storage/report 命名不再使用历史 M30 preview 命名。

## Validation

阶段回归命令：

```bash
cd backend
uv run pytest \
  tests/test_upload_preview_pipeline.py \
  tests/test_routes_tasks.py \
  tests/test_upload_flow.py \
  tests/test_config_env.py \
  tests/test_m29_plan_materializer.py \
  -q
cd ..
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
git diff --check
```

静态命名检查：

```bash
rg -n "upload-m30-preview|m30_upload_pipeline|upload_m30_preview|M30Upload|M30Pipeline|M30Preview|M30_PREVIEW|M29_PREVIEW|m30_1_uploads|M3011StageTimings|m29-materialization" backend/app backend/tests figma-plugin/src AGENTS.md README.md backend/README.md docs/architecture/api-contracts.md docs/engineering/testing-strategy.md docs/engineering/current-mainline-code-map.md docs/reference/env-vars.md
```

Expected: no matches.
