# 066 M29 Model-First Perception Pivot

## Status

Superseded planning and exploration target. The implemented runtime contract is now captured by `docs/plans/completed/068-m29-model-first-mainline-destructive-refactor.md`, current code map, and later completed regression plans.

The current `main` branch still runs the deterministic M29 source chain. The latest committed direction up to plan 065 improved composite media handling by adding residual media ownership, foreground claim evidence, internal promotion, and cleanup authorization. A final narrow rule-based patch was also kept on `main`: text-contained control backgrounds inside composite media can now become inferred M29.6 foreground claims when the raw primitive graph misses the button background.

That patch is useful as a fallback, but it also exposed the architectural limit: M29.6 is becoming a hand-written visual model. Continuing to add geometry, anchor, edge, threshold, and promotion rules will keep producing local improvements while increasing maintenance cost and regression risk.

## First-Principles Judgment

The real product goal is not to prove every candidate through hand-authored evidence math. The real goal is:

```text
source screenshot -> editable, selectable, visually faithful Figma layers
```

The current M29 chain tries to infer too much semantic perception from deterministic geometry:

```text
pixels
-> connected components
-> hand-written geometry roles
-> evidence score
-> promotion
-> replay
-> cleanup
```

This path is explainable, but it is a poor fit for open-ended visual perception. New screenshots keep creating valid UI objects whose pixel form does not match existing thresholds. Each repair adds more code to what is effectively a manually coded classifier.

The preferred next direction is:

```text
pixels
-> model perception candidates
-> M29 ownership compiler
-> replay plan
-> materializer
-> render-back validation
```

In this direction, the model owns "what is visible here?" and M29 owns "which candidates are safe to compile into editable Figma layers?"

## Current Runtime State

Current mainline remains:

```text
Figma Plugin
-> POST /api/upload-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29.6 media internal decomposition
-> transparent asset report
-> evidence contract
-> internal source promotion
-> final M29.3/M29.4/M29.5
-> plan-driven materializer
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma
```

The current M29.6 deterministic fallback can now propose:

```text
inferred_shape / text_support_background / internal_pill_button
```

when an OCR text box is contained by a stable local support region. This helped the login-button sample, but it should be treated as a fallback capability, not the future primary perception strategy.

## Model Candidate

Local model file provided for exploration:

```text
/Volumes/WorkDrive/Models/model_fp16.onnx
```

Observed from filesystem only:

```text
size: about 5.8 MB
format: ONNX-like binary file
```

Historical context before 067/068: at the time of this plan, the backend environment did not have `onnx` installed, and active runtime did not include ONNX inference. This is no longer the current runtime fact; use `docs/plans/completed/068-m29-model-first-mainline-destructive-refactor.md` and the current code map for implemented model-first behavior.

The original probe questions were:

```text
input tensor names and shapes
output tensor names and shapes
opset
metadata / labels
preprocessing requirements
whether output is bbox, mask, class logits, embedding, or something else
runtime dependency needed for inference
```

Do not add `onnxruntime` or other inference dependencies to `main` until the model probe proves the output is useful for UI perception.

## Proposed New Contract

Introduce an internal perception adapter. It should be isolated from M29 at first:

```text
source PNG
-> perception provider
-> normalized perception candidates
```

Candidate shape:

```text
candidateId
sourceProvider
classLabel
roleHint
bbox
mask optional
score
rawOutputRef
```

M29 then consumes candidates as one evidence source:

```text
perception candidate
+ OCR
+ existing primitive evidence
-> M29.2 source object candidate
-> M29.5 replay / cleanup authorization
```

M29 must not directly trust the model for cleanup. Cleanup still needs replacement ownership and local visual risk checks.

## What To Stop Doing

Do not continue expanding M29.6 as the primary visual recognizer.

Avoid adding more one-off gates such as:

```text
new fixed coordinate windows
brand/text-specific labels
theme-color rules
sample path rules
more score weights for a single screenshot
materializer semantic guessing
Renderer/plugin repair patches
```

Bridge fate remains diagnostic only. It should explain where a candidate failed; it must not become a decision source.

## Exploration Stages

### Stage 1: ONNX Probe

Create a separate branch and inspect `/Volumes/WorkDrive/Models/model_fp16.onnx`.

Allowed outputs:

```text
backend/scripts/probe_onnx_model.py
docs/plans/archive/superseded/066 artifacts or notes
small JSON probe result under a non-storage docs/artifact path if needed
```

Do not modify upload-preview runtime in this stage.

Acceptance:

```text
model input/output shapes are known
dependency requirement is known
one dry inference path is understood or blocked with concrete error
```

Current probe script:

```text
backend/scripts/probe_onnx_model.py
```

Run it without adding runtime dependencies:

```bash
cd backend
uv run --with onnxruntime --with pillow --with numpy python scripts/probe_onnx_model.py \
  --model /Volumes/WorkDrive/Models/model_fp16.onnx \
  --input /Users/luhui/Downloads/525测试 \
  --output-dir tmp/model_probe_script_525 \
  --input-size 960 \
  --max-files 3
```

Observed model facts from the probe:

```text
input: images [batch, 3, height, width] tensor(float)
output: output0 [batch, 5, anchors] tensor(float)
decode: YOLO-like single-class [x, y, w, h, objectness]
role labels: none
```

Interpretation:

```text
The model is useful as a model-first UI object proposal source.
It is not a complete design reconstruction model because it has no class labels, hierarchy, text semantics, or cleanup authority.
M29 should consume its boxes as perception candidates, then use OCR and ownership/replay contracts to compile editable Figma nodes.
```

### Stage 2: Perception Adapter Prototype

If the model outputs useful UI candidates, create a report-only adapter:

```text
backend/app/perception_model_report/
```

It should write an internal report only. No DSL changes, no materializer changes.

Acceptance:

```text
report exists
normalized candidates are visible
no source ownership changes
no upload-preview behavior changes unless explicitly enabled
```

### Stage 3: M29 Consumer Contract

Only after Stage 2 proves useful, add a controlled bridge:

```text
perception_model_report -> M29.2 candidate source objects
```

This should replace broad M29.6 heuristic growth, not add another parallel decision maze.

Acceptance:

```text
model candidates can become M29 source objects through a small contract
M29.5 remains replay/cleanup authority
materializer remains an executor
```

## Validation

Initial probe validation:

```bash
git diff --check
git status --short --branch
```

If a report-only adapter is added:

```bash
cd backend
uv run pytest tests/test_perception_model_report.py -q
```

If upload-preview integration is later enabled:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/测试/images \
  --poll-timeout 300
```

Do not use a single sample as final acceptance.

## Decision Boundary

This plan is allowed to introduce a model-first perception branch.

It is not allowed to:

```text
change public DSL schema
change Figma plugin protocol
replace Renderer
make bridge fate a decision source
commit model binaries into the repo
add inference dependencies to main before probe evidence
```
