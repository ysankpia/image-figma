# 105 PSD-like Model Evidence Assist Eval

- 状态：completed
- 创建日期：2026-06-02
- 完成日期：2026-06-02
- 负责人：Codex

## Goal

验证昨天训练的 18 类 UI 检测模型是否能作为 PSD-like Python service 的证据源，反哺当前剩余问题：

```text
PSD-like physical layer proposals
+ YOLO 18-class model detections
+ OCR blocks
-> model_evidence.v1.json
-> model/V1 match report
-> issue-assist decision report
```

本阶段只做只读评估，不改变当前 Draft DSL、layer_stack、asset、preview 输出。

## Scope

包含：

- 新增 `services/psdlike-python/tools/model_evidence_eval.py`。
- 读取当前 PSD-like 输出目录中的 `layer_stack.v1.json`。
- 使用模型：
  - `/Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.onnx`
  - 或同目录 `best.pt`
- 输出：
  - `model_evidence.v1.json`
  - `model_overlay.png`
  - `model_match_report.md`
  - `model_assist_summary.json`
  - `model_assist_summary.md`
  - `source_draft_overlay_model_contact_sheet.png`

不包含：

- 不修改 PSD-like 主 pipeline。
- 不修改旧 V1 oracle。
- 不修改 Go 实验。
- 不把模型检测框直接变成最终 Shape/Raster/Text layer。
- 不从模型生成文字。
- 不让模型直接 suppress OCR。

## Evidence Contract

模型输出只作为证据：

```text
model detection
-> match existing physical layer by IoU/IoA
-> semanticTags / candidate boost / risk signal
```

禁止：

```text
YOLO bbox -> direct crop
YOLO Text -> TextLayer
YOLO TextButton -> ShapeLayer without pixel confirmation
YOLO Image -> suppress OCR alone
```

## Evaluation Questions

1. 模型是否覆盖当前 low-control recall case 中的 `TextButton/EditText/Spinner/Switch/Multi_Tab`？
2. 模型是否覆盖 high-MAE / raster-heavy case 中的 `Icon/Image/BackgroundImage/Map`？
3. 模型框和 PSD-like physical layer 的 IoU/IoA 是否足够支持语义标签？
4. 模型是否有明显误检，例如把普通文本或卡片误判成按钮？
5. 模型是否能作为二次局部搜索窗口，而不是直接决定最终 bbox？

## Validation

单张 smoke：

```bash
cd services/psdlike-python
uv run python tools/model_evidence_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --current-output /Users/luhui/Downloads/psdlike_python_service_eval_all \
  --model /Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.onnx \
  --out /Users/luhui/Downloads/psdlike_model_evidence_eval_smoke \
  --limit 1
```

全量：

```bash
cd services/psdlike-python
uv run python tools/model_evidence_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --current-output /Users/luhui/Downloads/psdlike_python_service_eval_all \
  --model /Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.onnx \
  --out /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --limit 0
```

## Acceptance

- 工具能跑完 86 张，不影响当前 PSD-like 输出。
- 每个 case 至少输出 `model_evidence.v1.json` 或错误 artifact。
- 汇总报告能回答：
  - semantic match rate
  - low-control coverage
  - media/icon coverage
  - dangerous OCR-overlap detections
  - recommended next stage。

## Notes

- 当前本机已有 `ultralytics` 和 `onnxruntime`，本阶段不把它们写入 `pyproject.toml`。
- 如果模型效果好，下一阶段再规划 `model_assisted_pipeline`，并只允许模型触发局部二次搜索和 semantic tags。

## Completion Evidence

全量评估已完成，产物位于：

```text
/Users/luhui/Downloads/psdlike_model_evidence_eval_all
```

结果：

```text
86/86 ok
total detections = 8866
control detections = 531
media detections = 3134
low-control cases with model controls = 10
media missing physical candidates = 530
OCR overlap risk = 297
```

决策：

```text
模型适合作为 semantic evidence provider。
模型不直接生成 ShapeLayer / RasterLayer / TextLayer。
模型只允许触发 semanticTags、diagnostics 和后续局部物理重搜。
```
