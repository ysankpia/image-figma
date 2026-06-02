# 106 PSD-like Model-Assisted Semantic Evidence Pipeline

- 状态：active
- 创建日期：2026-06-02
- 负责人：Codex

## Summary

105 阶段已经证明，昨天训练的 18 类 UI 检测模型适合作为 PSD-like Python service 的证据源：

```text
PSD-like physical evidence = pixel ownership / geometry authority
OCR = text authority
YOLO model evidence = semantic hint / local search trigger / audit signal
Draft DSL = final ownership output
```

本计划定义后续分阶段接入方式。核心原则是：模型只提供语义证据和局部搜索窗口，不直接生成最终图层，不覆盖 OCR，不直接裁 asset，不直接决定 ownership。

## Source Evidence

105 全量评估产物：

```text
/Users/luhui/Downloads/psdlike_model_evidence_eval_all/model_assist_summary.md
/Users/luhui/Downloads/psdlike_model_evidence_eval_all/model_assist_summary.json
/Users/luhui/Downloads/psdlike_model_evidence_eval_all/model_assist_decision_report.md
/Users/luhui/Downloads/psdlike_model_evidence_eval_all/source_draft_overlay_model_contact_sheet.png
```

模型：

```text
/Volumes/WorkDrive/Datasets/vins_rico_yolov8/VINS-RICO-UPLABS-ANDROID.v2i.yolov8/runs/detect/runs/detect/train/weights/best.onnx
```

全量评估结论：

```text
86/86 ok
total detections = 8866
control detections = 531
media detections = 3134
low-control cases with model controls = 10
media missing physical candidates = 530
OCR overlap risk = 297
```

类别信号：

```text
TextButton = 464
EditText = 60
Icon = 1321
Image = 1807
Text = 5117
Card = 57
```

## First-Principles Decision

模型接入不能解决“像素归谁”的根问题。模型解决的是：

```text
这个区域可能是什么语义角色？
```

PSD-like pipeline 解决的是：

```text
这个可见像素最终由 ShapeLayer、RasterLayer、TextLayer 中哪一个拥有？
```

两者必须分层：

```text
model detection
-> semantic evidence
-> match physical layer or trigger local physical re-search
-> deterministic ownership gate
-> final layer / suppression / diagnostics
```

错误路径：

```text
model bbox
-> direct ShapeLayer / RasterLayer / TextLayer
```

这个错误路径会把模型 bbox 偏差、误检、OCR 冲突直接写进最终 DSL，导致不可审计、不可回滚、不可稳定调参。

## Scope

包含：

- 在 `services/psdlike-python` 中接入可选 `model_evidence.v1.json`。
- 为图层增加可审计的 `semanticTags` 或等价 meta 字段。
- 对 `TextButton`、`EditText`、`Spinner`、`Switch`、`CheckedTextView`、`Multi_Tab`、`Bottom_Navigation` 只触发局部 control surface re-search。
- 对 `Icon`、`Image`、`BackgroundImage`、`Map` 只触发局部 media candidate re-search。
- 对 `Text` / control detection 与 raster 的重叠写入 OCR/raster risk diagnostics。
- 保留 raw model evidence、matched semantic evidence、ownership decision evidence 三层证据。

不包含：

- 不修改旧 V1 oracle：
  - `services/backend-python/tools/psd_like_layer_decomposition_experiment.py`
- 不修改 Go 实验：
  - `services/psdlike-go/`
- 不修改主线 Go backend：
  - `services/backend-go/`
- 不把 `ultralytics` / `onnxruntime` 加入 `services/psdlike-python` 产品依赖。
- 不让 pipeline 内部直接加载模型；第一版只读取外部生成的 `model_evidence.v1.json`。
- 不做 Auto Layout、组件化、真实 Figma component、semantic UI tree。

## Evidence Contract

### Raw Model Evidence

原始模型证据必须不可变地保留：

