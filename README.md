# Image-to-Figma Design

Image-to-Figma Design 当前分支的可交付目标已经收敛为：把单张或多张截图转换成可人工确认的 Pencil/Figma 交付包，而不是继续追求全自动一次性切图全对。

当前分支的产品主线是 **Pencil Assisted Slice Workspace**。默认后端是 Python `services/pencil-python-backend`，默认浏览器入口是 `/api/pencil/slice-projects/workspace`。旧 Codia 生成路径、Go Draft `/api/draft-preview`、Python upload-preview、YOLO/PSD-like 自动 ownership 计划只保留作历史参考、候选证据或显式调试目标，不能作为当前新功能落点。

旧代码不是默认删除对象。`backend/`、`services/backend-python/`、`services/pencil-go/`、Draft/Renderer/Plugin 包和历史 Codia-like/M29 文档都可能是未来研究资产。判断某个目录能不能删、能不能改、能不能恢复为产品路径，先读 [docs/engineering/legacy-code-inventory.md](docs/engineering/legacy-code-inventory.md)。

## 当前主链

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> 用户点选 / 手动画框 / 调整 / 删除 / 命名
-> manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

核心合同：

- `candidates.v1.json`：自动候选，只是建议，不是最终裁判。
- `review_state.v1.json`：工作台状态，例如 rejected candidates、筛选、最后处理页。
- `manual_slices.v1.json`：最终交付真相源。
- `project.zip`：给 Pencil 打开，再导入 Figma。
- `selected-assets.zip`：给前端开发使用的确认后切图资源。

当前不做：

```text
官方 Codia JSON byte-for-byte 复刻
全自动 semantic UI control tree 作为产品主合同
Auto Layout
Figma Component/Instance
响应式布局编译
YOLO / VLM / M29 / PSD-like 作为最终 visible ownership 裁判
services/pencil-go 复活为产品路径
账号/支付/额度
```

## 运行

Pencil assisted slice 后端：

```bash
cd services/pencil-python-backend
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike \
OCR_PROVIDER=none \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

打开工作台：

```text
http://127.0.0.1:8100/api/pencil/slice-projects/workspace
```

如果需要真实 OCR，在本地未提交 env 中配置：

```bash
OCR_PROVIDER=baidu_ppocrv5
BAIDU_PADDLE_OCR_TOKEN=...
```

保留的 Go Draft 路径只在明确恢复或调试历史 Draft runtime 时使用：

```bash
cd services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver
```

保留的 Python/FastAPI preview 路径只在明确调试历史 upload-preview 时使用：

```bash
cd backend
uv sync
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 验证

当前 Pencil backend：

```bash
cd services/pencil-python-backend
make check
make slice-acceptance \
  IMAGE=/absolute/path/to/image-or-dir \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

如果显式改 Go Draft / 插件 / Renderer，再运行对应检查：

```bash
cd services/backend-go
go test ./...

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
- [services/pencil-python-backend/README.md](services/pencil-python-backend/README.md)
- [docs/reference/pencil-python-backend-api.md](docs/reference/pencil-python-backend-api.md)
- [docs/runbooks/pencil-python-backend-handoff.md](docs/runbooks/pencil-python-backend-handoff.md)
- [docs/runbooks/pencil-python-backend-deploy.md](docs/runbooks/pencil-python-backend-deploy.md)
- [docs/engineering/current-code-map.md](docs/engineering/current-code-map.md)
- [docs/engineering/legacy-code-inventory.md](docs/engineering/legacy-code-inventory.md)
- [docs/engineering/validation.md](docs/engineering/validation.md)
- [docs/plans/completed/141-pencil-assisted-slice-review-and-export.md](docs/plans/completed/141-pencil-assisted-slice-review-and-export.md)
- [docs/plans/completed/144-assisted-slice-project-workspace.md](docs/plans/completed/144-assisted-slice-project-workspace.md)
- [docs/plans/completed/145-assisted-slice-workspace-acceptance-hardening.md](docs/plans/completed/145-assisted-slice-workspace-acceptance-hardening.md)
