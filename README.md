# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑草稿。

当前分支的产品主线是 **Editable Draft Layer Pipeline**。默认后端是 Go `services/backend-go/cmd/draftserver`，默认上传入口是 `/api/draft-preview`。旧 Codia 生成路径和 Python upload-preview 只保留作历史参考或显式调试目标，不能作为新功能落点。

## 当前主链

```text
单张 PNG
-> Figma Plugin
-> POST /api/draft-preview
-> Go Draft server
-> OCR
-> M29 physical evidence
-> optional OpenAI-compatible vision detector/review
-> Editable Layer Graph
-> Draft Runtime DSL
-> GET /api/draft-preview/{taskId}/dsl
-> GET /api/draft-preview/{taskId}/assets/{assetId}.png
-> Renderer
-> Figma editable draft
```

核心合同：

- `editable_layer_graph.v1.json`：后端主合同，表达可编辑 layer ownership、z-order、source refs 和决策原因。
- `draft_runtime.dsl.v1.json`：Renderer 输入合同。
- `asset_manifest.json`：本地 raster asset 可解析性合同。

当前不做：

```text
官方 Codia JSON byte-for-byte 复刻
语义 UI control tree 作为产品主合同
Auto Layout
Figma Component/Instance
响应式布局编译
批量上传
账号/支付/额度
```

## 运行

Go Draft 后端：

```bash
cd services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver
```

如果需要真实 OCR 或在线视觉模型，在本地未提交 env 中配置：

```bash
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
DRAFT_SERVER_VISION_ENABLED=true
VISION_BASE_URL=...
VISION_MODEL=...
VISION_API_KEY=...
VISION_WIRE_API=responses
VISION_DETECTOR_CONCURRENCY=3
```

前端/插件：

```bash
pnpm install
pnpm --filter @image-figma/figma-plugin run build
```

保留的 Python/FastAPI preview 路径只在明确调试历史 upload-preview 时使用：

```bash
cd backend
uv sync
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 验证

后端：

```bash
cd services/backend-go
go test ./...
```

TypeScript packages：

```bash
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

仓库级检查：

```bash
git diff --check
git status --short --branch
```

## 文档入口

从 [docs/index.md](docs/index.md) 开始阅读。关键当前事实文档：

- [AGENTS.md](AGENTS.md)
- [docs/architecture/overview.md](docs/architecture/overview.md)
- [docs/architecture/runtime.md](docs/architecture/runtime.md)
- [docs/architecture/draft-layer-graph.md](docs/architecture/draft-layer-graph.md)
- [docs/architecture/vision-provider.md](docs/architecture/vision-provider.md)
- [docs/engineering/current-code-map.md](docs/engineering/current-code-map.md)
- [docs/engineering/validation.md](docs/engineering/validation.md)
- [docs/plans/active/093-editable-draft-layer-pipeline-rebuild.md](docs/plans/active/093-editable-draft-layer-pipeline-rebuild.md)
