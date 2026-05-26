# 067 M29 Model-First Perception Implementation

- 状态：active
- 创建日期：2026-05-27
- 负责人：Codex

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

Add an opt-in pipeline stage:

```text
perception_model_report
```

Gate it behind settings/env:

```text
M29_PERCEPTION_MODEL_ENABLED=true
M29_PERCEPTION_MODEL_PATH=/Volumes/WorkDrive/Models/model_fp16.onnx
```

Default must remain off until dependency and batch evidence are stable.

Acceptance:

- With env enabled, `/api/upload-preview` writes `m29_perception_model/perception_model_report.json`.
- With env disabled, current pipeline output remains unchanged.
- No DSL/materialization changes in this stage.
- Batch run on `/Users/luhui/Downloads/m29` completes with report artifacts.

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

### Stage 4: Replace M29.6 Primary Candidate Flow

Change upload-preview ordering under the opt-in flag:

```text
perception_model_report
-> perception_source_compiler
-> M29.3/M29.4/M29.5 final chain
```

M29.6 remains available as fallback/debug but no longer owns primary visual discovery when model-first mode is on.

Acceptance:

- The old M29.6 -> transparent -> evidence -> promotion loop is not required for model-proposed button/icon/control source objects.
- Bridge/model fate trace can explain model candidate -> source ownership -> replay/materializer outcome.
- Hard regression image shows Google/Facebook/Snapchat button backgrounds and icons have a source path before materialization.

### Stage 5: Asset And Residual Cleanup

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

### Stage 6: Real Sample Batch And Figma-Facing Inspection

Run:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300
```

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

### Stage 7: Legacy Pruning Plan

Only after Stage 6 shows stable improvement:

- Move M29.6-only heuristics toward fallback/dead-path status.
- Update `docs/engineering/current-mainline-code-map.md`.
- Update `docs/engineering/testing-strategy.md`.
- Update `docs/engineering/m29-contract-regression-matrix.md`.
- Archive or delete old audit packages only with import/test inventory.

Acceptance:

- No old path is deleted without import and test evidence.
- Mainline docs show model-first perception as primary path.
- Historical rule-based modules are clearly fallback or archived.

## Validation Commands

Probe validation:

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
- Each commit must state whether it is report-only, runtime opt-in, or runtime mainline.
- Do not enable model-first runtime by default until report-only and compiler tests pass.
- Do not treat single-image success as final acceptance.
- Do not hide regressions by lowering thresholds for one sample.
- When a stage fails, inspect the relevant artifact first: perception report, compiler report, M29.5 replay plan, materialization report, bridge/model fate trace.
- If a fix tempts changes in materializer/Renderer/plugin to compensate for missing source ownership, stop and re-run first-principles gate.

## Risks

- The ONNX model is single-class. It cannot tell button/icon/text/card roles by itself.
- OCR still decides text content; model boxes alone cannot produce editable text.
- Source-crop icon replay may be visually useful but less clean than transparent alpha assets.
- Adding `onnxruntime` as a backend dependency may affect deploy size/startup; keep it opt-in until proven.
- Model candidates may over-detect text/link blocks; compiler must prefer safe source ownership over node explosion.

## Notes

This plan supersedes the direction of continuing to harden M29.6 as a visual recognizer. Existing 065 residual ownership work remains useful as compiler/materializer safety logic, but model-first perception changes where foreground claims originate.
