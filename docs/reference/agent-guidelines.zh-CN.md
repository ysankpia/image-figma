# Agent Guidelines 中文参考快照

本文件只是根目录 `AGENTS.md` 的中文参考快照。根目录 `AGENTS.md` 是 agent 执行时的权威版本；如果两者冲突，以根目录 `AGENTS.md` 为准。

## 当前事实源

先读：

```text
AGENTS.md
PROGRESS.md
docs/index.md
docs/product/direction-contract.md
docs/roadmap.md
README.md
docs/engineering/current-code-map.md
docs/engineering/legacy-code-inventory.md
docs/engineering/validation.md
```

不要依赖聊天记录、旧计划、ADR、legacy 草稿或历史 Codia/Pencil/Draft 文档来覆盖当前代码和当前 docs。

## 当前产品主线

当前分支的产品主线是 Slice Studio：

```text
1..N UI screenshots/design images
-> repository root
-> project workspace
-> original source images in local storage
-> saved SliceRecord boxes in SQLite
-> assets.zip
-> project.zip / design.pen
```

核心目标：

```text
screenshots/design images -> user-confirmed Pencil/Figma handoff package + frontend asset zip
```

## 当前运行面

默认开发命令：

```bash
bun run dev
```

默认端口：

```text
Next web:  http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
```

基线检查：

```bash
pnpm run check
pnpm run build
git diff --check
git status --short --branch
```

## 关键合同

- Saved Slice Studio pages and slices 是当前编辑和导出真相源。
- `manual_ui_slices.v1` 是 export manifest schema。
- AI boxes 是临时建议，只有保存为普通 SliceRecord 后才进入导出。
- OCR 只提供文字内容。
- TypeScript M29 physical evidence 只辅助 OCR text bbox。
- Go `m29extract` 是显式 fallback/reference，不是默认部署依赖。

## 旧路径状态

以下都是历史/参考/延后路线，不能作为当前默认产品路径：

```text
archive/legacy-code/services/pencil-python-backend
archive/legacy-code/services/pencil-asset-backend
archive/legacy-code/services/pencil-handoff-studio
Go /api/draft-preview
Python /api/upload-preview
/api/codia-preview
Generate Beta
codia assembly/control/tree/emitter
M29 Direct compare
legacy M30
M31-M39/M39.1
ONNX proposer
archive/legacy-code/figma-plugin runtime
archive/legacy-code/packages/image-to-figma-renderer default route
```

要删除、移动、恢复旧目录，先读 `docs/engineering/legacy-code-inventory.md`，再写 active plan。