```json
{
  "version": "model_evidence.v1",
  "model": {
    "path": "/path/to/best.onnx",
    "hash": "optional"
  },
  "sourceImage": "/path/to/source.png",
  "canvas": {"width": 941, "height": 1672},
  "detections": [
    {
      "id": "det_0001",
      "className": "TextButton",
      "confidence": 0.87,
      "bbox": {"x": 40, "y": 120, "width": 180, "height": 52}
    }
  ]
}
```

### Matched Semantic Evidence

模型框与 PSD-like physical layer / OCR block 匹配后，生成可追踪 semantic evidence：

```json
{
  "tag": "TextButton",
  "source": "model_evidence",
  "detectionId": "det_0042",
  "confidence": 0.87,
  "authority": "hint",
  "match": {
    "layerId": "shape_0012",
    "iou": 0.42,
    "detectionCoverageByLayer": 0.91,
    "layerCoverageByDetection": 0.78
  }
}
```

`authority` 必须是 `hint`、`risk` 或 `audit`。禁止写成 `truth`。

### Ownership Decision Evidence

最终采用或拒绝模型证据时，必须写 reason：

```json
{
  "detectionId": "det_0042",
  "decision": "accepted_local_control_surface",
  "layerId": "shape_0031",
  "reason": "ocr_containment_and_fill_ring_passed"
}
```

拒绝也必须可审计：

```json
{
  "detectionId": "det_0091",
  "decision": "rejected_model_control",
  "reason": "failed_fill_stability_or_ocr_containment"
}
```

## Stage Plan

### Stage 106A: Semantic Evidence Ingestion

目标：

```text
读取可选 model_evidence.v1.json
-> normalize detections
-> match existing layers/OCR by IoU/IoA
-> add semanticTags/meta diagnostics
-> 不改变最终 visible layers
```

允许变化：

- `layer_stack.v1.json` 中可新增 meta / semanticTags。
- `ownership_report.v1.json` 可新增 semantic evidence diagnostics。
- `diagnostics.md` 可新增模型语义统计。

禁止变化：

- 不改变 `TextLayer`、`RasterLayer`、`ShapeLayer` 数量。
- 不新增/删除 asset。
- 不改变 preview 视觉输出。
- 不改变 DSL 可见图层结构，除非只是可忽略 meta。

验收：

```text
86/86 pass
visible metrics 与无模型输入一致
semanticTags 存在且 sourceRefs 可追踪
YOLO Text 不生成 TextLayer
YOLO bbox 不生成 asset
```

### Stage 106B: Control Local Re-Search

目标：

```text
TextButton/EditText 等 control detection
-> 只作为局部搜索窗口
-> 在窗口内重新跑 OCR anchored control surface evidence
-> 通过 OCR + fill/ring/padding gate 才生成 ShapeLayer
```

适用类别：

```text
TextButton
EditText
Spinner
Switch
CheckedTextView
Multi_Tab
Bottom_Navigation
```

硬 gate：

```text
OCR containment / adjacency evidence
non-text fill stability
outer ring contrast
reasonable padding
not full-page backing
not high-texture image
does not consume OCR text pixels
```

禁止：

```text
TextButton bbox -> direct ShapeLayer
control bbox -> raster crop
control bbox -> inpaint
model confidence alone -> ownership
```

验收：

```text
low-control cases improved
controlSurfaceShapeLayerCount 不系统性下降
rawTextOverlapRaster 不上升
rasterTextKnockoutCount 不上升
visualMae 不系统性变差
```

重点观察 105 报告里的 low-control cases：

```text
case_0005_0d3f09a5d3
case_0028_4e77499f09
case_0037_7aa443d6c7
case_0085_fcd7ad45fe
```

### Stage 106C: Media/Icon Local Re-Search

目标：

```text
Icon/Image/BackgroundImage/Map detection
-> 只作为局部 media candidate search window
-> 在窗口内用 texture/edge/connected component 重新验证
-> 通过物理证据才补 RasterLayer
```

适用类别：

```text
Icon
Image
BackgroundImage
Map
```

硬 gate：

```text
low OCR overlap
local texture/edge or alpha-like foreground evidence
not full-page backing
not button/control background
asset bbox supported by pixels, not only model bbox
```

禁止：

