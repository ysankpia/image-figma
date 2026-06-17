# 本地设置

当前默认运行面是仓库根目录的 Slice Studio。

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

- Bun for Slice Studio scripts.
- Node.js / pnpm for workspace checks.
- Git.
- Go / Python only when explicitly maintaining historical Go/Python routes.

## Install

仓库依赖：

```bash
pnpm install
```

## Run Slice Studio

本地启动：

```bash
pnpm run dev
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
storage/app.sqlite
storage/users/{userId}/projects/{projectId}/originals/
storage/users/{userId}/projects/{projectId}/exports/
```

兼容说明：

```text
已有旧本地项目可能仍在 storage/projects/{projectId}/...
当前运行时继续兼容读取，新的上传和导出写入 users/{userId}/projects/{projectId}/...
```

`storage/` 是运行数据，不提交。不要删除用户正在使用的项目 storage，除非用户明确要求。

## Environment

Slice Studio 默认读取根目录 `.env.local`。复制示例：

```bash
cp .env.example .env.local
```

常用本地配置：

```text
NEXT_PUBLIC_SLICE_STUDIO_API_URL=
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_LOAD_LOCAL_ENV=true
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_AUTH_COOKIE_NAME=slice_studio_session
SLICE_STUDIO_AUTH_SESSION_TTL_DAYS=30
SLICE_STUDIO_AUTH_SECURE_COOKIES=false
SLICE_STUDIO_LOCAL_OWNER_EMAIL=local@slicestudio.dev
SLICE_STUDIO_LOCAL_OWNER_NAME=Local Owner
SLICE_STUDIO_LOCAL_OWNER_PASSWORD=slice-studio-local-owner
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
pnpm run check
pnpm run build
git diff --check
git status --short --branch
```

如果只需要跑 Slice Studio 单元测试：

```bash
pnpm run test
```

## Manual Smoke

1. 启动 Slice Studio。
2. 打开 `/projects`。
3. 新建项目并上传多张 UI 图。
4. 在 Review Workbench 手动画框。
5. 保存后刷新页面，确认页面和 slices 仍存在。
6. 导出 `assets.zip`，确认 ZIP 包含 originals、slices、manifest 和 project metadata。
7. 导出 `project.zip`，确认 ZIP 包含 `design.pen`、manifest、originals、remainders 和 visible slices。
8. 如果配置了 AI provider，点击 `AI 当前页`，确认返回 boxes 并保存成普通 slices。
9. 如果项目有多页，点击 `AI 全部页`，确认 batch progress、completed/failed/skipped/new assets 统计正常。
10. 对重要项目，打开 `project.zip/design.pen` 做一次视觉检查。

## 189 生产化入口

在 189 的当前阶段，浏览器侧默认走 Next.js 同源 `/api`，所以本地同时启动 Web 和 API 后，登录态会通过浏览器 cookie 正常回传给服务端页面保护。

新增入口：

- `/` landing page
- `/login`
- `/projects`
- `/projects/:projectId/review`
- `/settings`
- `/billing`
- `/admin`

本地 API smoke：

```bash
pnpm run smoke
```

`bun run smoke` 会创建临时项目、上传页面、重命名/替换/删除页面、保存 slices、导出 `assets.zip` 和 `project.zip`，最后删除临时项目。它不覆盖真实 AI provider；AI 需要单独用真实 key 做手动 smoke。

## Historical Python Pencil Route

只在显式维护 `archive/legacy-code/services/pencil-python-backend` 时使用：

```bash
cd archive/legacy-code/services/pencil-python-backend
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
cd archive/legacy-code/services/pencil-python-backend
make slice-acceptance \
  IMAGE=/absolute/path/to/image-or-dir \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

## Historical Go Draft Route

只在显式恢复或调试 Go Draft 时使用：

```bash
cd archive/legacy-code/services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver
```

Go 检查：

```bash
cd archive/legacy-code/services/backend-go
go test ./...
```

Draft CLI 示例：

```bash
cd archive/legacy-code/services/backend-go
go run ./cmd/draftcompile -input /absolute/path/to/input.png -out /tmp/draft-out
```

## Historical Python Upload Preview

只在明确调试历史 `/api/upload-preview` 时启动：

```bash
cd archive/legacy-code/backend
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Figma Plugin / Renderer

Figma 插件和 Renderer 属于历史/延后 Draft runtime 资产，不是当前 Slice Studio 默认交付路径。只有任务明确恢复插件渲染时才跑：

```bash
cd archive/legacy-code/figma-plugin
pnpm run build

cd ../packages/image-to-figma-renderer
pnpm run typecheck
pnpm run test
```
