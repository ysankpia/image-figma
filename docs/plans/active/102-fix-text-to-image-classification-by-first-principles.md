# 102 Fix Text-To-Image Classification By First Principles

- 状态：active
- 创建日期：2026-06-02
- 所属链路：`/Users/luhui/.gemini/antigravity/scratch/` Two-Stage Cascade Inference

## Summary

在之前的两阶段级联匹配脚本中，若 YOLO 分类器与 OmniParser 候选框重合度低（IoU <= 0.25），系统会默认将候选框归类为 `"Icon"`。这导致了许多包含文本的候选框被错误识别为图像或图标（如把“去缴费”等文本按钮识别为 `Icon`）。

根据第一性原理（First Principles of UI Parsing）：
1. **文本是确定的**：如果一个候选框内包含有 OCR 识别出的文字，它就绝对不可能是纯图形的 `Icon` 或 `Image`。它必须是文本图层（`TextLayer`）、文本按钮（`TextButton`）或文本输入框（`EditText`）等文本承载型控件。
2. **图形是独立的**：如果一个候选框内**没有**任何 OCR 文字，它就绝对不可能是 `Text` 或 `CheckedTextView`，而应该归类为图形/背景容器图层（如 `Icon`、`Image`、`Card` 等）。

本计划旨在通过级联 OCR 物理边界数据来约束和修正分类逻辑，消除“字被识别成图”的分类缺陷。

## Proposed Changes

我们将修改 `/Users/luhui/.gemini/antigravity/scratch/two_stage_inference.py`，引入 OCR 边界交叉检验：

1. **获取图片的 SHA256 标识**，并从 `/Users/luhui/Downloads/psd_like_ocr_cache_test/` 动态加载对应的 `.ocr_blocks.v1.json`。
2. **计算每个候选框与 OCR 文本块的相交比例**（Intersection Area / OCR Block Area）。若该比例大于阈值（如 0.4），则判定该候选框包含该文本块。
3. **根据是否包含文本进行分类决策树分流**：
   - **包含文本**：
     - 若 YOLO 匹配成功（IoU > 0.25）且分类为 `Text` / `TextButton` / `EditText` / `CheckedTextView`，保留分类。
     - 若 YOLO 匹配到容器类（如 `Card` / `Toolbar` / `Bottom_Navigation` / `Spinner`），保留分类。
     - 否则，强制分类为 `Text`，避免退化为 `Icon` 或 `Image`。
   - **不包含文本**：
     - 若 YOLO 匹配成功且非文本分类，保留分类。
     - 若 YOLO 匹配为文本类，修正为 `Card`（若面积大）或 `Icon`/`Image`（若面积小）。
     - 否则，默认分类为 `Icon`（小框）或 `Image`（大框）。

## Verification Plan

1. 运行修改后的 `two_stage_inference.py` 脚本处理测试集图片。
2. 将可视化结果输出图保存至 `/Users/luhui/.gemini/antigravity/brain/de418e3e-e109-443a-832b-f69bfcbf54f8/`。
3. 对比修改前后的检测框分类标注，重点确认原先被错误分类为 `Icon` 或 `Image` 的文本区域是否被修正为了 `Text` / `TextButton`。
4. 更新对比报告 `prediction_test_report.md` 展示最终融合效果。
