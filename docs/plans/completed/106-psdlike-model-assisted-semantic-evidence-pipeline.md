# 106 PSD-like Model-Assisted Semantic Evidence Pipeline

- 状态：completed，106A/106B/106C/106D implemented and validated
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

本计划当前按顺序执行 106B、106C、106D。106A 的 metadata-only 合同保持不变；106B/106C 只允许把模型证据作为局部物理重搜窗口，106D 只增加审计 artifact。

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

状态：implemented。

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

实现边界：

```text
低置信度 detection 只进 semantic/audit，不改变 visible layer。
高置信度 detection 只扩大局部搜索候选，不跳过物理 gate。
小文字大按钮不能直接复用 OCR-anchor 的 area-ratio gate；model-window gate 复用 fill/ring/padding/texture/text-contrast primitive。
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

状态：implemented。

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

状态：implemented。

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

106A 的模型证据接入点位于 final physical layer stack 生成之后、写 artifacts 之前：

```text
load image / OCR
-> physical evidence
-> raster / shape / control candidates
-> ownership planner
-> assets
-> final physical layer stack
-> optional model_evidence ingestion
-> semanticTags / semanticEvidence diagnostics
-> DSL
-> previews / reports
```

106A 禁止模型证据影响 candidates、ownership、assets、inpaint 或任何 visible layer 字段。

106B/106C 当前执行时，模型证据被拆成 early context 和 late annotation：

```text
load image / OCR
-> physical evidence
-> raster / shape / control candidates
-> early model_evidence context
-> optional local physical re-search
-> ownership planner
-> assets
-> layer stack
-> late semantic matching / tags / audit
-> DSL
-> previews / reports
```

不允许模型证据绕过 ownership planner。

106B/106C 的固定顺序：

```text
1. existing physical candidates
2. existing OCR anchored control surfaces
3. 106B model-assisted control search
4. merge shape/control candidates
5. promote complex/control surfaces
6. suppress control-owned raster
7. 106C model-assisted media refinement
8. suppress text-owned raster fragments
9. assign media-owned text blocks
10. ownership/assets/layer_stack
11. late semanticTags + audit reports
12. DSL/previews/reports
```

## 106A Validation Evidence

实现范围：

```text
services/psdlike-python/app/core/model_evidence.py
services/psdlike-python/app/core/pipeline.py
services/psdlike-python/app/core/dsl.py
services/psdlike-python/app/core/reports.py
services/psdlike-python/app/api.py
services/psdlike-python/tools/run_one.py
services/psdlike-python/tools/batch_eval.py
services/psdlike-python/tests/test_core_pipeline.py
```

验证命令：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --out /Users/luhui/Downloads/psdlike_106a_nomodel_eval_10_final \
  --limit 10
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_106a_model_metadata_eval_10_final \
  --limit 10
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_106a_model_metadata_eval_all_final \
  --limit 0
```

结果：

```text
py_compile pass
pytest: 10 passed
10-case no-model: 10/10 pass
10-case model metadata: 10/10 pass
10-case visible diffs between no-model and model: 0
86-case model metadata: 86/86 pass
DSL valid: 86/86
missingAssetTotal: 0
shapeAssetTotal: 0
fullPageVisibleRasterTotal: 0
semanticTagTotal: 2583
modelDetectionTotal: 8866
modelControlDetectionTotal: 531
modelMediaDetectionTotal: 3134
modelOcrOverlapRiskTotal: 297
ignoredCount: 0
visible diffs vs /Users/luhui/Downloads/psdlike_python_service_eval_all: 0
FastAPI smoke: POST /api/draft-preview with modelEvidence completed; /dsl and /preview returned 200
```

## 106B/106C Validation Evidence

实现范围：

```text
services/psdlike-python/app/core/model_control.py
services/psdlike-python/app/core/model_media.py
services/psdlike-python/app/core/pipeline.py
services/psdlike-python/app/core/layers.py
services/psdlike-python/app/core/media_text.py
services/psdlike-python/app/core/reports.py
services/psdlike-python/tools/batch_eval.py
services/psdlike-python/tests/test_core_pipeline.py
```

