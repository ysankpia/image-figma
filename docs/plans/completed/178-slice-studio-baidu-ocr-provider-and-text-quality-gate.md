# 178 Slice Studio Baidu OCR Provider And Text Quality Gate

## Status

Completed.

## Summary

修复 Slice Studio Pencil 导出默认使用 Tesseract 导致的噪声 TextLayer，并补齐百度 OCR TextLayer 输出质量。导出 OCR provider 改为优先使用已有百度 AI Studio PP-OCRv5 异步 API；没有 `BAIDU_PADDLE_OCR_TOKEN` 时跳过 OCR，不再默认用 Tesseract 污染 `.pen`。同时增加通用 TextLayer 质量门，拒绝超宽、低置信度、疑似合并多区域的 OCR 行，并修复可编辑文字叠在原图文字上造成的重影、字号过大和字重被 Pencil 忽略的问题。

## Scope

- 修改 `apps/slice-studio` OCR provider 和 env 加载。
- 复用现有百度 PP-OCRv5 协议：submit job -> poll -> download JSONL -> parse `rec_texts/rec_scores/rec_boxes/rec_polys`。
- 保留 Tesseract 作为显式诊断 provider：`SLICE_STUDIO_OCR_PROVIDER=tesseract`。
- 不引入 `paddleocr`、`paddlepaddle`、`rapidocr` 或其他本地重依赖。
- 对已接受的 OCR TextLayer 区域在 `remainder.png` 上做局部背景填充式 text knockout，避免原始文字和可编辑文字重复拥有同一批像素。
- 修正 Pencil text schema 输出：`fontWeight` 使用字符串，字号使用宽高双约束估算，颜色从 bbox 内相对背景对比最高的像素簇估算。
- 不做按钮背景结构化，不做全自动 UI 控件树。

## Validation

```bash
cd apps/slice-studio
bun run typecheck
bun run test
bun run build
bun run smoke

cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
git diff --check
```

## Completion Evidence

- `cd apps/slice-studio && bun run typecheck`
- `cd apps/slice-studio && bun run test`
- `cd apps/slice-studio && bun run build`
- `cd apps/slice-studio && bun run smoke`
- Real sample export: `project_mq8plzjo_257c14b7` exported `project.zip` with `assetCount=29`, `ocr.provider=baidu_ppocrv5`, `textLayerCount=48`.
- Pencil MCP opened `/tmp/slice-studio-p1-fixed/design.pen`; frame screenshot showed the visible OCR double-rendering removed compared with `/Users/luhui/Downloads/P1.png`.
- Local crop checks confirmed accepted OCR text regions are background-filled in `remainder.png`, while confirmed slice regions still use alpha knockout.
