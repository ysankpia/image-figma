# 067 M29 Model-First Perception Implementation

- 状态：superseded
- 创建日期：2026-05-27
- 负责人：Codex

归档说明：本 implementation plan 的方向已由 068 破坏性主链重构实际落地，并由后续完成计划继续修 model-first 回归。本文保留为实施背景，不再代表 active runtime work。

## Goal

把当前 M29 主线从“手写视觉感知模型”改成“模型优先感知 + M29 ownership compiler”。

真实目标不是继续证明每个像素候选，而是：

```text
source screenshot
-> editable/selectable/visually faithful Figma design
```

当前问题的第一性原理判断：

```text
M29 继续增长 visual detectors / M29.6 / evidence weights / promotion loops，
本质是在用 Python 手写视觉模型。
```

本计划将职责改成：

```text
model_fp16.onnx:
  find visible UI object proposals as bbox candidates

OCR:
  provide text content and text boxes

M29:
  compile OCR + model candidates into source ownership,
  relation graph,
  replay plan,
  cleanup authorization,
  materialization safety
```

最终目标效果是：一张截图进入系统后，Figma 里尽可能还原为可编辑文字、可选择按钮/图标/胶囊/卡片/导航项，并保留复杂主视觉为 residual raster。不是为了输出更多框，也不是为了让模型直接替代 Figma/Renderer。

## Scope

包含：

- 引入 report-only `perception_model_report`，消费 `/Volumes/WorkDrive/Models/model_fp16.onnx`，输出 normalized UI object proposals。
- 将模型候选作为 M29.2 source ownership 的主要视觉候选来源。
- 用模型候选替换或降级 M29.6 中最脆弱的 connected component / OCR-anchor / action-row / marker / internal media detector 逻辑。
- 把 `internal_source_promotion` 的长链路收敛成更直接的 source compiler 路径，避免 M29.6 -> transparent -> evidence -> promotion -> rerun 的循环依赖继续膨胀。
- 保留 M29.3 relation、M29.4 weak evidence、M29.5 replay plan、ownership conservation、materializer、Renderer 和 Figma plugin 的边界。
- 对 `/Users/luhui/Downloads/m29` 做真实样本验证，重点覆盖前 10 张 `ChatGPT Image 2026年5月17日 14_47_13 (...).png` 和恶心图 `微信图片_20260524225318_199_118.png`。

不包含：

- 不修改 public API、DSL schema、Renderer protocol、Figma plugin protocol。
- 不把模型输出直接变成 DSL visible nodes。
- 不让 bridge fate、materializer、Renderer 或 plugin 发明 source ownership。
- 不提交模型二进制文件。
- 不按文件名、文案、品牌、坐标、主题色、截图尺寸、单样本结构写特化规则。
- 不承诺一次提交达到 Codia 全量效果；每阶段必须用真实图片和 artifact 证明收益。

## First-Principles Contract

### Real Goal

用户需要的是：

```text
截图 -> Figma 可编辑设计稿
```

不是：

```text
更复杂的 M29 evidence report
更多阈值
更多 bridge fate blocker
更多局部规则
```

### Source Truth

不可替代的 source truth：

```text
source PNG pixels
OCR text content and boxes
model object proposal boxes
M29 source ownership decisions
M29.5 replay/cleanup authorization
```

模型输出不是最终 truth。它是 perception proposal truth：这里可能有 UI 对象。最终 source ownership 仍由 M29 编译。

### Information-Loss Point

当前链路最大的信息损失发生在：

```text
raw M29 / M29.2 过早把 composite media 归为 full preserve_raster
```

之后 M29.6 再去 media 里挖对象，已经变成补救。模型-first 后，感知候选必须在 source ownership 前进入，而不是在 M29.5 后面补救。

### Wrong Abstraction To Remove

需要逐步拆掉的错误抽象：

```text
M29.6 as primary visual recognizer
transparent asset as candidate gate
evidence contract as visual existence judge
internal source promotion as rerun bridge
```

正确抽象：

```text
perception model report = visual proposal layer
M29.2 source ownership = compiler input boundary
M29.5 replay plan = visible node and cleanup authority
```

## Module Replacement Map

### Replace First

`backend/app/media_internal_decomposition/`

当前它承担 M29.6 media 内部 object detection：OCR anchor、non-OCR foreground、marker、table dot、icon、action row、component top-N、scale gates。模型-first 后，它应降级为 fallback/debug，不再是主视觉发现层。

替代目标：

```text
backend/app/perception_model_report/
```

### Downgrade To Utility / Fallback

`backend/app/visual_primitive/`

保留：

```text
bbox.py
mask.py
metrics.py
pixels.py
geometry.py
artifacts.py
validation.py
relations.py
```

降级或减少主线依赖：

```text
components.py
detectors.py
support.py
support_scoring.py
```

这些 detector 不应继续作为 primary perception source。

### Rewrite Responsibility

`backend/app/m29_evidence_contract/`

从：

```text
does this visual object exist?
```

改成：

```text
can this model/OCR candidate be safely compiled into source ownership?
```

### Simplify

`backend/app/transparent_asset_report/`

从：

```text
candidate filter + alpha asset + visible replay gate
```

改成：

```text
asset/mask builder for already accepted candidates
```

### Replace / Rename Later

`backend/app/internal_source_promotion/`

当前它是 M29.6 evidence 回写 M29.2 的桥。模型-first 后应该被更直接的 compiler 替代：

```text
backend/app/perception_source_compiler/
```

## Target Mainline

阶段性目标主线：

```text
Figma Plugin
-> POST /api/upload-preview
-> OCR
-> perception_model_report
-> raw M29 fallback primitives
-> M29.2 source ownership compiler
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> ownership conservation
-> optional transparent/mask asset build
-> bridge fate / model fate trace
-> plan materializer
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma
```

Long-term target after stabilization:

```text
OCR
-> model perception candidates
-> M29.2 source ownership
-> M29.3 relation
-> M29.5 replay/cleanup
-> materializer
```

The older M29.6/promotion loop becomes compatibility fallback, not the primary path.

## Validation Dataset

Primary validation set:

```text
/Users/luhui/Downloads/m29
```

Observed image count:

```text
16 images
```

Stage gate subsets:

```text
M29 ten-image set:
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月17日 14_47_13 (1).png
  ...
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月17日 14_47_13 (10).png

Hard regression image:
  /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png

Additional 525/login/composite images:
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月23日 17_37_14.png
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月23日 17_39_56.png
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月23日 17_48_23.png
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月23日 17_50_34.png
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月23日 17_52_19.png
```

The first ten images are the main stage gate. The hard regression image must be inspected in every runtime integration stage, because previous rule-based M29 changes repeatedly failed there.

## Acceptance Definition

