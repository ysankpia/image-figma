# Bug: Text replacement rejects OCR labels on low-complexity UI cards

- 状态：open
- 创建日期：2026-05-17
- 影响范围：M12 text replacement coverage

## Summary

百度 PP-OCRv5 已经识别出首页样例中的多个 UI 文本，但 M12 replacement safety gate 将部分文本判为 `complex_background`，导致它们没有生成可编辑 `visible_text_replacement`。

这不是图形、图标或组件组重建问题。M12 本来就不重建圆形头像、图标组、卡片组件或 Auto Layout；本问题只记录“已 OCR 识别的文字没有被安全替换成可编辑 Text”。

## Reproduction

样例任务：

```text
task_034376da3344
```

样例文件：

```text
/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/01_学生端-首页选床活动.png
```

运行配置：

```text
OCR_PROVIDER=baidu_ppocrv5
TEXT_REPLACEMENT_MODE=apply
TEXT_REPLACEMENT_ENABLE_COLORED_BG=true
TEXT_REPLACEMENT_MAX_BLOCKS=100
```

复现方式：

1. 启动后端并加载 Figma 插件。
2. 上传首页样例 PNG。
3. 查看 Figma 图层和 `/api/tasks/{taskId}/text-replacements`。
4. 下列 OCR block 已识别，但没有被替换成可编辑 Text：

```text
ocr_text_004 男生
ocr_text_005 2026级新生
ocr_text_026 可视化选床，像高铁选座一样直观
ocr_text_028 预览选床界面
ocr_text_029 可选
ocr_text_031 不可选
ocr_text_032 温馨提示
ocr_text_034 选床确认后将无法自行修改，如需调整请联系辅导员。
```

当前 replacement 决策：

```text
accepted: 26
rejected: 12
rejected complex_background: 10
```

## Root Cause

OCR 阶段正常。`backend/storage/ocr/task_034376da3344.json` 中能看到对应文本、bbox 和高置信度。

M12 的背景/前景采样仍偏保守。它只接受浅色纯背景或低复杂度彩色/深色背景上的高对比文字。badge、插画附近卡片、预览区域图例、提示卡片这类区域边缘含渐变、阴影、图标、插画或底色变化，当前采样会判定为 `complex_background`，从而拒绝可见替换。

## Fix

未修复。建议放入后续阶段处理：

- M13：增加 text replacement 质量控制和区域级回退/开关，先让这类 rejected case 可观测、可批量比较。
- M14+：改进 text replacement 采样策略，例如基于 OCR bbox 周边局部边缘采样、pill/badge 背景估计、图例文本与色块分离、提示卡片内文字的局部背景估计。

不要在 M12 直接放宽 `complex_background`，否则会增加双层文字、遮盖图标和误盖插画的风险。

## Regression Guard

后续修复时必须用该首页样例回归，至少检查：

- 上述 OCR block 仍能被 PP-OCRv5 识别。
- `男生`、`2026级新生`、`可视化选床，像高铁选座一样直观`、`温馨提示` 和提示正文至少部分进入 accepted replacement。
- `可选`、`已选`、`不可选` 三个图例文字的处理一致，不能只替换其中一个。
- fallback region、hidden OCR candidate 和 original reference 仍保留。

## Validation Evidence

2026-05-17 本地检查：

```bash
jq -r '.blocks[] | [.id,.text, (.bbox|join(",")), (.confidence|tostring)] | @tsv' \
  backend/storage/ocr/task_034376da3344.json

jq -r '.decisions[] | [.ocrBlockId,.decision,.reason, (.bbox|join(","))] | @tsv' \
  backend/storage/text_replacements/task_034376da3344.json
```

结果显示 OCR completed，`block_count=38`；text replacement completed，`accepted_count=26`，`rejected_count=12`，其中 `complex_background=10`。

## Prevention Notes

后续每次扩大 replacement 覆盖率，都应先对比 OCR blocks 与 replacement decisions。不能把“没识别到文字”和“识别到了但被 replacement 拒绝”混为一类问题。
