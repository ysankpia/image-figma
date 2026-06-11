# 本地设置

当前默认运行面是 Slice Studio：`apps/slice-studio`。

```text
1..N UI screenshots/design images
-> Slice Studio project workspace
-> saved SliceRecord boxes
-> assets.zip
-> project.zip / design.pen
```

旧 Pencil Python、Go Draft、Python `/api/upload-preview`、Codia Beta、M29 Direct compare、legacy M30、M31-M39 和 ONNX proposer 只在任务明确要求调试旧路径时启动。它们不是当前默认运行路径。

## Prerequisites

需要：

- Bun for `apps/slice-studio`.
- Node.js / pnpm for workspace checks.
- Git.
- Go / Python only when explicitly maintaining historical Go/Python routes.

## Install

仓库依赖：

```bash
pnpm install
```

Slice Studio 依赖：

```bash
cd apps/slice-studio
bun install
```

## Run Slice Studio

本地启动：

```bash
cd apps/slice-studio
bun run dev
```

默认端口：

```text
Next web:  http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
```

打开：

```text
http://127.0.0.1:3010/projects
```

本地数据：

```text
apps/slice-studio/storage/app.sqlite
apps/slice-studio/storage/projects/{projectId}/originals/
apps/slice-studio/storage/projects/{projectId}/exports/
```

`storage/` 是运行数据，不提交。不要删除用户正在使用的项目 storage，除非用户明确要求。

## Environment

Slice Studio 默认读取 `apps/slice-studio/.env.local`。复制示例：

```bash
cd apps/slice-studio
cp .env.example .env.local
```

常用本地配置：

```text
NEXT_PUBLIC_SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_LOAD_LOCAL_ENV=true
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_STORAGE_ROOT=./storage
SLICE_STUDIO_ALLOWED_ORIGIN=http://127.0.0.1:3010
SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5
SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=ts_m29_physical_evidence
SLICE_STUDIO_AI_SLICE_PROVIDER=openai_responses
SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY=4
```

OCR token 和 AI key 只能放在 `.env.local` 或进程环境，不能提交。

## Checks

默认检查：

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
git status --short --branch
```

如果只需要跑 Slice Studio 单元测试：

```bash
cd apps/slice-studio
bun run test
```

## Manual Smoke

1. 启动 Slice Studio。
2. 打开 `/projects`。
3. 新建项目并上传多张 UI 图。
4. 在 Review Workbench 手动画框或点击 `AI 当前页`。
5. 确认框出现在 canvas 和资产总览里。
6. 刷新页面，确认已保存的 slices 仍存在。
7. 导出 `assets.zip`。
8. 导出 `project.zip`。
9. 检查 `project.zip` 里有 `design.pen`、`manifest.json`、`project.json` 和 `assets/visible/*`。

## Historical Python Pencil Route

只在显式维护 `services/pencil-python-backend` 时使用：

```bash
cd services/pencil-python-backend
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike \
OCR_PROVIDER=none \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

旧工作台：

```text
http://127.0.0.1:8100/api/pencil/slice-projects/workspace
```

旧验收：

```bash
cd services/pencil-python-backend
make slice-acceptance \
  IMAGE=/absolute/path/to/image-or-dir \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

## Historical Go Draft Route

只在显式恢复或调试 Go Draft 时使用：

```bash
cd services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver
```

Go 检查：

```bash
cd services/backend-go
go test ./...
```

Draft CLI 示例：

```bash
cd services/backend-go
go run ./cmd/draftcompile -input /absolute/path/to/input.png -out /tmp/draft-out
```

## Historical Python Upload Preview

只在明确调试历史 `/api/upload-preview` 时启动：

```bash
cd backend
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Figma Plugin / Renderer

Figma 插件和 Renderer 属于历史/延后 Draft runtime 资产，不是当前 Slice Studio 默认交付路径。只有任务明确恢复插件渲染时才跑：

```bash
pnpm --filter @image-figma/figma-plugin run build
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```