A stage cannot pass by saying candidate count improved. It must show artifact-level progress toward editable Figma output.

Per-image acceptance checklist:

- OCR text that should be normal UI text becomes editable text.
- Buttons have selectable background shape or image/control node, not only editable text floating over a dead raster.
- Icons inside buttons/nav/action rows are selectable as image/icon nodes when model/OCR evidence supports them.
- Pills, badges, selected markers, table/status dots, and circular controls become selectable shape or icon nodes when evidence supports them.
- Complex hero artwork remains residual raster and is not exploded into junk nodes.
- Parent raster does not duplicate foreground objects after cleanup authorization; if cleanup is unsafe, the trace must say so and visible replay must remain.
- Materializer consumes only M29.5 replay/cleanup plan, not raw model output.

Project-level acceptance:

- No public API/DSL/plugin/Renderer protocol changes.
- No sample-specific rules.
- `/Users/luhui/Downloads/m29` batch produces ledgers and artifacts that identify which images improved, regressed, or remain blocked.
- For any remaining failure, there is a first blocking layer in a trace/report, not a mystery.

## Implementation Phases

### Stage 0: Baseline And Model Probe Ledger

Use the existing probe script to run the model on `/Users/luhui/Downloads/m29` and write a stable comparison ledger under `backend/tmp/`.

Command:

```bash
cd backend
uv run --with onnxruntime --with pillow --with numpy python scripts/probe_onnx_model.py \
  --model /Volumes/WorkDrive/Models/model_fp16.onnx \
  --input /Users/luhui/Downloads/m29 \
  --output-dir tmp/model_probe_m29 \
  --input-size 960 \
  --score-threshold 0.05 \
  --top-k 80
```

Acceptance:

- `probe_results.json` exists.
- overlays exist for all 16 images.
- first ten images and hard regression image have visible candidate boxes.
- If the model misses a critical object, record it as model limitation, not an M29 bug.

Initial Stage 0 run:

```text
report: backend/tmp/model_probe_m29/probe_results.json
summary: imageCount=16, candidateCount=931
hard regression image: 微信图片_20260524225318_199_118.png, candidateCount=13
```

The hard regression image has model candidates for the visible login controls. That proves the next blocker is not candidate recall; it is how candidates become M29 source ownership, replay, and cleanup.

Commit boundary:

```text
No runtime code unless fixing probe-only script defects.
```

### Stage 1: Report-Only Perception Model Package

Create:

```text
backend/app/perception_model_report/
backend/tests/test_perception_model_report.py
```

Responsibilities:

- Load ONNX model only when explicitly configured or called by tests.
- Normalize output into provider-neutral candidates:

```text
candidateId
sourceProvider
modelPathHash
bbox
score
areaRatio
rawOutputRef
roleHint = unknown_ui_object
```

- Write:

```text
m29_perception_model/perception_model_report.json
```

- Produce optional overlay preview artifacts.

Dependency policy:

- This stage may add `onnxruntime` only after documenting why temporary `uv --with` is insufficient for runtime integration.
- If dependency risk is unclear, keep package callable only from scripts/tests with optional import.

Acceptance:

- Unit tests decode `[1, 5, anchors]` model-like output deterministically.
- Report is read-only: `createdVisibleNodeCount=0`, `dslChanged=false`, `materializationChanged=false`.
- No upload-preview behavior changes by default.

Implementation status:

```text
backend/app/perception_model_report/ added as report-only package.
backend/tests/test_perception_model_report.py covers decoder, report-only invariant, missing model/raw-output guard, and optional onnxruntime import behavior.
backend/scripts/probe_onnx_model.py now reuses the package decoder/preprocess logic to avoid probe/runtime drift.
```

Stage 1 smoke:

```text
image: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
report: backend/tmp/perception_model_stage1_smoke/perception_model_report.json
summary: candidateCount=13, reportOnly=true, sourceOwnershipChanged=false, materializationChanged=false
```

### Stage 2: Upload Pipeline Report-Only Integration

Add a report-only pipeline stage, initially guarded by env and now enabled by default:

```text
perception_model_report
```

Gate it behind settings/env:

```text
M29_PERCEPTION_MODEL_ENABLED=true
M29_PERCEPTION_MODEL_PATH=/Volumes/WorkDrive/Models/model_fp16.onnx
```

This was initially kept off while dependency and batch evidence stabilized; Stage 15 makes it default-on.

Acceptance:

- With env enabled, `/api/upload-preview` writes `m29_perception_model/perception_model_report.json`.
- With env disabled, current pipeline output remains unchanged.
- No DSL/materialization changes in this stage.
- Batch run on `/Users/luhui/Downloads/m29` completes with report artifacts.

Implementation status:

```text
M29_PERCEPTION_MODEL_ENABLED and M29_PERCEPTION_MODEL_PATH added to backend settings and env docs.
upload-preview can emit m29_perception_model/perception_model_report.json.
historical note: Stage 2 initially kept default production behavior unchanged; Stage 15 later changes the default to model-first.
```

Stage 2 smoke:

```text
image: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
env: M29_PERCEPTION_MODEL_ENABLED=true, M29_PERCEPTION_MODEL_PATH=/Volumes/WorkDrive/Models/model_fp16.onnx
report: backend/tmp/stage2_optin_storage/upload_previews/stage2_smoke/m29_perception_model/perception_model_report.json
result: perception report exists, final design.dsl.json exists
```

### Stage 3: Perception Source Compiler Prototype

Create:

```text
backend/app/perception_source_compiler/
backend/tests/test_perception_source_compiler.py
```

Input:

```text
OCR document
perception model report
source PNG pixels
current M29.2 document
```

Output:

```text
enhanced M29.2 source objects
compiler report
```

Initial compiler rules must stay generic:

- model candidate containing OCR text -> possible control/card/background owner.
- model candidate with child OCR + small candidate relation -> possible button/control group.
- model candidate with no OCR but compact and high score -> possible raster icon/image owner.
- candidate overlapping huge hero area -> preserve residual media / report only unless OCR/control relation supports it.
- repeated aligned candidates -> row/action/nav evidence.

Forbidden:

- no text literal/brand/file/path/coordinate rules.
- no direct DSL nodes.
- no cleanup authorization.

Acceptance:

- Synthetic tests prove button background, icon, pill, and circular control candidates become M29.2 source objects.
- False-positive hero/texture candidates remain media/report-only.
- M29.3/M29.5 can consume the enhanced M29.2 document without schema changes.

Implementation status:

```text
backend/app/perception_source_compiler/ added as an independent compiler prototype.
It consumes OCR + perception_model_report + source PNG + current M29.2 and writes an enhanced M29.2 document plus perception_source_compiler_report.json.
It does not create DSL nodes, assets, cleanup authorization, or materializer shortcuts.
```