验证命令：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --out /Users/luhui/Downloads/psdlike_106c_nomodel_eval_10 \
  --limit 10
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_106c_model_visible_eval_10_r2 \
  --limit 10
```

结果：

```text
py_compile pass
pytest: 22 passed
10-case no-model: 10/10 pass
10-case model visible: 10/10 pass
missingAssetTotal: 0
shapeAssetTotal: 0
fullPageVisibleRasterTotal: 0
rawTextOverlapRaster: no-model 4, model 4
rasterTextKnockoutCount: no-model 7, model 7
modelControlAcceptedTotal: 22
modelMediaAcceptedTotal: 131
modelMediaAddedRasterTotal: 5
modelMediaMergedRasterTotal: 0
modelMediaOwnedTextSuppressedTotal: 5
semanticTagTotal: 341
```

全量 86-case 最终验证：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_106bcd_model_visible_eval_all_r3 \
  --limit 0
```

结果：

```text
86-case model visible: 86/86 pass
DSL valid: 86/86
missingAssetTotal: 0
shapeAssetTotal: 0
fullPageVisibleRasterTotal: 0
rawTextOverlapRasterTotal: no-model 32, model 32
rasterTextKnockoutCountTotal: no-model 52, model 52
textOverlapRasterTotal: no-model 0, model 0
tinyRasterFragmentsTotal: no-model 0, model 0
visualMaeAverage: no-model 9.9612, model 9.9400
visualDiff30RatioAverage: no-model 0.0656, model 0.0654
modelControlAcceptedTotal: 149
modelControlRejectedTotal: 382
modelMediaAcceptedTotal: 1059
modelMediaRejectedTotal: 2075
modelMediaAddedRasterTotal: 20
modelMediaMergedRasterTotal: 0
modelMediaLimitedRasterTotal: 0
modelMediaOwnedTextSuppressedTotal: 33
semanticTagTotal: 2597
modelDetectionTotal: 8866
modelOcrOverlapRiskTotal: 297
quality increases: none for rawTextOverlapRaster, rasterTextKnockoutCount, textOverlapRaster, tinyRasterFragments
```

## 106D Validation Evidence

实现范围：

```text
services/psdlike-python/app/core/reports.py
services/psdlike-python/app/core/pipeline.py
services/psdlike-python/tests/test_core_pipeline.py
```

新增输出：

```text
semantic_evidence_report.md
semantic_tags_summary.json
model_ownership_decisions.v1.json
```

验证命令：

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
uv run python tools/batch_eval.py \
  --manifest /Users/luhui/Downloads/psd_like_v1_baseline_audit_dark_control_eval/input_manifest.v1.json \
  --ocr-cache-dir /Users/luhui/Downloads/psd_like_ocr_cache_test \
  --model-evidence-root /Users/luhui/Downloads/psdlike_model_evidence_eval_all \
  --out /Users/luhui/Downloads/psdlike_106d_model_audit_eval_10 \
  --limit 10
```

结果：

```text
py_compile pass
pytest: 22 passed
10-case model audit: 10/10 pass
semantic_evidence_report.md: 10/10 present
semantic_tags_summary.json: 10/10 present
model_ownership_decisions.v1.json: 10/10 present
missingAssetTotal: 0
shapeAssetTotal: 0
fullPageVisibleRasterTotal: 0
rawTextOverlapRasterTotal: 4
rasterTextKnockoutCountTotal: 7
modelControlAcceptedTotal: 22
modelMediaAcceptedTotal: 131
modelMediaAddedRasterTotal: 5
modelMediaOwnedTextSuppressedTotal: 5
semanticTagTotal: 341
```

全量 86-case 审计产物验证：

```text
/Users/luhui/Downloads/psdlike_106bcd_model_visible_eval_all_r3
semantic_evidence.v1.json: 86/86 present
semantic_evidence_report.md: 86/86 present
semantic_tags_summary.json: 86/86 present
model_ownership_decisions.v1.json: 86/86 present
draft_runtime.dsl.v1_0.json: 86/86 present
```

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