```text
YOLO Image bbox -> direct asset crop
YOLO Icon bbox -> direct asset crop
Image detection covering OCR -> suppress OCR
```

验收：

```text
mediaMissingPhysicalCandidate 下降
missingAssetCount = 0
fullPageVisibleRaster = 0
tinyRasterFragments 不上升
OCR/raster overlap 不上升
```

重点观察 105 报告里的 media-missing cases：

```text
case_0039_833980d531
case_0038_7cf2a4adbb
case_0053_a6e0f6d72d
case_0078_e4388a0954
case_0082_f1a0a7922e
case_0016_29094ac707
```

### Stage 106D: Semantic Evidence Audit Layer

目标：

```text
把语义证据沉淀为可读报告和后续组件化输入
```

输出：

```text
semantic_evidence_report.md
semantic_tags_summary.json
model_ownership_decisions.v1.json
```

用途：

- 后续组件化命名。
- 后续分组/Frame 语义 hints。
- 后续 Auto Layout readiness 评估。
- 审计模型误检和误用风险。

禁止：

- 不把 semantic tag 升级成 structural owner。
- 不创建 Button/ListView/Toolbar/BottomNavigation 作为 first-version Draft layer kind。
- 不从语义标签反推文字。

## Pipeline Position

模型证据接入点应位于物理候选产生之后、ownership planner 之前：

```text
load image / OCR
-> physical evidence
-> raster / shape / control candidates
-> optional model_evidence ingestion
-> semantic matching
-> optional local physical re-search
-> ownership planner
-> assets
-> layer stack
-> DSL
-> previews / reports
```

不允许模型证据绕过 ownership planner。

## Validation Plan

### Static

```bash
cd services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

### No-Model Equivalence

无模型输入时，必须保持当前 PSD-like Python service 行为：

```text
case_0003 与 oracle key metrics delta = 0
case_0004 与 oracle key metrics delta = 0
10-case batch pass
```

### Model Metadata-Only Validation

Stage 106A：

```bash
cd services/psdlike-python
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_model_assisted_metadata_eval_all \
  --limit 0
```

验收：

```text
86/86 pass
DSL valid = 100%
missingAssetCount = 0
shapeAssetCount = 0
fullPageVisibleRaster = 0
visible layer counts unchanged from no-model run
semanticTags count > 0
```

### Model-Assisted Visible Validation

Stage 106B/106C 后：

```bash
cd services/psdlike-python
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_model_assisted_visible_eval_all \
  --limit 0
```

硬门：

```text
86/86 pass
DSL valid = 100%
missingAssetCount = 0
shapeAssetCount = 0
fullPageVisibleRaster = 0
TextLayer count 不低于无模型合法值
rawTextOverlapRaster 不高于无模型
rasterTextKnockoutCount 不高于无模型
```

质量门：

```text
low-control cases improved
media-missing physical candidates reduced
visualMae 平均值不系统性变差
worst regression cases 写 ledger
```

## Anti-Specialization Rules

实现中禁止使用：

```text
case id
file path
image name
visible copy/text
brand
fixed coordinate
fixed bbox
fixed screen size
```

允许使用：

```text
source pixels
OCR bbox/confidence
model class/confidence/bbox as hint
relative geometry
IoU/IoA
local color/edge/texture evidence
image-scale-normalized thresholds
```

## Stop Conditions

立即停止并写 blocker / failure report：

- 模型输入导致无模型路径漂移。
- YOLO Text 影响 OCR authority。
- model bbox 被直接写成 final asset crop。
- rawTextOverlapRaster 或 rasterTextKnockoutCount 系统性上升。
- low-control 修复只改善个别样本但引入更多误检。
- media/icon 补漏开始误吞按钮、卡片背景或 OCR 文本。

## Commit Strategy

每个阶段独立提交：

```text
docs: plan psdlike model-assisted semantic evidence pipeline
feat: ingest psdlike model semantic evidence
feat: add model-assisted control local search
feat: add model-assisted media local search
test: add psdlike semantic evidence audit reports
```

每个提交必须包含对应验证输出摘要，不能把 dependency、算法、批量报告、生成 artifacts 混在一个提交里。