Compiler contract:

```text
model candidate with contained OCR -> control_background / shape_replay source object
compact non-text model candidate -> raster_icon / icon_replay source object with source-crop visible replay evidence
large full-media/hero candidate -> report_only
```

M29.5/ownership support:

```text
perception_model_foreground_claim is recognized as an upstream foreground claim for replay overlap decisions.
Source-crop icon replay may stay visible over parent media.
Copied-image cleanup still requires M29.5 cleanupTargets and remains blocked when no transparent/safe replacement mask exists.
```

Stage 3 validation:

```text
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
result: 71 passed

python3 -m py_compile backend/app/perception_source_compiler/*.py backend/app/m29_replay_plan/*.py backend/app/ownership_conservation/*.py backend/tests/test_perception_source_compiler.py backend/tests/test_ownership_conservation.py
result: passed

git diff --check
result: passed
```

### Stage 4: Upload Preview Source Compiler Integration

Change upload-preview ordering so model proposals can enter source ownership before relation/replay planning:

```text
perception_model_report
-> perception_source_compiler
-> M29.3/M29.4/M29.5 final chain
```

M29.6 remains available as fallback/debug in this stage. It still runs later in the current pipeline for compatibility and diagnostics, but model-proposed source objects no longer need the M29.6 -> transparent -> evidence -> promotion loop before they can be consumed by M29.3/M29.5.

Implementation status:

```text
upload-preview now stores m29_perception_source_compiler artifacts when M29_PERCEPTION_MODEL_ENABLED=true.
The compiler receives OCR, perception_model_report, source PNG pixels, and the current M29.2 document.
The enhanced M29.2 document feeds the subsequent M29.3/M29.4/M29.5 chain.
historical note: Stage 4 initially kept production unchanged; Stage 15 later changes the default to model-first.
```

Dependency status:

```text
historical note: onnxruntime was not a project dependency in Stage 4; Stage 15 adds it because model-first is now the default local runtime.
```

Acceptance:

- The old M29.6 -> transparent -> evidence -> promotion loop is not required for model-proposed button/icon/control source objects.
- Bridge/model fate trace can explain model candidate -> source ownership -> replay/materializer outcome.
- Hard regression image produces perception compiler artifacts and model-proposed source objects before materialization.
- Stage 4 does not yet claim Codia-like final quality; control background inference is expected to continue in Stage 5.

### Stage 5: Control And Button Role Inference

Improve `perception_source_compiler` so it does not treat most model boxes as isolated icons. The compiler should infer control/background ownership from generic relations:

```text
candidate contains OCR text
candidate tightly contains icon/text children
candidate aligns with nearby OCR in a button-like geometry
candidate belongs to a repeated row/nav/action structure
candidate has stable fill/radius/foreground-layer evidence
```

Allowed output:

```text
control_background / shape_replay
raster_icon / icon_replay
indicator shape / shape_replay
residual media report_only
```

Forbidden:

```text
no brand/text literal/file/path/task-id/fixed-coordinate rules
no materializer/Renderer/plugin semantic patch
no direct DSL node creation from model candidates
```

Acceptance:

- The first ten `/Users/luhui/Downloads/m29` images show improved control/background source ownership without node explosion.
- The hard regression image has source paths for visible button backgrounds, button icons, and editable OCR text where model/OCR evidence supports them.
- Rejected candidates carry actionable compiler reasons, not generic mystery failures.
- M29.5 consumes compiler-created source objects through normal replay planning.

Implementation status:

```text
perception_source_compiler now treats preserve_raster media as residual-capable parent ownership, not a duplicate that suppresses foreground control claims.
Generic horizontal control geometry can compile to control_background / shape_replay when score, area, aspect, fill, texture, edge, and image-scale gates pass.
Low-score compact candidates can compile to raster_icon only when they are strongly contained by an already compiled control background.
Loose low-score fragments remain report_only.
```

Stage 5 validation:

```text
focused tests:
  cd backend
  uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
  result: 74 passed

py_compile:
  python3 -m py_compile backend/app/perception_source_compiler/*.py backend/tests/test_perception_source_compiler.py
  result: passed

hard regression direct pipeline:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  output root: backend/tmp/stage5_hard_smoke_storage/upload_previews/stage5_hard_smoke
  perceptionCandidateCount: 13
  compiledSourceObjectCount: 8
  compiledControlBackgroundCount: 4
  compiledRasterIconCount: 4
  plannedShapeReplayCount: 7
  plannedIconReplayCount: 31
  dslRootChildCount: 35

first ten direct pipeline:
  summary: backend/tmp/stage5_first10_direct_summary.json
  failed: 0 / 10
  Stage 4 totals: compiled=60, controls=1, icons=59
  Stage 5 totals: compiled=118, controls=28, icons=90
```

Remaining risk:

```text
Stage 5 uses OCR_PROVIDER=fake in direct pipeline validation because real OCR credentials are environment-dependent.
The compiler still needs artifact inspection for the one first-ten image with compiledControlBackgroundCount=0.
Cleanup quality remains Stage 6; this stage proves source ownership and replay path improvement, not final residual erasure.
```

### Stage 6: Asset And Residual Cleanup

Use existing M29.5 cleanup authority for model-proposed foreground objects.

Rules:

- Button/pill/card backgrounds replay as `shape_geometry` when fill/radius evidence is safe.
- Icons replay as cropped image/icon assets when transparent alpha is unavailable.
- Parent media remains residual raster.
- Cleanup risk blocks erasure only, not visible replay.

Acceptance:

- Parent copied image asset does not duplicate replayed foreground when cleanup is authorized.
- If cleanup is unsafe, final DSL still contains selectable foreground node and the trace records cleanup blocker.
- Materializer still refuses cleanup not present in M29.5.

Implementation status:

```text
M29.5 shape cleanup risk no longer treats raw model score as the only cleanup authority for styled foreground controls.
Low-score perception foreground claims can authorize copied-image cleanup only when the role is a styled control-like shape:
  internal_control_background
  internal_overlay_badge
  internal_pill_button
  internal_circle_control
Unstyled marker/table/status shapes still require the existing evidence score gate and remain blocked when evidence is weak.
Materializer still consumes only final M29.5 cleanupTargets.
```

Stage 6 validation:

```text
focused tests:
  cd backend
  uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_perception_source_compiler.py -q
  result: 76 passed

py_compile:
  python3 -m py_compile backend/app/m29_replay_plan/*.py backend/tests/test_m29_replay_plan.py
  result: passed

hard regression direct pipeline:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  output root: backend/tmp/stage6_hard_smoke_storage/upload_previews/stage6_hard_smoke
  compiledControlBackgroundCount: 4
  compiledRasterIconCount: 4
  plannedShapeReplayCount: 7
  copiedImageAssetCleanupTargetCount: 7
  copiedImageAssetShapeErasedCount: 5
  visibleNodeCount: 44

first ten direct pipeline:
  summary: backend/tmp/stage6_first10_direct_summary.json
  failed: 0 / 10
  Stage 5 totals: compiled=118, controls=28, icons=90, cleanupTargets=0, shapeErased=0, internalErased=0
  Stage 6 totals: compiled=118, controls=28, icons=90, cleanupTargets=85, shapeErased=82, internalErased=3
```

