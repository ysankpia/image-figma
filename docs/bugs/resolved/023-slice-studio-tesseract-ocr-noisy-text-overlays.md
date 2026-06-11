# Bug: Slice Studio OCR creates noisy oversized or duplicated Pencil TextLayers

- 状态：resolved
- 创建日期：2026-06-11
- 影响范围：`apps/slice-studio` 的 `project.zip/design.pen` OCR TextLayer 导出

## Summary

Slice Studio Pencil export 第一版默认调用本地 Tesseract。实际茶饮样本中，Tesseract 把状态栏、搜索栏、商品区域和底部导航合并成超宽行，并把图片/图标噪声识别为 `ee`、`@ a a @` 等文本。生成的 `.pen` 中出现大量 oversized editable TextLayer，视觉上污染导出结果。

切到百度 PP-OCRv5 后，识别内容明显改善，但导出的 `.pen` 仍把 editable TextLayer 叠在包含原始文字像素的 `remainder.png` 上。同时 `fontWeight` 以 number 写入被 Pencil 导入为 `normal`，CSS fallback 字体串被当成单一字体名，字号又按 OCR bbox 高度粗估。用户手动导出的 `/Users/luhui/Downloads/P1.png` 因此出现重影、字号偏大和字体不贴。

## Reproduction

1. 从 Slice Studio 导出 `/Users/luhui/Downloads/project_mq8plzjo_257c14b7-project (1)/design.pen`。
2. 用 Pencil 打开文件。
3. 检查 `page_0001__frame` 下的 text nodes。

观察到 23 个 TextLayer，其中多项 bbox 接近整屏宽，例如 `868x35`、`882x77`、`901x95`、`910x94`。内容包含错误合并和噪声文本，例如 `9:41 oll > Gs) 100%`、`Q搜索茶饮/小料/套餐照会员码`、`加wx ac @`、`@ a a @`。

## Root Cause

Tesseract TSV `--psm 6` 对移动 UI 截图的复杂图文混排不稳定，会把多个独立 UI 文本和图标噪声合并成单行。Slice Studio v1 又缺少 provider 选择和 TextLayer 质量门，导致所有 OCR 行都进入 Pencil。

仓库已有百度 AI Studio PP-OCRv5 异步 OCR provider 和环境变量，但 Slice Studio 没有加载仓库根 `.env.local`，也没有接入该 provider。

第二层根因在 Pencil export 合成合同：

- `remainder.png` 只挖掉 manual slice bbox，没有擦掉被 OCR TextLayer 接管的文字像素。
- `fontWeight` 使用 number，Pencil schema 需要 string，导入后退化成 `normal`。
- `fontFamily` 使用 CSS fallback 字符串，Pencil 把整串当成一个字体名，实际字体退回默认。
- 字号只按 bbox height 估算，没有受文本宽度和字符数量约束，短文本会被放大。

## Fix

- Slice Studio 默认 OCR provider 改为 `baidu_ppocrv5`。
- 服务启动时加载仓库根目录或 app 目录 `.env.local` 中的 OCR 环境变量。
- 没有 `BAIDU_PADDLE_OCR_TOKEN` 时跳过 OCR，而不是默认回退到 Tesseract。
- 保留 Tesseract 仅作为显式诊断选项：`SLICE_STUDIO_OCR_PROVIDER=tesseract`。
- Text reconstruction 增加通用质量门，拒绝低置信度和超宽 OCR 行。
- 对已接受的 OCR TextLayer bbox，在 `remainder.png` 上做局部背景填充式 text knockout，消除原图文字和 editable text 的重复像素所有权。
- TextLayer 字号改为宽高双约束估算，`fontWeight` 输出为 `"400"` / `"500"` / `"600"` 字符串，`fontFamily` 输出为单一 `PingFang SC`。
- 文本颜色改为用周边背景估计，再取 bbox 内相对背景对比最高的像素簇，避免白底、绿底和红字都被简单黑度规则带偏。
- 竖排或印章类短 CJK 文本不生成普通横排 editable TextLayer，继续留在 raster/remainder。

## Regression Guard

- 单元测试覆盖百度 PP-OCRv5 JSONL 解析、manifest provider 字段、manual slice overlap 过滤、超宽 OCR 行过滤。
- 单元测试覆盖 remainder text knockout 不破坏 slice alpha 行为、Pencil text style 字段类型、短文本字号不再按 bbox 高度膨胀、竖排短 CJK 不强行生成横排 TextLayer。
- smoke 检查 Pencil manifest 中 OCR/text layer 字段存在，并检查 TextLayer 字体字段类型。

## Validation Evidence

- `cd apps/slice-studio && bun run typecheck`
- `cd apps/slice-studio && bun run test`
- `cd apps/slice-studio && bun run build`
- `cd apps/slice-studio && bun run smoke`
- 真实项目 `project_mq8plzjo_257c14b7` 重新导出成功：`assetCount=29`，`textLayerCount=48`，`ocr.provider=baidu_ppocrv5`。
- 新 manifest 中 TextLayer `fontFamily=PingFang SC`，`fontWeight` 为 `"400"` / `"500"` / `"600"`，不再导入成 `normal`。
- Pencil MCP 打开 `/tmp/slice-studio-p1-fixed/design.pen` 并截图确认重影基本消除；局部 remainder crop 检查确认商品标题、价格和结算按钮文字区域已被背景填充，不是透明洞。
