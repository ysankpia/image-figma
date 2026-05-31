# 本地设置

当前本地默认运行面是 Go Draft backend：`services/backend-go/cmd/draftserver`。插件通过 `/api/draft-preview` 上传 PNG，并拉取 Draft Runtime DSL 和本地 crop assets。

历史 Python/FastAPI `/api/upload-preview` 只在任务明确要求调试旧 preview 路径时启动。旧 Codia Beta、M29 Direct compare、legacy M30、M31-M39、ONNX proposer 等实验保留在历史文档或 git history 中，不是当前默认运行路径。

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

## Install

安装 workspace 依赖：

```bash
pnpm install
```

安装保留 Python preview 依赖：

```bash
cd backend
uv sync
```

## Run Go Draft Backend

插件 Draft 调试默认启动 Go 后端：

```bash
cd services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver
```

真实 OCR：

```bash
cd services/backend-go
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
DRAFT_SERVER_ADDR=127.0.0.1:8000 \
go run ./cmd/draftserver
```

在线 vision detector/review：

```bash
cd services/backend-go
DRAFT_SERVER_VISION_ENABLED=true \
VISION_BASE_URL=https://example-provider.test \
VISION_MODEL=provider-model-id \
VISION_API_KEY=... \
VISION_WIRE_API=responses \
VISION_DETECTOR_CONCURRENCY=3 \
DRAFT_SERVER_ADDR=127.0.0.1:8000 \
go run ./cmd/draftserver
```

Go task artifacts 默认写到：

```text
services/backend-go/storage/draft_server/draft_previews/{taskId}/
```

Completed task 至少应包含：

```text
source.png
m29/
vision/
draft/editable_layer_graph.v1.json
draft/draft_runtime.dsl.v1.json
draft/draft_validation_report.md
assets/asset_manifest.json
assets/*.png
logs/task_report.md
```

## Run Draft CLIs

单图编译：

```bash
cd services/backend-go
go run ./cmd/draftcompile -input /absolute/path/to/input.png -out /tmp/draft-out
```

只跑视觉 detector：

```bash
cd services/backend-go
VISION_BASE_URL=... \
VISION_MODEL=... \
VISION_API_KEY=... \
go run ./cmd/draftdetect -input /absolute/path/to/input.png -out /tmp/detect-out
```

Codia reference/eval，只做对比，不做生成：

```bash
cd services/backend-go
go run ./cmd/drafteval analyze -input /path/to/sample.canvas.json -out /tmp/eval
go run ./cmd/drafteval diff -generated /tmp/gen/codia_ir.v1.json -golden /tmp/gold/codia_ir.v1.json -out /tmp/diff
go run ./cmd/drafteval audit -diff /tmp/diff/codia_structure_diff.v1.json -out /tmp/audit
```

## Run Retained Python Preview Backend

只有调试历史 `/api/upload-preview` preview path 时启动 Python 后端：

```bash
cd backend
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

开发诊断 profile：

```bash
cd backend
UPLOAD_PREVIEW_PROFILE=development uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## OCR

默认 OCR provider：

```bash
OCR_PROVIDER=fake
```

百度 PP-OCRv5 异步 OCR：

```bash
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
BAIDU_PADDLE_OCR_MODEL=PP-OCRv5
```

百度 token 是 bearer token，只能放在本地环境变量或未提交的 `.env.local` 中，不能写入仓库。

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

Go 后端：

```bash
cd services/backend-go
go test ./...
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

只检查插件：

```bash
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

保留 Python preview 测试：

```bash
cd backend
uv run pytest -q
```

## Figma Manual Smoke

1. 打开 Figma。
2. 进入插件开发模式。
3. 加载 `figma-plugin/manifest.json`。
4. 运行 `Image-to-Figma Design`。
5. 启动 Go 后端：`cd services/backend-go && DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver`。
6. 选择一个 PNG。
7. 点击插件里的 Draft 生成动作。
8. 插件上传到 `/api/draft-preview`。
9. 后端完成后，插件拉取 `/api/draft-preview/{taskId}/dsl`，并以 `/api/draft-preview/{taskId}` 作为 asset base URL。
10. 当前页面应生成尺寸等于 PNG 的 root Frame。
11. Layers 中应出现 Draft root、Group、Text、Raster、Shape 等节点；RasterLayer crop assets 不应出现 image load failed warning。
12. UI 应显示生成节点数和 warning 数。

`Sample` 按钮保留为开发备用入口，不调用后端。

## API Smoke

上传 PNG：

```bash
curl -F "file=@/absolute/path/to/input.png" \
  http://localhost:8000/api/draft-preview
```

轮询 Go Draft task：

```bash
curl http://localhost:8000/api/draft-preview/{taskId}
```

获取 Draft Runtime DSL：

```bash
curl http://localhost:8000/api/draft-preview/{taskId}/dsl
```

获取 RasterLayer asset：

```bash
curl -I http://localhost:8000/api/draft-preview/{taskId}/assets/{assetId}.png
```

保留 Python preview 上传 PNG：

```bash
curl -F "file=@/absolute/path/to/input.png" \
  http://localhost:8000/api/upload-preview
```

当前不支持旧 product routes；它们应返回 404 或普通 API not-found response。

## Localhost Network Access

`localhost` 只配置在 `manifest.json` 的 `networkAccess.devAllowedDomains`。Figma 不允许把 localhost 放进正式 `allowedDomains`，除非同时提供审核用 `reasoning` 字段。开发期如果要阻断正式网络域名，`allowedDomains` 必须写成 `["none"]`，不能写空数组。

## Configuration

环境变量记录在 [../reference/env-vars.md](../reference/env-vars.md)。