Remaining risk:

```text
Icon residual cleanup still blocks source-crop icons without transparent replacement; this is intentional until a safe mask exists.
One first-ten image still has cleanupTargets=0; this needs artifact inspection in Stage 7, not a single-image rule.
Direct validation still uses OCR_PROVIDER=fake because real OCR credentials are environment-dependent.
```

### Stage 7: Real Sample Batch And Figma-Facing Inspection

Enhance the HTTP batch validation script so it can run the model-first path and record perception evidence.

Script requirements:

```text
--perception-model-path /Volumes/WorkDrive/Models/model_fp16.onnx
# --disable-perception-model is available only for compatibility isolation
```

The ledger must record perception/compiler/replay/materializer metrics, not just task success:

```text
perceptionCandidateCount
compiledSourceObjectCount
compiledControlBackgroundCount
compiledRasterIconCount
plannedShapeReplayCount
plannedIconReplayCount
copiedImageAssetCleanupTargetCount
copiedImageAssetShapeErasedCount
copiedImageAssetInternalErasedCount
materializedVisibleNodeCount
```

Run the first ten:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --max-files 10 \
  --poll-timeout 300 \
  --startup-timeout 60 \
  --perception-model-path /Volumes/WorkDrive/Models/model_fp16.onnx
```

Run the hard regression image by copying it into a temporary one-image input directory and using the same command without `--max-files`.

Inspect:

```text
upload_preview_batch_validation.json
design.dsl.json
materialization_report.json
perception_model_report.json
compiler report
bridge/model fate trace
```

For the first ten images and the hard regression image, record:

```text
editable text count
selectable image/icon count
selectable shape/control count
residual media count
cleanup target count
visible replay blockers
regressions
```

Acceptance:

- Meaningful improvement over current M29 on first ten images.
- Hard regression image has selectable button backgrounds/icons/text where model evidence supports them.
- Remaining failures are classified into model miss, OCR miss, ownership compiler blocker, cleanup blocker, or materializer blocker.

Implementation status:

```text
backend/scripts/run_upload_preview_batch_validation.py supports model-first runtime by default with --perception-model-path and a --disable-perception-model compatibility switch.
Ledger schemaVersion is 0.3 and records runtimeOptions plus perception/compiler/replay/materializer counters.
Perception artifacts are required by default model-first validation. Compatibility isolation can disable them with --disable-perception-model. Stage 15 later adds onnxruntime as a backend dependency.
```

Stage 7 validation:

```text
focused tests:
  cd backend
  uv run pytest tests/test_upload_preview_batch_validation_script.py -q
  result: 6 passed

py_compile:
  python3 -m py_compile scripts/run_upload_preview_batch_validation.py tests/test_upload_preview_batch_validation_script.py
  result: passed

diff check:
  git diff --check
  result: passed

first ten HTTP batch:
  ledger: backend/tmp/validation/upload_preview_batch_20260527_025602/upload_preview_batch_validation.json
  completedTaskCount: 10 / 10
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalPerceptionCandidateCount: 659
  totalCompiledSourceObjectCount: 139
  totalCompiledControlBackgroundCount: 104
  totalCompiledRasterIconCount: 35
  totalPlannedShapeReplayCount: 242
  totalPlannedIconReplayCount: 380
  totalCopiedImageAssetCleanupTargetCount: 173
  totalCopiedImageAssetShapeErasedCount: 39
  totalCopiedImageAssetInternalErasedCount: 9
  totalMaterializedVisibleNodeCount: 1593
  totalVisibleOwnershipOverlapConflicts: 8
  averageDslVisualGateNormalizedMeanAbsError: 0.013056
  maxDslVisualGateChangedPixelRatio10: 0.171102

hard regression HTTP batch:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  ledger: backend/tmp/validation/upload_preview_batch_20260527_030126/upload_preview_batch_validation.json
  completedTaskCount: 1 / 1
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalPerceptionCandidateCount: 13
  totalCompiledSourceObjectCount: 6
  totalCompiledControlBackgroundCount: 4
  totalCompiledRasterIconCount: 2
  totalPlannedShapeReplayCount: 13
  totalPlannedIconReplayCount: 9
  totalCopiedImageAssetCleanupTargetCount: 17
  totalCopiedImageAssetShapeErasedCount: 12
  totalCopiedImageAssetInternalErasedCount: 0
  totalMaterializedVisibleNodeCount: 35
  averageDslVisualGateNormalizedMeanAbsError: 0.007875
  maxDslVisualGateChangedPixelRatio10: 0.055304
```

Stage 7 conclusion:

```text
The model-first path is now reproducible through the real /api/upload-preview HTTP flow.
Candidate recall is no longer the first blocker on the hard regression image.
The next owning layer is quality hardening in perception_source_compiler and residual cleanup:
  first-ten image (8) has compiled controls/icons but copiedImageAssetCleanupTargetCount=0.
  source-crop icon cleanup still rarely executes because transparent/safe replacement is missing.
  first-ten batch still has 8 visible ownership overlap conflicts.
Do not patch Renderer/plugin/materializer to hide these; continue at source ownership/replay cleanup layers.
```

### Stage 8: Perception Ownership Quality Hardening

First Stage 7 repair:

```text
problem:
  Some low-score model candidates inside compiled controls were compiled as raster_icon even when their bbox overlapped OCR text.

first-principles owner:
  perception_source_compiler

reason:
  An icon source owner cannot claim pixels that are already owned by editable text.
  This is source ownership conflict, not a Renderer/plugin/materializer issue.

fix:
  Add a stricter max_control_child_icon_text_overlap gate only for low-score child-icon inference.
  Keep normal high-confidence compact icon inference unchanged.
```

Validation:

```text
focused tests:
  cd backend
  uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
  result: 77 passed

