# 本地设置

当前 Codia Beta 本地默认后端是 Go `services/backend-go/cmd/codiaserver`。历史 Python/FastAPI `/api/upload-preview` 仍保留为 DSL v0.1 M29 preview 路径。历史 M8-M28、M29 Direct compare、M29.0.x/M30 legacy bridge、M31-M39 downstream、SAM2/perception/icon/slice 等实验保留在 ADR、completed plans 和 git history 中，不再是本地默认运行路径。

## Prerequisites

需要：

- Node.js 24.x。当前开发机使用 Homebrew `node@24`。
- pnpm 10.33.2。
- Go 1.22+。
- Python 3.12.7，由 asdf 管理。
- Git。

`.tool-versions` 当前只固定：

```text
python 3.12.7
```

本机 asdf 当前没有 nodejs 插件，所以本轮不把 Node 写入 `.tool-versions`。

## Install

安装前端/共享包依赖：

```bash
pnpm install
```

安装保留 Python preview 依赖：

```bash
cd backend
uv sync
```

## Run Go Codia Beta Backend

插件 `Generate Beta` 调试默认启动 Go 后端：

```bash
cd services/backend-go
CODIA_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/codiaserver
```

真实 OCR：

```bash
cd services/backend-go
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
CODIA_SERVER_ADDR=127.0.0.1:8000 \
go run ./cmd/codiaserver
```

在线 detector：

```bash
cd services/backend-go
CODIA_SERVER_DETECTOR_ENABLED=true \
CODIA_UI_DETECTOR_BASE_URL=https://example-provider.test \
CODIA_UI_DETECTOR_MODEL=provider-model-id \
CODIA_UI_DETECTOR_API_KEY=... \
CODIA_SERVER_ADDR=127.0.0.1:8000 \
go run ./cmd/codiaserver
```

Go task artifacts 写到：

```text
services/backend-go/storage/codia_server/codia_previews/{taskId}/compile/
```

## Run Retained Python Preview Backend

只有调试 `Generate from PNG` / `/api/upload-preview` / DSL v0.1 时启动 Python 后端。默认 fake OCR、本地文件存储、M29 production artifact profile：

```bash
cd backend
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

开发诊断 profile：

```bash
cd backend
UPLOAD_PREVIEW_PROFILE=development uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`UPLOAD_PREVIEW_PROFILE` 只作为历史 alias 被读取；新命令使用 `UPLOAD_PREVIEW_PROFILE`。

## OCR

默认 OCR provider：

```bash
OCR_PROVIDER=fake
```

百度 PP-OCRv5 异步 OCR：

```bash
cd backend
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
BAIDU_PADDLE_OCR_MODEL=PP-OCRv5 \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

百度 token 是 bearer token，只能放在本地环境变量或未提交的 `.env.local` 中，不能写入仓库。当前 M29 preview path 把 OCR 当 required evidence；百度 OCR 失败时 task 会 failed，不会生成假 completed DSL。

## Build Figma Plugin

构建正式插件：

```bash
pnpm --filter @image-figma/figma-plugin run build
```

只构建底层 dev harness：

```bash
pnpm --filter @image-figma/figma-plugin run build:dev
```

Figma 插件主线程的 JavaScript 解析器比现代浏览器页面更保守。插件 bundle 目标使用 `es2017`，并在构建后扫描 `??`、`?.`、ESM import/export、`structuredClone`、`Object.hasOwn` 和 `for await` 残留。

## Run Checks

仓库级：

```bash
pnpm run check
```

只检查 DSL Schema 包：

```bash
pnpm --filter @image-figma/dsl-schema run typecheck
pnpm --filter @image-figma/dsl-schema run test
```

只检查 Renderer 包：

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

运行 Go Codia Beta 测试：

```bash
cd services/backend-go
go test ./internal/codia/... ./cmd/codiacompile ./cmd/codiaserver
```

运行保留 Python preview 测试：

```bash
cd backend
uv run pytest -q
```

当前 Codia Beta 完整验收：

```bash
cd services/backend-go && go test ./internal/codia/... ./cmd/codiacompile ./cmd/codiaserver
cd ../..
pnpm -r run test
pnpm -r run typecheck
git diff --check
git status --short --branch
```

## Figma Manual Smoke

1. 打开 Figma。
2. 进入插件开发模式。
3. 加载 `figma-plugin/manifest.json`。
4. 运行 `Image-to-Figma Design`。
5. 插件应打开 `420 x 560` 工具面板。
6. 启动 Go 后端：`cd services/backend-go && CODIA_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/codiaserver`。
7. 选择一个 PNG。
8. 点击 `Generate Beta`。
9. 插件上传到 `/api/codia-preview`。
10. 后端完成后，插件拉取 `/api/codia-preview/{taskId}/dsl`，并以 `/api/codia-preview/{taskId}` 作为 asset base URL。
11. 当前页面应生成尺寸等于 PNG 的 root Frame。
12. Layers 中应出现 Codia Runtime Root、Groups、Text、Image、Background/Button 等节点；ImageView crop assets 不应出现 `CODIA_RUNTIME_IMAGE_SOURCE_NOT_FOUND`。
13. UI 应显示生成节点数和 warning 数。

`Sample` 按钮保留为开发备用入口，不调用后端。

当前插件不再提供 `Generate Compare`，也不再拉取 `/api/tasks/{taskId}/m29-direct-dsl`。

## API Smoke

Go Codia Beta 上传 PNG：

```bash
curl -F "file=@/absolute/path/to/input.png" \
  http://localhost:8000/api/codia-preview
```

轮询 Go Codia Beta 任务：

```bash
curl http://localhost:8000/api/codia-preview/{taskId}
```

获取 Codia Runtime DSL v0.2：

```bash
curl http://localhost:8000/api/codia-preview/{taskId}/dsl
```

保留 Python preview 上传 PNG：

```bash
curl -F "file=@/absolute/path/to/input.png" \
  http://localhost:8000/api/upload-preview
```

轮询任务：

```bash
curl http://localhost:8000/api/tasks/{taskId}
```

获取正式 DSL：

```bash
curl http://localhost:8000/api/tasks/{taskId}/dsl
```

获取 materialization report：

```bash
curl http://localhost:8000/api/tasks/{taskId}/materialization
```

当前不支持：

```bash
curl http://localhost:8000/api/tasks/{taskId}/m29-direct-dsl
curl http://localhost:8000/api/upload
```

These should return 404 or a normal API not-found response.

## Localhost Network Access

`localhost` 只配置在 `manifest.json` 的 `networkAccess.devAllowedDomains`。Figma 不允许把 localhost 放进正式 `allowedDomains`，除非同时提供审核用 `reasoning` 字段。开发期如果要阻断正式网络域名，`allowedDomains` 必须写成 `["none"]`，不能写空数组。

## Configuration

环境变量记录在 [../reference/env-vars.md](../reference/env-vars.md)。
