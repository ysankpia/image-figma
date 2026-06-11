# 177 Slice Studio Pencil Editable Text Layer V1

## Summary

在 `apps/slice-studio` 的 `project.zip/design.pen` 导出里补第一版可编辑文字层。范围固定：只从原图 OCR 出未被用户确认 slice 覆盖的普通文字，生成 Pencil `text` 节点；不重建按钮背景、不做 Auto Layout、不做 AI 分块、不接旧 Python runtime。

## Decisions

- manual slices 仍是图片资产真相源。
- OCR 只补 remainder 里的文字，不覆盖 slice 区域。
- 按钮、卡片、标签背景继续保留在 `remainder.png` 或 slice PNG 中；只让文字可编辑。
- OCR provider 第一版使用本地 `tesseract` CLI，默认语言 `chi_sim+eng`。
- 如果本机没有 tesseract 或 OCR 失败，`project.zip` 继续导出，只记录 `textLayerCount=0` 和 skip reason。
- 字体第一版使用跨平台 fallback：`PingFang SC, Microsoft YaHei, sans-serif`。

## Implementation

- 新增 `server/text-ocr.ts`：调用 tesseract TSV，解析 word/line，按行合并文本。
- 新增 `server/text-reconstruction.ts`：过滤 overlap manual slices 的 OCR 行，估算字号/颜色，生成 Pencil text layer 数据。
- 更新 `pencil-exporter.ts`：支持 `text` node，把 OCR text nodes 放在 remainder 和 slice layers 上方。
- 更新 `pencil-package.ts` manifest：记录每页 `textLayers`、`textLayerCount`、OCR provider/status。
- 更新 README：说明 Pencil export 现在包含 OCR text layer，但按钮背景不结构化。
- 更新 tests/smoke：覆盖 overlap filter、manifest text layer、`.pen` 文字节点存在性。

## Progress

- 2026-06-11: 已实现本地 tesseract OCR TSV 解析、manual slice overlap 过滤、Pencil text node 导出、manifest OCR/textLayers 记录、README 更新和单元测试覆盖。当前 v1 不做 text knockout；底层 remainder 里的原始文字像素仍保留。

## Current Limitation

当前 `SliceKind` 只有 `image`，没有按钮/商品图/图标等语义类型，所以 OCR text layer 会保守跳过被任何 confirmed slice 覆盖的文字。这样能避免商品图或图标内部文字乱变成 editable text，但如果用户把整个按钮切成一个 raster slice，按钮内文字也会被跳过。下一阶段若要“按钮整体可保留 raster 背景但文字可编辑”，需要先给 slice 增加稳定的 kind 或允许用户标记 `text overlay allowed`，不能靠固定坐标或文字内容猜。

## Validation

```bash
cd apps/slice-studio
bun run check
bun run build
bun run smoke

cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
git diff --check
git status --short --branch
```