py_compile:
  python3 -m py_compile app/perception_source_compiler/*.py tests/test_perception_source_compiler.py
  result: passed

first ten HTTP batch after repair:
  ledger: backend/tmp/validation/upload_preview_batch_20260527_030822/upload_preview_batch_validation.json
  completedTaskCount: 10 / 10
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  previous Stage 7 value: 8
  totalCompiledSourceObjectCount: 125
  previous Stage 7 value: 139
  totalCompiledControlBackgroundCount: 104
  previous Stage 7 value: 104
  totalCompiledRasterIconCount: 21
  previous Stage 7 value: 35
  totalMaterializedVisibleNodeCount: 1591
  previous Stage 7 value: 1593
  totalCopiedImageAssetCleanupTargetCount: 173
  averageDslVisualGateNormalizedMeanAbsError: 0.013117

hard regression HTTP batch after repair:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  ledger: backend/tmp/validation/upload_preview_batch_20260527_031354/upload_preview_batch_validation.json
  completedTaskCount: 1 / 1
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  totalCompiledSourceObjectCount: 6
  totalCompiledControlBackgroundCount: 4
  totalCompiledRasterIconCount: 2
  totalMaterializedVisibleNodeCount: 35
  averageDslVisualGateNormalizedMeanAbsError: 0.007875
```

Conclusion:

```text
The repair removed all first-ten visible ownership overlap conflicts without reducing control background compilation.
The removed compiled icons were unsafe text-overlapping child-icon candidates.
The next quality owner remains residual cleanup and media-parent assignment:
  first-ten image (8) still has compiled controls/icons but copiedImageAssetCleanupTargetCount=0 because many perception controls have no parent media to erase.
  source-crop icon cleanup remains blocked without transparent/safe replacement.
```

### Stage 9: Source-Crop Icon Residual Cleanup

Second Stage 7 repair:

```text
problem:
  Source-crop icons were visible/selectable but often left duplicated pixels inside their parent copied media because M29.5 required a transparentAssetPath before authorizing copied-image cleanup.

first-principles owner:
  M29.5 cleanup authority + ownership conservation contract

reason:
  A source-crop icon asset is itself a bbox replacement owner.
  If M29.5 has already accepted the icon as visible replay and the icon is contained by its parent media, bbox cleanup is a valid residual media operation.
  Materializer must still consume only M29.5 cleanupTargets; it must not infer this cleanup itself.

fix:
  Allow promoted/perception foreground icon cleanup when sourceEvidence.controlRowSourceCropEligible=true, even without transparentAssetPath.
  Keep text-overlap, parent-media, alpha-risk, and relation containment checks.
  Ownership conservation now accepts this bbox replacement cleanup instead of reporting invalid_copied_image_asset_cleanup.
```

Validation:

```text
focused tests:
  cd backend
  uv run pytest tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_plan_materializer.py -q
  result: 70 passed

py_compile:
  python3 -m py_compile app/m29_replay_plan/cleanup.py app/ownership_conservation/conflicts.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_plan_materializer.py
  result: passed

first ten HTTP batch after repair:
  ledger: backend/tmp/validation/upload_preview_batch_20260527_032053/upload_preview_batch_validation.json
  completedTaskCount: 10 / 10
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  totalCopiedImageAssetCleanupTargetCount: 178
  previous Stage 8 value: 173
  totalCopiedImageAssetInternalErasedCount: 14
  previous Stage 8 value: 9
  totalCompiledSourceObjectCount: 125
  totalCompiledControlBackgroundCount: 104
  totalCompiledRasterIconCount: 21
  totalMaterializedVisibleNodeCount: 1591
  averageDslVisualGateNormalizedMeanAbsError: 0.013117

hard regression HTTP batch after repair:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  ledger: backend/tmp/validation/upload_preview_batch_20260527_032659/upload_preview_batch_validation.json
  completedTaskCount: 1 / 1
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  totalCopiedImageAssetCleanupTargetCount: 18
  previous Stage 8 value: 17
  totalCopiedImageAssetInternalErasedCount: 1
  previous Stage 8 value: 0
  totalMaterializedVisibleNodeCount: 35
  averageDslVisualGateNormalizedMeanAbsError: 0.007875
```

Conclusion:

```text
Source-crop icon residual cleanup is now authorized through M29.5 and audited by ownership conservation.
This improves copied-media residual cleanup without adding materializer, Renderer, plugin, sample, text, brand, or coordinate special cases.
The remaining first-ten image (8) copiedImageAssetCleanupTargetCount=0 is not a materializer failure: its compiled controls have no parent media region to erase, so fallback cleanup is the correct current target.
```

### Stage 10: Perception Text-Region Ownership Guard

After Stage 9, the current HTTP validation path was rerun with collision-resistant output directories and per-record visual gate metrics.

Problem found:

```text
perception_source_compiler treated large text-containing content regions as control_background.
Worst example:
  /Users/luhui/Downloads/m29/ChatGPT Image 2026年5月17日 14_47_13 (10).png
  model candidate bbox [34,326,801,249] covered the carousel/banner media.
  compiler emitted m292_perception_control_0001 as a large rounded_rect shape.
  M29.5 and materializer correctly executed the plan, producing a huge pale-blue pill over the banner.
```

First-principles owner:

```text
perception_source_compiler
```

Reason:

```text
The model is single-class and can propose large UI/content regions.
A text-containing candidate is not automatically a button/control.
Only finite controls, pills, buttons, search fields, and compact UI affordances should claim shape ownership.
Large content/card/banner regions should stay residual media or report-only unless a separate background contract proves a safe card replay.
```

Fix:

```text
Add a generic content-region guard for text-containing perception candidates.
Reject text candidates as control_background when their bbox height is too large relative to contained OCR text height or when they contain too many OCR boxes.
Keep true button/search/pill geometry paths working.
Limit pill radius inference to finite-height controls so large cards do not get half-height pill radii.
Improve batch validation script:
  default output directories now include microseconds and pid to avoid concurrent run collisions.
  each record now exposes top-level visual gate metrics for sorting and inspection.
```

Validation:

```text
focused tests:
  cd backend
  uv run pytest tests/test_upload_preview_batch_validation_script.py -q
  result: 8 passed

  cd backend
  uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
  result: 80 passed

py_compile:
  python3 -m py_compile scripts/run_upload_preview_batch_validation.py tests/test_upload_preview_batch_validation_script.py
  result: passed

  python3 -m py_compile app/perception_source_compiler/*.py tests/test_perception_source_compiler.py
  result: passed

first ten HTTP batch after repair:
  ledger: backend/tmp/validation/upload_preview_batch_20260526_195954_651397_95047/upload_preview_batch_validation.json
  completedTaskCount: 10 / 10
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  totalCompiledSourceObjectCount: 69
  previous Stage 9 value: 125
  totalCompiledControlBackgroundCount: 60
  previous Stage 9 value: 104
  totalCompiledRasterIconCount: 9
  previous Stage 9 value: 21
  totalCopiedImageAssetCleanupTargetCount: 180
  previous Stage 9 value: 178
  averageDslVisualGateNormalizedMeanAbsError: 0.004795
  previous Stage 9 value: 0.013117
  maxDslVisualGateChangedPixelRatio10: 0.043956
  previous Stage 9 value: 0.171102

hard regression HTTP batch after repair:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  ledger: backend/tmp/validation/upload_preview_batch_20260526_195954_649544_95046/upload_preview_batch_validation.json
  completedTaskCount: 1 / 1
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  totalCompiledSourceObjectCount: 4
  previous Stage 9 value: 6
  totalCompiledControlBackgroundCount: 3
  previous Stage 9 value: 4
  totalCompiledRasterIconCount: 1
  previous Stage 9 value: 2
  averageDslVisualGateNormalizedMeanAbsError: 0.005637
  previous Stage 9 value: 0.007875
  maxDslVisualGateChangedPixelRatio10: 0.039108
  previous Stage 9 value: 0.055304
```

Conclusion:

```text
Candidate recall was not the blocker.
The owning failure was source ownership over-claiming in perception_source_compiler.
The repair removes large false control backgrounds, improves visual reconstruction on the first-ten gate set and the hard image, and keeps M29.5/materializer boundaries intact.
Remaining visible error is now mostly font rendering/OCR text fidelity plus smaller icon/cleanup gaps, not the large-banner ownership failure.
```

### Stage 11: Model-First Fate Trace

After Stage 10, the old `m29_bridge_fate_trace` could explain only the M29.6/transparent/evidence/promotion path. It could not explain the new model-first path:

```text
perception candidate
-> perception_source_compiler
-> final M29.5 replay
-> cleanup target
-> materializer result
```

First-principles owner:

```text
diagnostic/report surface
```

Reason:

```text
The model-first path must not hide remaining failures behind old M29.6 bridge diagnostics.
The trace must be read-only and must not feed source ownership, replay, cleanup, materializer, Renderer, or plugin decisions.
```

Implementation status:

```text
backend/app/m29_perception_fate_trace/ added as a report-only diagnostic package.
upload-preview emits m29_perception_fate_trace/perception_fate_trace_report.json when M29_PERCEPTION_MODEL_ENABLED=true.
batch validation now requires and summarizes the perception fate trace only for model-first validation runs.
The trace reports:
  candidateId
  bbox
  score
  compilerDecision
  compilerReason
  compiledSourceObjectId
  compiledRole
  finalReplayDecision
  cleanupDecision
  materializerDecision
  firstBlockingStage
  firstBlockingReason
```

Report-only invariants:

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
materializationChanged=false
sourceOwnershipChanged=false
materializerConsumesTrace=false
```

Validation:

```text
focused tests:
  cd backend
  uv run pytest tests/test_m29_perception_fate_trace.py tests/test_upload_preview_pipeline.py tests/test_upload_preview_batch_validation_script.py -q
  result: 20 passed

py_compile:
  python3 -m py_compile app/m29_perception_fate_trace/*.py app/upload_preview/pipeline.py app/upload_preview/stages.py app/upload_preview/paths.py scripts/run_upload_preview_batch_validation.py tests/test_m29_perception_fate_trace.py tests/test_upload_preview_pipeline.py tests/test_upload_preview_batch_validation_script.py
  result: passed

hard regression HTTP batch:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  ledger: backend/tmp/validation/upload_preview_batch_20260526_202159_745679_13323/upload_preview_batch_validation.json
  completedTaskCount: 1 / 1
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalPerceptionCandidateCount: 13
  totalCompiledSourceObjectCount: 4
  totalCompiledControlBackgroundCount: 3
  totalCompiledRasterIconCount: 1
  totalPerceptionFateTraceCount: 13
  totalPerceptionFateBlockedCount: 9
  totalVisibleOwnershipOverlapConflicts: 0
  averageDslVisualGateNormalizedMeanAbsError: 0.005637

first ten HTTP batch:
  ledger: backend/tmp/validation/upload_preview_batch_20260526_202250_581048_14288/upload_preview_batch_validation.json
  completedTaskCount: 10 / 10
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalPerceptionCandidateCount: 659
  totalCompiledSourceObjectCount: 69
  totalCompiledControlBackgroundCount: 60
  totalCompiledRasterIconCount: 9
  totalPerceptionFateTraceCount: 659
  totalPerceptionFateBlockedCount: 612
  totalVisibleOwnershipOverlapConflicts: 0
  averageDslVisualGateNormalizedMeanAbsError: 0.004795
```

Hard image trace sample:

```text
task: task_979ca273cf4e
trace summary:
  traceCount=13
  compiledCount=4
  materializedCount=4
  cleanupAuthorizedCount=4
  blockedCount=9
  firstBlockingStageCounts:
    none=4
    m29_perception_source_compiler=9
  firstBlockingReasonCounts:
    visible_replay_materialized=4
    insufficient_ownership_evidence=5
    duplicate_or_near_equal_existing_source_object=3
    content_region_too_large_for_control_background=1
```

Conclusion:

```text
Stage 11 does not improve visual output directly.
It closes the diagnostic gap for model-first perception so the next repair can target the correct owning layer.
On the hard image and first-ten gate set, remaining model-first blockers are now visible in m29_perception_source_compiler, not hidden behind M29.6/transparent/bridge fate reports.
```

### Stage 12: Complex Control Raster Crop Preservation

After Stage 11, the fate trace showed one hard-image model candidate still blocked by:

```text
content_region_too_large_for_control_background
```

An attempted fix that compiled this kind of tall/single-line control as a flat `shape_replay` increased selectable nodes but worsened visual fidelity by flattening complex/glowing button backgrounds.

First-principles owner:

```text
perception_source_compiler
M29.5 visible overlap suppression
ownership_conservation
```

Reason:

```text
Simple solid controls should replay as shape_geometry.
Complex/textured/glowing controls should replay as selectable foreground image crops.
The parent large media remains residual raster.
Materializer must still execute only final M29.5 plan items.
```

Fix:

```text
When a text-containing candidate is too tall for safe flat control shape replay,
but still passes generic control geometry evidence,
compile it as:
  visualKind = media_region
  pixelOwner = preserve_raster
  replayDecision = image_replay
  sourceEvidence.internalRole = internal_control_raster_background
  sourceEvidence.promotionSource = perception_model_foreground_claim

Allow this exact foreground crop relation to overlap its parent residual media in:
  M29.5 visible overlap suppression
  ownership conservation conflict analysis

Keep normal overlapping media duplicates suppressed.
```

Batch ledger enhancement:

```text
compiledControlImageCount
totalCompiledControlImageCount
```

This separates complex selectable control crops from flat `control_background` shape replay.

Validation:

```text
focused tests:
  cd backend
  python3 -m py_compile app/perception_source_compiler/*.py app/m29_replay_plan/*.py app/ownership_conservation/*.py scripts/run_upload_preview_batch_validation.py tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_upload_preview_batch_validation_script.py
  result: passed

  cd backend
  uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py tests/test_upload_preview_batch_validation_script.py -q
  result: 95 passed

hard regression HTTP batch:
  input: /Users/luhui/Downloads/m29/微信图片_20260524225318_199_118.png
  ledger: backend/tmp/validation/upload_preview_batch_20260526_204621_437550_33237/upload_preview_batch_validation.json
  completedTaskCount: 1 / 1
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  totalCompiledSourceObjectCount: 5
  totalCompiledControlBackgroundCount: 3
  totalCompiledControlImageCount: 1
  totalCompiledRasterIconCount: 1
  totalPerceptionFateTraceCount: 13
  totalPerceptionFateBlockedCount: 8
  totalMaterializedVisibleNodeCount: 35
  averageDslVisualGateNormalizedMeanAbsError: 0.005637
  maxDslVisualGateChangedPixelRatio10: 0.039108

hard regression trace:
  task: task_3884ad47f2ea
  perception_candidate_0001 -> m292_perception_control_image_0001
  compiledRole: media_region
  compiledReplayDecision: image_replay
  internalRole: internal_control_raster_background
  finalReplayDecision: image_replay
  materializerDecision: replayed
  firstBlockingStage: none

first ten HTTP batch:
  ledger: backend/tmp/validation/upload_preview_batch_20260526_204857_044541_35386/upload_preview_batch_validation.json
  completedTaskCount: 10 / 10
  missingArtifactCount: 0
  assetFetchFailedCount: 0
  totalVisibleOwnershipOverlapConflicts: 0
  totalPerceptionCandidateCount: 659
  totalCompiledSourceObjectCount: 72
  totalCompiledControlBackgroundCount: 60
  totalCompiledControlImageCount: 3
  totalCompiledRasterIconCount: 9
  totalPerceptionFateTraceCount: 659
  totalPerceptionFateBlockedCount: 609
  totalMaterializedVisibleNodeCount: 1617
  averageDslVisualGateNormalizedMeanAbsError: 0.004690
  maxDslVisualGateChangedPixelRatio10: 0.043956
```

Anti-specialization check:

```text
No production branch uses image filename, path, task id, brand, visible text, theme color, fixed coordinate, or fixed bbox.
The new allow path requires generic sourceEvidence:
  perception_model_foreground_claim
  internal_control_raster_background
  foregroundClaimId
  mediaSourceObjectId == parent sourceObjectId
```

Conclusion:

```text
This stage fixes a real model-first source-chain blocker without flattening complex controls into unsafe shapes.
It improves selectable control coverage through normal M29.2 -> M29.5 -> materializer flow.
Remaining blockers are still in perception_source_compiler and cleanup quality, not Renderer/plugin.
```

### Stage 13: Import/Test Inventory And Documentation Sync

Decision:

```text
Do not prune M29.6, transparent assets, evidence contract, internal source promotion, or bridge fate trace yet.
```

Reason:

```text
backend/app/upload_preview/pipeline.py still runs the M29.6 compatibility chain:
  M29.6 media internal decomposition
  -> transparent asset report
  -> evidence contract report
  -> internal source promotion
  -> final promoted M29.3/M29.4/M29.5 reports
  -> bridge fate trace

backend/app/upload_preview/pipeline.py also runs the model-first chain:
  perception model report
  -> perception source compiler
  -> final M29.3/M29.4/M29.5
  -> perception fate trace
```

Inventory evidence:

```text
backend/app/upload_preview/stages.py imports wrappers for both the compatibility M29.6 chain and model-first perception chain.
backend/tests/test_upload_preview_pipeline.py still asserts default M29.6 artifacts exist.
historical note: Stage 13 tests still asserted opt-in behavior; Stage 15 replaces this with default-on and explicit-disable tests.
```

Boundary update:

```text
AGENTS.md
docs/engineering/current-mainline-code-map.md
docs/engineering/testing-strategy.md
docs/engineering/m29-contract-regression-matrix.md
```

Acceptance:

- No runtime path is deleted in this stage.
- Default upload behavior remains compatible with existing M29.6 artifacts.
- Model-first perception is documented as default-on and report/source-compiler bounded after Stage 15.
- `internal_source_promotion` is documented as the compatibility bridge for the old M29.6 evidence chain, not the model-first bridge.
- Legacy ONNX proposer remains forbidden and is not confused with the current opt-in perception model report.

Validation:

```bash
git diff --check
cd backend
uv run pytest tests/test_upload_preview_pipeline.py tests/test_config_env.py tests/test_upload_preview_batch_validation_script.py -q
```

### Stage 14: Complex Control Child Icon Ownership

Problem:

```text
Complex controls that are unsafe as flat shapes can replay as selectable foreground image crops.
Low-score child icons inside those control crops were still treated as report-only, because the compiler only recognized shape controls as parent controls.
After compiler support was added, M29.5 could still suppress the child icon as a duplicate when a compatibility M29.6 promoted icon existed, or treat icon-over-control-crop as ordinary image/icon overlap.
```

Fix:

```text
perception_source_compiler:
  Treat proven `internal_control_raster_background` image crops as parent controls for contained child icon candidates.

M29.5 replay plan:
  Prefer the model-first child icon over a near-equal compatibility M29.6 promoted icon when the compatibility icon's parent is the model-first control crop.
  Keep icon replay over its parent control crop instead of visible-overlap suppressing it.
  Authorize copied-image cleanup for both nested residual owners:
    parentControlSourceObjectId
    mediaSourceObjectId

ownership_conservation:
  Treat icon-over-parent-control-crop overlap and nested copied-image cleanup as explainable only when `parentControlSourceObjectId` / `mediaSourceObjectId` evidence is present.
```

Guardrails:

```text
No model candidate bypasses M29.2/M29.5.
No materializer, Renderer, or plugin creates ownership.
No filename, task id, visible text, brand, theme, fixed coordinate, or fixed bbox rule.
Ordinary overlapping media duplicates remain suppressible.
```

Validation:

```bash
cd backend
python3 -m py_compile app/perception_source_compiler/*.py app/m29_replay_plan/*.py app/ownership_conservation/*.py tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py

uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py -q
```

Result:

```text
90 passed.
```

Hard image validation:

```text
ledger: backend/tmp/validation/upload_preview_batch_20260526_211751_165704_57016/upload_preview_batch_validation.json
completedTaskCount: 1 / 1
totalVisibleOwnershipOverlapConflicts: 0
totalCompiledSourceObjectCount: 6
totalCompiledControlImageCount: 1
totalCompiledRasterIconCount: 2
totalPerceptionFateTraceCount: 13
totalPerceptionFateBlockedCount: 7
totalPlannedIconReplayCount: 9
totalCopiedImageAssetInternalErasedCount: 3
totalMaterializedVisibleNodeCount: 36
averageDslVisualGateNormalizedMeanAbsError: 0.005637
maxDslVisualGateChangedPixelRatio10: 0.039108
```

Trace proof:

```text
perception_candidate_0007
-> m292_perception_icon_0001
compiledRole: raster_icon
internalRole: internal_icon_candidate
parentControlSourceObjectId: m292_perception_control_image_0001
finalReplayDecision: icon_replay
materializerDecision: replayed
firstBlockingStage: none
```

First-ten validation:

```text
ledger: backend/tmp/validation/upload_preview_batch_20260526_211847_110907_58063/upload_preview_batch_validation.json
completedTaskCount: 10 / 10
missingArtifactCount: 0
assetFetchFailedCount: 0
totalVisibleOwnershipOverlapConflicts: 0
totalPerceptionCandidateCount: 659
totalCompiledSourceObjectCount: 72
totalCompiledControlBackgroundCount: 60
totalCompiledControlImageCount: 3
totalCompiledRasterIconCount: 9
totalPerceptionFateTraceCount: 659
totalPerceptionFateBlockedCount: 609
totalMaterializedVisibleNodeCount: 1617
averageDslVisualGateNormalizedMeanAbsError: 0.004690
maxDslVisualGateChangedPixelRatio10: 0.043956
```

Conclusion:

```text
This closes a real model-first nested ownership gap for complex selectable controls.
It does not solve missing model proposals such as a model that never emits an independent icon bbox.
The next repair should inspect remaining high-value perception fate blockers before widening compiler gates.
```

### Stage 15: Default Model-First Runtime

Problem:

```text
The model-first chain existed, but normal backend starts still used the old rule-first path unless the caller remembered M29_PERCEPTION_MODEL_ENABLED=true plus uv --with onnxruntime.
That made live manual upload tests misleading and kept pushing repairs back toward hand-written visual recognition.
```

Change:

```text
M29_PERCEPTION_MODEL_ENABLED defaults to true.
M29_PERCEPTION_MODEL_PATH defaults to /Volumes/WorkDrive/Models/model_fp16.onnx.
onnxruntime is now a backend dependency instead of a temporary uv --with package.
batch validation defaults to model-first and provides --disable-perception-model only for compatibility isolation.
unit tests explicitly disable the model unless the test is asserting default model-first behavior with a fake extractor.
```

Boundary:

```text
The model report is still proposal evidence only.
The compiler is still the only bridge into M29.2 ownership.
M29.5 is still the only visible replay and cleanup authority.
The legacy M39/ONNX proposer remains deleted and forbidden.
```

Validation:

```bash
cd backend
uv run pytest tests/test_config_env.py tests/test_upload_preview_pipeline.py tests/test_upload_preview_batch_validation_script.py tests/test_perception_model_report.py -q
```

### Stage 16: Inferred Leading Icon Inside Proven Controls

Problem:

```text
The default model-first path can emit a whole button/control bbox without an independent icon bbox.
In the hard login sample, the Google control compiled as `control_background`, but the model's small child candidate was the text span, not the leading logo.
The compiler therefore needed a bounded fallback for the common UI relation: icon on the left, OCR text on the right, both inside a proven control.
```

Change:

```text
For an already compiled OCR-containing control, the compiler searches only the local region left of the leftmost contained OCR box.
It extracts a compact high-contrast foreground cluster from source pixels and emits a derived `raster_icon` source object when geometry, contrast, fill, aspect, containment, and text-overlap checks pass.
Existing child model candidates suppress this inference only when they are real left-of-text icon candidates, not when they overlap the OCR text.
Perception fate trace now includes derived compiled source objects, so a derived icon has its own trace through M29.5 and materialization.
```

Boundary:

```text
No text, brand, filename, task id, fixed coordinate, fixed bbox, or theme-color rule.
The model candidate still creates only M29.2 source ownership through `perception_source_compiler`.
M29.5 remains the only visible replay and copied-media cleanup authority.
The fate trace remains read-only diagnostics.
```

Validation:

```bash
cd backend
uv run pytest tests/test_m29_perception_fate_trace.py tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py -q
```

Hard sample validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir tmp/default_model_hard_input \
  --poll-timeout 300 \
  --startup-timeout 60
```

Observed hard-sample evidence:

```text
ledger: backend/tmp/validation/upload_preview_batch_20260526_222146_462248_4999/upload_preview_batch_validation.json
task: task_d79c5ff2386f
compiledSourceObjectCount: 8
compiledRasterIconCount: 4
perceptionFateTraceCount: 15
visibleOwnershipOverlapConflicts: 0
derived Google control icon:
  perception_candidate_0005:leading_icon
  -> m292_perception_icon_0002
  -> bbox [134, 1024, 90, 77]
  -> finalReplayDecision icon_replay
  -> materializerDecision replayed
```

## Validation Commands

Probe validation:

```bash
cd backend
uv run python scripts/probe_onnx_model.py \
  --model /Volumes/WorkDrive/Models/model_fp16.onnx \
  --input /Users/luhui/Downloads/m29 \
  --output-dir tmp/model_probe_m29 \
  --input-size 960 \
  --score-threshold 0.05 \
  --top-k 80
```

Focused tests as stages land:

```bash
cd backend
uv run pytest \
  tests/test_perception_model_report.py \
  tests/test_perception_source_compiler.py \
  tests/test_source_ui_physical_graph.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_upload_preview_pipeline.py \
  -q
```

Batch validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300
```

Static closeout:

```bash
git diff --check
git status --short --branch
```

## Stage-Gated Execution Rules

- Each stage gets a separate commit.
- Each commit must state whether it is report-only, compatibility isolation, or runtime mainline.
- Model-first runtime is now the default; use `M29_PERCEPTION_MODEL_ENABLED=false` only to isolate compatibility regressions.
- Do not treat single-image success as final acceptance.
- Do not hide regressions by lowering thresholds for one sample.
- When a stage fails, inspect the relevant artifact first: perception report, compiler report, M29.5 replay plan, materialization report, bridge/model fate trace.
- If a fix tempts changes in materializer/Renderer/plugin to compensate for missing source ownership, stop and re-run first-principles gate.

## Risks

- The ONNX model is single-class. It cannot tell button/icon/text/card roles by itself.
- OCR still decides text content; model boxes alone cannot produce editable text.
- Source-crop icon replay may be visually useful but less clean than transparent alpha assets.
- `onnxruntime` increases backend dependency size, but is accepted for the default local model-first runtime.
- Model candidates may over-detect text/link blocks; compiler must prefer safe source ownership over node explosion.

## Notes

This plan supersedes the direction of continuing to harden M29.6 as a visual recognizer. Existing 065 residual ownership work remains useful as compiler/materializer safety logic, but model-first perception changes where foreground claims originate.
