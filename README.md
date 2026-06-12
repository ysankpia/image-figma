# Slice Studio

Slice Studio 是当前仓库的主线产品：本地项目制 UI 切图工具。它把 1..N 张截图或设计稿变成用户确认后的 `assets.zip` 和 Pencil/Figma handoff `project.zip`。

当前默认产品入口：

```text
repository root
```

## 当前主链

```text
1..N UI screenshots/design images
-> Slice Studio project workspace
-> source images stored under storage/
-> user-drawn or AI-assisted rect slices
-> optional rect/subject/card cut modes
-> SQLite-backed project state
-> assets.zip for frontend assets
-> project.zip / design.pen for Pencil/Figma handoff
```

核心合同：

- `SliceRecord` / SQLite project state：当前编辑和导出真相源。
- `manual_ui_slices.v1` manifest：导出包真相源。
- AI boxes：临时画框建议，进入前端后就是普通 slice，不单独持久化。
- OCR：只提供 editable text content。
- TypeScript M29 physical evidence：只辅助 OCR text bbox 定位，不创建 visible layers。
- Go `m29extract`：只作为显式 fallback/reference，不是默认部署依赖。

## 运行 Slice Studio

从仓库根目录启动当前产品：

```bash
pnpm install
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

## 配置

Slice Studio 默认读取根目录 `.env.local`，不要把密钥提交到仓库。

常用变量见：

- [.env.example](.env.example)
- [docs/reference/env-vars.md](docs/reference/env-vars.md)

关键变量：

```text
NEXT_PUBLIC_SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5
SLICE_STUDIO_TEXT_BBOX_SOURCE=m29_ocr_hybrid
SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=ts_m29_physical_evidence
SLICE_STUDIO_AI_SLICE_PROVIDER=openai_responses
SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY=4
SLICE_STUDIO_AI_SLICE_TILE_COUNT=6
SLICE_STUDIO_AI_SLICE_OVERVIEW_REVIEW=true
```

## 验证

Slice Studio 基线检查：

```bash
pnpm run check
pnpm run build
```

仓库级检查：

```bash
git diff --check
git status --short --branch
```

当改动导出、OCR、M29 text bbox、AI slicing、Pencil package 时，还需要真实样本验证：上传多页图片，保存 slices，导出 `assets.zip` 和 `project.zip`，检查 `manifest.json` 和 `.pen` 可打开。

## 旧代码状态

旧代码不是默认删除对象。这个仓库保留了多条历史路线：Pencil Python Backend、Pencil Asset Backend、Pencil Handoff Studio、Go M29/Draft、Python upload-preview、Renderer、Figma plugin、PSD-like、Codia eval 等。它们已经物理归档到 [archive/legacy-code](archive/legacy-code)，有研究价值，但不能覆盖当前 Slice Studio 主线。

判断旧目录能不能删、改、恢复为产品路径，先读：

- [docs/engineering/legacy-code-inventory.md](docs/engineering/legacy-code-inventory.md)
- [docs/engineering/current-code-map.md](docs/engineering/current-code-map.md)

默认规则：

```text
new product work -> root app/components/server/shared/scripts/tests
old services -> archive/legacy-code reference/fallback/legacy research unless a new active plan says otherwise
manual/saved Slice Studio slices -> final export truth
```

## 文档入口

从这里开始：

- [AGENTS.md](AGENTS.md)
- [PROGRESS.md](PROGRESS.md)
- [docs/index.md](docs/index.md)
- [docs/product/direction-contract.md](docs/product/direction-contract.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/engineering/current-code-map.md](docs/engineering/current-code-map.md)
- [docs/engineering/legacy-code-inventory.md](docs/engineering/legacy-code-inventory.md)
- [docs/engineering/validation.md](docs/engineering/validation.md)
