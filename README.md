# Image-to-Figma Design

Image-to-Figma Design 的目标是把单张 PNG 截图或设计稿转换为 Figma 画布中的可编辑设计稿。

当前仓库已经把产品主链收口到 M29 plan-driven materialization。历史上 M30、M29 Direct compare、M31-M39 downstream、SAM2/perception/icon/slice 等实验仍保留在 ADR、completed plans 和 git history 中，但不再是当前运行时事实。

## 当前主链

```text
单张 PNG
-> Figma Plugin
-> POST /api/upload-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 plan-driven materializer
-> GET /api/tasks/{taskId}/dsl
-> Figma Renderer
-> Figma 可编辑设计稿
```

`/api/upload-preview` 是当前正式上传入口。`/api/tasks/{taskId}/dsl` 是唯一正式设计稿出口。

## 当前能力

- 单张 PNG 上传。
- fake OCR 或百度 PP-OCRv5 异步 OCR。
- raw M29 visual primitive graph。
- M29.2 pixel ownership。
- M29.3 bbox relation graph。
- M29.4 weak structural evidence report。
- M29.5 replay plan，控制 visible node 顺序、去重、node budget 和 cleanup 授权。
- M29 plan-driven DSL materialization，输出 text、shape、image、fallback/reference 结构。
- Renderer 将 DSL v0.1 写入 Figma。

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

后端：

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
cd backend && uv run pytest -q
cd ..
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
