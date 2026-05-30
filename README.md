# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库的 Codia Beta 后端已经切到 Go：插件 `Generate Beta` 走 `services/backend-go/cmd/codiaserver`、DSL v0.2 Codia Runtime 和本地 crop assets。历史 Python/FastAPI `/api/upload-preview` 仍保留为 DSL v0.1 M29 preview 路径，但不是 Codia Beta 输出质量调试的起点。

## 当前 Codia Beta 主链

```text
单张 PNG
-> Figma Plugin Generate Beta
-> POST /api/codia-preview
-> Go codiaserver
-> OCR
-> Go M29 physical evidence
-> optional OpenAI-compatible UI detector
-> Codia assembly/control/tree/emitter
-> DSL v0.2 Codia Runtime
-> GET /api/codia-preview/{taskId}/dsl
-> GET /api/codia-preview/{taskId}/assets/{assetId}.png
-> renderCodiaRuntimeDesign
-> Figma 可编辑设计稿
```

`/api/codia-preview` 是当前 Codia Beta 上传入口。`/api/codia-preview/{taskId}/dsl` 是 Codia Beta DSL v0.2 输出端点。`/api/upload-preview` 和 `/api/tasks/{taskId}/dsl` 是保留的 Python DSL v0.1 preview 路径。

## 当前能力

- 单张 PNG 上传。
- fake OCR 或百度 PP-OCRv5 异步 OCR。
- Go M29 physical evidence。
- OpenAI-compatible UI detector 可选接入，provider/baseUrl/model/apiKey 可配置。
- Codia assembly/control/tree/emitter，输出 role-aware tree。
- DSL v0.2 Codia Runtime artifact。
- ImageView crop assets 由 Go server 提供给 renderer。
- Renderer 通过 `renderCodiaRuntimeDesign` 写入 Figma。

当前不做：

```text
代码生成
Auto Layout
Figma Component/Instance
响应式布局编译
批量上传
账号/支付/额度
质量看板
```

## 运行

Go Codia Beta 后端：

```bash
cd services/backend-go
CODIA_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/codiaserver
```

如果需要真实 OCR 或在线 detector，在本地未提交 env 中配置：

```bash
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
CODIA_SERVER_DETECTOR_ENABLED=true
CODIA_UI_DETECTOR_BASE_URL=...
CODIA_UI_DETECTOR_MODEL=...
CODIA_UI_DETECTOR_API_KEY=...
```

保留的 Python/FastAPI preview 路径：

```bash
cd backend
uv sync
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端/插件：

```bash
pnpm install
pnpm --filter @image-figma/figma-plugin run build
```

## 验证

完整验证：

```bash
cd services/backend-go && go test ./internal/codia/... ./cmd/codiacompile ./cmd/codiaserver
pnpm -r run test
pnpm -r run typecheck
```

仓库级检查：

```bash
git diff --check
git status --short --branch
```

## 文档入口

从 [docs/index.md](docs/index.md) 开始阅读。关键当前事实文档：

- [AGENTS.md](AGENTS.md)
- [docs/architecture/backend.md](docs/architecture/backend.md)
- [docs/architecture/api-contracts.md](docs/architecture/api-contracts.md)
- [docs/engineering/current-mainline-code-map.md](docs/engineering/current-mainline-code-map.md)
- [docs/engineering/m29-contract-regression-matrix.md](docs/engineering/m29-contract-regression-matrix.md)
