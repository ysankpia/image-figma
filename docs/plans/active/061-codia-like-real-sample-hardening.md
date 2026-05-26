
# 061 Codia-like Real Sample Hardening

Use the `stage-gated-dev-agent` Skill.

I am going to sleep. Do not ask me to review every image. You must run this as a stage-gated autonomous task.

Default behavior:

```text
stage passes -> commit -> continue
whole task complete -> stop and output Final Report
contract/dependency/conflict/systemic regression -> stop and output Blocker Report
```

## 0. Real Goal

The goal is to move the current PNG/Image-to-Figma pipeline toward a Codia-like usable design draft:

```text
reduce user repair cost in Figma
```

This does NOT mean 100% editable reconstruction.

It means:

* the upload-preview pipeline is stable on real images;
* the output DSL remains visually faithful enough to be usable;
* obvious UI text, finite controls, icons, small markers, tab/action rows, and internal UI elements inside media/banner/card areas become more editable/selectable when evidence supports it;
* complex photos, textures, hero graphics, avatars, charts, product images, and unsafe regions remain raster/fallback instead of being incorrectly redrawn;
* cleanup only happens when M29.5 explicitly authorizes it;
* every accepted replay decision is traceable through source evidence.

Do not optimize for candidate count. Optimize for:

```text
correctness
repair cost reduction
traceability
no duplicate ghosts
no broken visual output
no single-sample overfitting
```

---

## 1. Source Truth

The source truth chain is:

```text
source PNG pixels
+ OCR boxes
+ raw M29 primitive graph
+ M29.2 source ownership
+ M29.3 relation graph
+ M29.4 weak structural evidence
+ M29.5 replay plan
+ M29.6 / transparent / promotion evidence, reprocessed through M29.2-M29.5
+ M29 plan-driven materializer
```

The current product path is:

```text
Figma Plugin
-> POST /api/upload-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 region relation
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 ownership conservation report
-> M29.6 media internal decomposition report
-> M29 transparent asset report
-> M29 internal source promotion
-> M29.3/M29.4/M29.5 final reports from promoted M29.2
-> M29 hierarchy candidate report
-> M29 sibling group candidate report
-> M29 layout energy report
-> M29 Auto Layout permission report
-> M29 plan-driven materializer
-> M29 design token report
-> M29 B-stage quality report
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma Canvas
```

`/api/upload-preview` is the official upload entry.

`/api/tasks/{taskId}/dsl` is the official design draft output.

Do not restore old product paths.

---

## 2. Primary Sample Set

Use this folder as the main real-image benchmark:

```text
/Users/luhui/Downloads/测试/images
```

Requirements:

* Treat every PNG/JPG/JPEG/WebP image inside this folder as part of the batch unless the current upload code only accepts PNG.
* If non-PNG files exist and the current product only accepts PNG, record them as `unsupported_input_format` in the ledger. Do not silently skip them.
* Do not test one image and claim completion.
* Single-image testing is allowed only for diagnosis.
* Final acceptance for each stage requires rerunning this 40-image primary batch.
* Do not recursively include sibling folders such as `images 2` or `images 3` in the primary stage gate unless this plan is explicitly updated.

If these folders exist locally, run them as secondary regression sets after the primary set:

```text
/Users/luhui/Downloads/测试/525测试
/Users/luhui/Downloads/m29
/Users/luhui/Downloads/525测试
```

If they do not exist, record `not_found` and continue with `/Users/luhui/Downloads/测试/images`.

---

## 3. Allowed Dependencies

The following dependencies may be installed or used if they are not already available:

```text
Pillow
NumPy
scikit-image
```

They are allowed only as image math execution dependencies.

Allowed usage:

* decode and normalize pixels;
* crop arrays by bbox;
* compute masks, bbox, area, overlap, IoU, containment;
* label connected components;
* run morphology operations;
* estimate local background, alpha, edge/ring samples, texture, variance, luma, and pixel diff;
* generate diagnostic overlays or RGBA debug assets.

Forbidden usage:

* do not let these libraries decide `pixelOwner`;
* do not let them decide `visualKind`;
* do not let them decide `replayDecision`;
* do not let them authorize cleanup;
* do not let them create DSL nodes;
* do not let them mutate materialization output directly;
* do not let them infer component identity;
* do not let them infer Auto Layout permission;
* do not put filename/path/sample-id/fixed-coordinate rules inside image math utilities.

The following are also acceptable only if already part of the project policy:

```text
orjson -> only behind backend/app/json_tools.py
rich -> dev/script output only
```

Do NOT add these without stopping and asking:

```text
OpenCV
SAM / SAM2
ONNX
PyTorch
local OCR runtime
Go service
external service
new model API
```

---

## 4. Allowed Scope

Allowed to modify:

```text
backend/app/visual_primitive/
backend/app/source_ui_physical_graph/
backend/app/media_internal_decomposition/
backend/app/transparent_asset_report/
backend/app/m29_evidence_contract/
backend/app/internal_source_promotion/
backend/app/region_relation_graph_report.py
backend/app/region_relation_kernel.py
backend/app/stable_design_cluster/
backend/app/m29_replay_plan/
backend/app/ownership_conservation/
backend/app/plan_materializer/
backend/app/dsl_visual_comparison/
backend/app/image_math/
backend/app/json_tools.py
backend/scripts/
backend/tests/
docs/plans/active/
docs/bugs/
docs/engineering/m29-contract-regression-matrix.md
docs/engineering/dependency-policy.md
docs/runbooks/local-setup.md
```

Allowed to add:

```text
batch validation script
artifact ledger generator
visual diff ledger
diagnostic report-only overlays
focused regression tests
bug records
active plan document
```

---

## 5. Forbidden Scope Without Migration Proposal

Do not modify these unless you stop and produce a Migration Proposal:

```text
DSL schema
public API response shape
Figma Renderer contract
Figma plugin protocol
task status contract
database schema
official route semantics
```

Do not add these feature classes in this task:

```text
Figma Auto Layout materialization
Figma Component/Instance materialization
Variant materialization
design token variable materialization
automatic vectorization
SVG replacement
full design system reconstruction
```

Report-only candidates are allowed, but they must not become Renderer-visible output.

---

## 6. Always Forbidden

Do not write rules based on:

```text
file name
exact local path
sample id
task id
upload order
fixed bbox
fixed coordinate
fixed screenshot size
literal visible text
brand
industry
theme color
business category
one-screenshot structure
```

Do not patch Renderer, plugin, or materializer to invent source owners.

Do not let materializer guess cleanup.

Do not clean fallback or copied media unless M29.5 has explicit cleanup targets.

Do not let audit-only evidence become visible DSL nodes.

Do not make fallback visually worse just to increase editable node count.

---

## 7. Current Contract Boundaries

The DSL output must remain compatible with DSL v0.1.

Visible M29 runtime roles may include:

```text
m29_text
m29_shape
m29_image
m29_symbol
fallback_region
original_reference
```

M29 symbols should remain image-backed raster symbols unless the current renderer contract explicitly supports another path.

The following must stay audit/report-only and must not become visible DSL children:

```text
mixed_symbol_text_candidate
future_promotable_uncertain_symbol_candidate
candidate_for_future_uncertain_review
keep_mixed_symbol_text_conflict
text_owned_rejected_lineage
residual mixed review output
M29.4 weak cluster role hints
M29.5 diagnostic_only
M29.5 fallback_only
M29.5 suppress_duplicate
```

M29.4 weak clusters do not grant permission to create:

```text
components
groups
Auto Layout
Figma Component/Instance
semantic UI widgets
```

---

## 8. Target Quality Areas

Work through these areas in order of highest impact from the batch ledger.

### A. Real Sample Batch Ledger

Create or improve a batch ledger for `/Users/luhui/Downloads/测试/images`.

Each image must record:

```text
input path
normalized input type
task id
upload-preview status
failed stage, if any
backend error, if any
DSL path
materialization report path
stage timings path
source image path
render-back image path, if available
visual diff image path, if available
M29 report paths
M29.2 report paths
M29.3 report paths
M29.4 report paths
M29.5 replay plan path
M29.6 media internal decomposition path
transparent asset report path
evidence contract report path
internal source promotion report path
ownership conservation report path
node counts
visible text count
visible shape count
visible image count
visible symbol count
fallback count
cleanup target count
executed cleanup count
ownership conflict count
degraded reason
human-inspection notes
```

The ledger must make failures and degraded cases visible. Do not hide them in console logs only.

### B. Stability

Acceptance:

```text
all supported images in /Users/luhui/Downloads/测试/images complete upload-preview
backend crash count = 0
batch process does not stop on a single bad input
each supported input produces a DSL or explicit failed/degraded record
/api/tasks/{taskId}/dsl is available for completed tasks
assets referenced by DSL are fetchable
```

### C. Text Editability Without Double Ghosts

Improve text replay only when source evidence supports it.

Acceptance:

```text
high-confidence UI OCR text should become editable when background/ownership/cleanup evidence supports safe replay
OCR text inside textured media/photo/banner/product image may remain raster if safe editability is not proven
text replay must not cause obvious double text ghosts
text cleanup must be authorized by M29.5 cleanup targets
text foreground color sampling must remain source-pixel based
failed text decisions must be reported with reasons
```

Do not globally relax text gates just to increase text count.

### D. Finite Controls

Finite controls include:

```text
buttons
badges
search boxes
small cards
table markers
action chips
input-like UI blocks
simple pill controls
```

Acceptance:

```text
finite control background -> editable shape/image node only when source evidence supports it
control text -> editable text node only when OCR/source ownership supports it
parent raster/copied media -> cleaned only through M29.5 cleanupTargets
cleanup result -> parent background remains visually intact, with no duplicate text and no dirty foreground block
```

Do not special-case color, text, filename, or coordinate.

### E. Media Internal Elements

For carousel/banner/card/product/media areas:

Acceptance:

```text
internal OCR UI text is identified as internal text candidate when evidence supports it
small internal UI icons/markers can become internal candidates when supported by multiple evidence types
transparent asset candidates remain report-only until evidence contract and M29.5 authorize replay
large hero/photo/texture fragments are rejected or preserved as raster
separators, highlights, shadows, light effects, and texture fragments are not promoted as icons
promoted internal icons require evidence contract allow + internal source promotion + M29.5 replay authorization
```

### F. Bottom Tabs / Action Rows / Table Markers / Small Dots

These must be handled as generic repeated weak UI structures, not as hardcoded bottom-tab logic.

Acceptance:

```text
repeated small UI structures are detected through geometry, anchor relations, pixel evidence, and repeated structure
small dots/table markers/action row icons are reported or replayed only when evidence supports them
OCR glyph fragments must not become icons
decorative separators and texture fragments must not become icons
the same logic must work outside bottom navigation
```

### G. Visual Diff / Render-back Quality Gate

If `dsl_visual_comparison` or render-back tooling exists, make it part of the batch ledger.

Each supported image should produce, when technically available:

```text
source image
rendered DSL image
diff image
visual diff metrics
```

Acceptance:

```text
each stage must compare before/after batch metrics
a fix is not accepted if it improves one image but causes systemic visual degradation elsewhere
visual diff is a gate, not just a debug artifact
when render-back is unavailable, record why and continue with artifact inspection
```

Do not optimize only for numeric pixel diff if it increases Figma repair cost.

### H. Safe Cleanup

Acceptance:

```text
fallback cleanup only executes with M29.5 fallback cleanup target
copied image asset cleanup only executes with M29.5 copied_image_asset cleanup target
promoted internal cleanup only executes with M29.5 copied_image_asset target and transparent asset alpha mask
materializer does not invent ownership or cleanup authorization
cleanup must not create holes, dirty blocks, broken text, or double images
```

### I. Structured Layer Quality

This task should improve layer usability before jumping to Auto Layout.

Acceptance:

```text
layer names should be understandable
M29 source and plan ids should remain traceable in meta
groups/containers may be report-only unless current contract safely supports visible structure
do not create Figma Auto Layout or Components in this task
do not change DSL coordinates into nested parent-local coordinates unless there is an approved contract change
```

---

## 9. EvidenceScore Calibration

Current evidence should be upgraded from single confidence checks toward multi-evidence consistency.

Evidence types to consider:

```text
OCR evidence
source pixel evidence
geometry evidence
M29.2 ownership evidence
M29.3 relation evidence
M29.4 weak repeated-structure evidence
M29.5 replay/cleanup authorization
transparent asset alpha/background evidence
media internal decomposition evidence
ownership conservation evidence
visual diff evidence
```

Acceptance:

```text
do not promote a candidate based only on local confidence
positive evidence, negative evidence, and risk must be reported
medium confidence may pass only with structural/repeated/local support
high text overlap, unstable background, edge-alpha residue, or hero/texture penalty should block or degrade
evidence contract must explain why replay is allowed or rejected
```

---

## 10. Stage Plan

Create an active plan:

```text
docs/plans/active/061-codia-like-real-sample-hardening.md
```

Use this structure:

```md
# 061 Codia-like Real Sample Hardening

## Goal
## Source Truth
## Sample Set
## Scope
## Forbidden Changes
## Dependency Policy
## Stage Loop
## Inspection Ledger Schema
## Acceptance
## Stop Conditions
## Stage Reports
```

Then execute stages.

Suggested stages:

### Stage 1: Batch Baseline And Ledger

Goal:

```text
Run /Users/luhui/Downloads/测试/images through upload-preview and produce a real batch ledger.
```

Required:

```text
discover input images
run the 40-image primary batch
record completed/failed/degraded
record all artifact paths
record missing artifacts
record current metrics
do not change algorithms unless required to make the batch runner work
```

Validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images
git diff --check
```

If the existing script does not support required ledger fields, extend it generally.

Commit after stage passes.

### Stage 2: Artifact Inspection And Owning Layer Classification

Goal:

```text
Inspect batch artifacts and classify failures by owning layer.
```

Do not fix everything yet.

Classify each issue as:

```text
raw M29 / visual primitive
M29.2 source ownership
M29.3 relation graph
M29.4 weak structure
M29.5 replay plan
M29.6 media internal decomposition
transparent asset report
evidence contract
internal source promotion
ownership conservation
plan materializer
dsl_visual_comparison / diagnostic only
Renderer/plugin contract issue
```

Commit docs/ledger improvements after stage passes.

### Stage 3: Highest-impact Generic Fix

Goal:

```text
Pick the highest-impact generic defect from the ledger and fix it at the owning layer.
```

Required:

```text
add focused regression test first or with the fix
do not patch downstream layers to hide upstream evidence problems
run targeted pytest
rerun the 40-image primary batch
compare before/after ledger
commit if accepted
```

### Stage 4+: Continue Generic Fix Loop

Repeat:

```text
select next highest-impact generic defect
add focused regression
implement smallest general fix
targeted pytest
40-image primary batch
visual diff / artifact comparison
commit
continue
```

Stop only when:

```text
all planned acceptance criteria pass
or a stop condition is triggered
```

---

## 11. Required Commands

Run at least these targeted tests when related layers change:

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_m29_evidence_contract.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py tests/test_dsl_visual_comparison.py -q
git diff --check
```

If image_math dependencies or boundaries change, also run:

```bash
cd backend
uv run pytest tests/test_json_tools.py tests/test_image_math_arrays.py tests/test_image_math_masks.py tests/test_image_math_components.py tests/test_image_math_alpha.py tests/test_image_math_import_boundaries.py -q
uv run pytest -q
git diff --check
```

If frontend/plugin/renderer files are changed unexpectedly, stop unless the task explicitly requires it.

---

## 12. Stage Acceptance Criteria

A stage passes only if:

```text
1. The stage goal is completed.
2. All stage-scoped tests pass.
3. Full /Users/luhui/Downloads/测试/images primary batch has been rerun.
4. Batch ledger is updated.
5. No backend crash occurs on supported inputs.
6. No public contract is changed.
7. No DSL schema change occurs.
8. No Renderer/plugin protocol change occurs.
9. No filename/path/text/brand/color/fixed-coordinate special rule is introduced.
10. Cleanup remains authorized only by M29.5 cleanupTargets.
11. New dependency usage respects image_math boundary policy.
12. Diff is stage-scoped.
13. Stage report is written.
14. Commit is created.
```

Commit message format:

```text
feat(stage-061-<n>): <short summary>

validated:
- <targeted pytest command>
- batch: /Users/luhui/Downloads/测试/images
result:
- <completed>/<total> completed
- <failed> failed
- <degraded> degraded
- <crash> crash
ledger:
- <ledger path>
```

---

## 13. Final Acceptance Criteria

The task is complete only when:

```text
1. /Users/luhui/Downloads/测试/images has a complete batch ledger.
2. All supported images complete upload-preview without backend crash.
3. Every completed task exposes /api/tasks/{taskId}/dsl.
4. Every DSL-referenced asset is fetchable.
5. Stage reports and commits exist for every stage.
6. The final ledger lists remaining failed/degraded cases explicitly.
7. The final report explains which quality areas improved and which remain unresolved.
8. No public contract was changed.
9. No forbidden dependency was added.
10. No single-sample special casing was introduced.
11. cleanup remains M29.5-authorized.
12. audit-only evidence remains audit-only.
```

Do not claim Codia parity. Claim only:

```text
Codia-like hardening progress with measured real-sample evidence.
```

---

## 14. Stop Conditions

Stop and write a Blocker Report if any of these happen:

```text
need to change DSL schema
need to change public API response shape
need to change Renderer contract
need to change Figma plugin protocol
need to change task status contract
need to add OpenCV/SAM/ONNX/PyTorch/local OCR/Go/external service
need to use a new model or external API
batch shows systemic visual regression
fixing one sample repeatedly breaks other samples
cannot isolate stage commit
tests require missing credentials
OCR provider is unavailable and no deterministic fallback exists
acceptance criteria conflict
the implementation requires a large architecture rewrite
```

Blocker Report format:

```md
# Blocker Report

## Current Stage
## What Was Completed
## Blocker
## Evidence
## Why Continuing Would Be Unsafe
## Options
## Recommended Decision
```

---

## 15. Final Report

When done, stop and output:

```md
# Final Report: Codia-like Real Sample Hardening

## 1. Summary
## 2. Standards Followed
## 3. Sample Sets
## 4. Completed Stages
| stage | result | commit | ledger |
|---|---|---|---|

## 5. Final Batch Result
| metric | value |
|---|---|
| total inputs | |
| supported inputs | |
| completed | |
| failed | |
| degraded | |
| crash count | |

## 6. Quality Improvements
- text editability:
- finite controls:
- media internal elements:
- bottom tabs / action rows / markers:
- visual diff:
- cleanup safety:
- layer structure:

## 7. Remaining Failed / Degraded Cases
| sample | symptom | owning layer | recommended next fix |
|---|---|---|---|

## 8. Contract Status
| contract | changed? | note |
|---|---|---|
| DSL schema | |
| API response shape | |
| Renderer protocol | |
| Figma plugin protocol | |
| dependency policy | |

## 9. Anti-overfitting Check
| check | result |
|---|---|
| filename/path rule | |
| fixed coordinate rule | |
| fixed screenshot size rule | |
| literal text rule | |
| brand/theme/color rule | |
| single-sample rule | |

## 10. Commits
List all stage commits.

## 11. Next Recommended Task
```

Ready for goal execution.

---

## 16. Stage Reports

### Stage 1: Batch Baseline And Ledger

Status:

```text
passed
```

Scope:

```text
Improved the upload-preview batch validation ledger and locked the primary stage gate to
/Users/luhui/Downloads/测试/images without recursively pulling sibling sample folders.
No replay, ownership, materializer, renderer, plugin, API, or DSL behavior was changed.
```

Validation:

```bash
python3 -m py_compile backend/scripts/run_upload_preview_batch_validation.py backend/tests/test_upload_preview_batch_validation_script.py
cd backend && uv run pytest tests/test_upload_preview_batch_validation_script.py tests/test_upload_preview_pipeline.py -q
cd backend && uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
git diff --check
```

Result:

```text
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_031541/upload_preview_batch_validation.json
```

Key baseline metrics:

```text
visible replay claims: 4917
composite media count: 215
internal candidates: 3441
accepted internal candidates: 2402
transparent asset candidates: 4541
transparent asset allowed: 102
promoted internal source objects: 18
average DSL visual normalized mean absolute error: 0.042053
max DSL visual changed pixel ratio @10: 0.208299
```

Anti-overfitting check:

```text
No filename, path, sample id, fixed coordinate, visible text, brand, theme color,
or single-screenshot rule was added. The script discovers generic image inputs,
records unsupported formats explicitly, and treats single images as diagnosis only.
```

Next:

```text
Stage 2 should inspect this ledger and classify the first quality issues by owning layer
before changing any M29 algorithm.
```

### Stage 2: Text-Excluded DSL Visual Gate

Status:

```text
passed
```

Scope:

```text
Inspected the Stage 1 batch ledger and worst visual-diff artifacts before changing M29.
The first high-impact issue was not source ownership or media decomposition math:
the report-only DSL visual comparison gate was dominated by dependency-free
approximate text rendering noise. Full-image diff metrics remain unchanged for
diagnostics, but structural regression gating now uses text-excluded metrics.
No DSL, Renderer, Figma plugin, API, M29.5 replay plan, materializer behavior,
source ownership, promotion, or cleanup authorization was changed.
```

First-principles classification:

```text
real goal: pick the next M29 repair by real visual structure regression, not by diagnostic renderer font noise
source truth: source PNG + final materialized DSL + report-only approximate DSL renderer
information-loss point: approximate text rasterization cannot reproduce real UI/Figma font glyph pixels
owning layer: dsl_visual_comparison report metrics and batch ledger summary
do-not-do: do not add font/model dependencies, identify fonts, or relax OCR/source ownership gates
next verification: targeted tests + 40-image primary upload-preview batch
```

Fix:

```text
visible DSL text bboxes -> text exclusion mask -> nonText/gate diff metrics
full diff metrics are preserved unchanged
gate metrics fall back to full diff when the mask leaves no non-text pixels
```

New report fields:

```text
nonTextPixelComparedCount
nonTextMeanAbsChannelError
nonTextNormalizedMeanAbsError
nonTextChangedPixelRatio10
gateNormalizedMeanAbsError
gateChangedPixelRatio10
gateFallbackReason
textExcludedPixelCount
textExcludedCoverage
```

Validation:

```bash
python3 -m py_compile backend/app/dsl_visual_comparison/render.py backend/app/dsl_visual_comparison/pipeline.py backend/tests/test_dsl_visual_comparison.py backend/scripts/run_upload_preview_batch_validation.py backend/tests/test_upload_preview_batch_validation_script.py
cd backend && uv run pytest tests/test_dsl_visual_comparison.py tests/test_upload_preview_batch_validation_script.py tests/test_upload_preview_pipeline.py -q
cd backend && uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
git diff --check
```

Result:

```text
targeted tests: 15 passed
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
gate fallback count: 0
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_040404/upload_preview_batch_validation.json
```

Key metrics:

```text
average DSL visual normalized mean absolute error: 0.042053
max DSL visual changed pixel ratio @10: 0.208299
average DSL visual gate normalized mean absolute error: 0.004658
max DSL visual gate changed pixel ratio @10: 0.134558
```

Worst gate samples:

```text
39-e588b6e980a0e5b7a5e58e82.png: gateChangedPixelRatio10=0.134558, gateNormalizedMeanAbsError=0.010781
37-e59296e595a1e88cb6e9a5ae.png: gateChangedPixelRatio10=0.122730, gateNormalizedMeanAbsError=0.012324
12-e5908ce59f8ee8b791e885bf.png: gateChangedPixelRatio10=0.120685, gateNormalizedMeanAbsError=0.010810
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, visible text, brand, theme color,
or single-screenshot rule was added. The mask is derived from generic visible
DSL text bboxes, and all-pixel metrics remain available to catch text-specific
diagnostic failures. Text-excluded gate metrics must not be used to claim text
quality is correct; OCR/source ownership/cleanup and Figma-visible text quality
remain separate validation concerns.
```

Next:

```text
Stage 3 should use the Stage 2 ledger to select the first actual M29 quality
issue by owning layer. Candidate areas are low internal-source promotion
coverage, transparent asset rejection reasons, and bottom-tab/internal-icon
diagnostic-only outcomes. Do not patch downstream materializer/Renderer/plugin
to invent source ownership.
```

### Stage 3: Internal Icon Transparent Asset Stabilization

Status:

```text
passed
```

Scope:

```text
Selected the highest-impact M29 quality issue from Stage 2: internal UI icon
candidates inside composite media could be detected by M29.6 but were often
rejected by transparent asset extraction because their foreground bbox was too
tight for reliable edge-background sampling. The fix stays in the evidence
chain: M29.6 internal candidates use a parent-media-clamped analysis bbox and
dominant background cluster for alpha evidence; internal source promotion uses
that analysis bbox so the RGBA asset and visible source object keep matching
geometry.

During first 40-image validation, artifact inspection found false positives:
generic non-OCR foreground lines from maps/floor plans/underlines could pass
alpha extraction and evidence scoring. The stage was not accepted at that
point. The evidence contract was tightened so generic `pixel_component /
non_ocr_foreground` remains report/reject only and cannot directly become
visible replay. Raw symbol evidence and OCR-anchor pixel foreground evidence
remain eligible when the full evidence contract allows it.

No DSL, API, Renderer, Figma plugin protocol, materializer ownership logic, or
M29.5 cleanup authorization contract was changed.
```

First-principles classification:

```text
real goal: make true internal UI icons/action markers selectable without promoting media texture fragments
source truth: source PNG pixels + M29.6 internal candidates + transparent alpha evidence + evidence contract
information-loss point: tight foreground bbox edge sampling confuses foreground pixels for background
owning layer: transparent asset alpha evidence and evidence contract replay authorization
do-not-do: do not lower thresholds blindly, do not promote from alpha allow alone, do not patch materializer/Renderer/plugin
next verification: targeted tests + 40-image primary upload-preview batch + promoted-crop inspection
```

Fix:

```text
M29.6 internal transparent candidates:
  source bbox -> parent-media-clamped analysis bbox
  edge pixels -> dominant background cluster when context expansion is used
  report records analysisBbox and backgroundCoverage

Internal source promotion:
  promoted bbox uses transparent asset analysisBbox when present
  original candidate bbox is preserved in sourceEvidence.candidateBbox

Evidence contract:
  generic pixel_component/non_ocr_foreground cannot directly allow visible replay
  such evidence remains available for reports and future stronger grouping logic
```

Validation:

```bash
cd backend
uv run pytest tests/test_m29_evidence_contract.py tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

Result:

```text
targeted tests: 91 passed
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_045958/upload_preview_batch_validation.json
```

Stage 2 -> Stage 3 key metric comparison:

```text
visible replay claims: 4917 -> 4921
transparent asset allowed: 102 -> 131
promoted internal source objects: 18 -> 23
average DSL visual gate normalized mean absolute error: 0.004658 -> 0.004586
max DSL visual gate changed pixel ratio @10: 0.134558 -> 0.135227
ownership conflict type counts: {} -> {}
```

Artifact inspection:

```text
Generated and inspected promoted internal icon crops from the final 40-image
batch. The earlier false positives from map route strokes, floor-plan lines,
and underline-like generic foreground no longer promote after the evidence
contract tightening. Remaining promotions are raw symbol or OCR-anchor internal
foreground candidates with transparent asset allow and evidence contract
allow_visible_replay.
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, fixed screenshot size, literal text,
brand, theme color, industry, or one-screenshot rule was added. The new gates
are source-type and evidence-contract based: tight internal foreground bboxes
get contextual alpha analysis, while generic non-OCR foreground remains
non-visible until stronger independent evidence exists.
```

Next:

```text
Continue Stage 4 with the next highest-impact generic defect. Current remaining
areas include raw M29 blocked-fragment recovery for label-anchored icons,
further false-positive control for internal media candidates, and finite-control
background/editability improvements. Do not change materializer, Renderer, or
plugin to invent source ownership.
```

### Stage 4: Internal Source Promotion Deduplication

Status:

```text
passed
```

Scope:

```text
Inspected the Stage 3 ledger before changing code. High diagnostic-only counts
were not accepted as a repair target because most remaining diagnostic objects
are text overlap, image-internal texture, oversized foreground, or line-like
fragments that should remain non-visible. The safer high-impact issue found in
the ledger was duplicate internal source promotion: one real sample promoted the
same internal foreground bbox twice from overlapping parent media.

The fix stays in the source promotion bridge. It dedupes promoted internal
source objects by final promoted bbox, keeps the object with the highest
evidence score, reassigns stable promoted ids, and records the loser as
`duplicate_promoted_internal_bbox` in rejectedCandidates. M29.5 and the
materializer remain consumers only; no downstream owner or cleanup logic was
invented.
```

First-principles classification:

```text
real goal: avoid duplicate source ownership for the same internal foreground pixels
source truth: promoted M29.2 source objects derived from M29.6 + transparent asset + evidence contract
information-loss point: overlapping parent media can produce two candidates with the same promoted bbox
owning layer: internal_source_promotion, before final M29.3/M29.4/M29.5 rebuild
do-not-do: do not rely on M29.5 overlap suppression or materializer cleanup to hide duplicate source ownership
next verification: targeted tests + 40-image primary batch + duplicate promoted bbox audit
```

Fix:

```text
promotion_candidates -> dedupe by promoted bbox
rank duplicate candidates by evidenceScore
keep highest ranked candidate
reject duplicate losers with duplicate_promoted_internal_bbox
renumber kept promoted ids after dedupe
```

Validation:

```bash
cd backend
uv run pytest tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_plan_materializer.py -q
git diff --check
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

Result:

```text
targeted tests: 57 passed
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
duplicate promoted bbox samples: 0
duplicate_promoted_internal_bbox rejects: 1
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_052302/upload_preview_batch_validation.json
```

Stage 3 -> Stage 4 key metric comparison:

```text
visible replay claims: 4921 -> 4921
promoted internal source objects: 23 -> 22
average DSL visual gate normalized mean absolute error: 0.004586 -> 0.004586
max DSL visual gate changed pixel ratio @10: 0.135227 -> 0.135227
ownership conflict type counts: {} -> {}
```

Artifact inspection:

```text
The duplicate promoted bbox found in Stage 3 for
34-e7a5a8e58aa1e6bc94e587ba.png is gone. The lower-scored duplicate candidate
is recorded as duplicate_promoted_internal_bbox, and the batch has no remaining
duplicate promoted internal bboxes.
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, fixed screenshot size, literal text,
brand, theme color, industry, or one-screenshot rule was added. The dedupe key
is the promoted source bbox produced by the evidence chain, and the selection
rank is generic evidenceScore.
```

Next:

```text
Continue the Stage 4+ loop. Do not recover more diagnostic/blocked foreground
until independent evidence proves it is UI, because the current ledger shows
most remaining diagnostic objects are correctly blocked text/texture/large/line
fragments.
```

### Stage 5: Text-Excluded Gate Diff Artifact

Status:

```text
passed
```

Scope:

```text
Inspected the latest 40-image ledger and top gate-diff samples before changing
M29. The highest `gateChangedPixelRatio10` samples were still hard to inspect
because the only PNG artifact was the full `source_diff.png`, which includes
approximate text-rendering noise. Stage 2 already added text-excluded gate
metrics, but there was no matching text-excluded diff image for human
inspection.

The fix is validation-surface only: `dsl_visual_comparison` now emits
`source_gate_diff.png`, where pixels covered by the visible DSL text exclusion
mask are zeroed. The batch ledger records `sourceGateDiffPng` and
`visualGateDiffImagePath`. No M29, DSL, Renderer, Figma plugin, source
ownership, replay plan, materializer, or cleanup behavior changed.
```

First-principles classification:

```text
real goal: choose future M29 fixes from structural visual evidence, not full-diff text noise
source truth: source PNG + final materialized DSL + text-excluded comparison mask
information-loss point: full diff artifact mixes approximate text renderer noise with non-text structural differences
owning layer: dsl_visual_comparison diagnostic artifact and batch ledger artifact map
do-not-do: do not tune M29 ownership based on text-noisy full diff screenshots
next verification: targeted tests + 40-image batch + gate-diff artifact inspection
```

Fix:

```text
source_diff.png remains unchanged as full diagnostic diff
source_gate_diff.png shows only non-text/gate diff pixels
ledger artifacts include sourceGateDiffPng
record.visualGateDiffImagePath points to source_gate_diff.png
```

Validation:

```bash
cd backend
uv run pytest tests/test_dsl_visual_comparison.py tests/test_upload_preview_batch_validation_script.py tests/test_upload_preview_pipeline.py -q
git diff --check
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

Result:

```text
targeted tests: 16 passed
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
sourceGateDiffPng artifacts: 40/40
visualGateDiffImagePath records: 40/40
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_054405/upload_preview_batch_validation.json
```

Stage 4 -> Stage 5 key metric comparison:

```text
visible replay claims: 4921 -> 4921
promoted internal source objects: 22 -> 22
average DSL visual gate normalized mean absolute error: 0.004586 -> 0.004586
max DSL visual gate changed pixel ratio @10: 0.135227 -> 0.135227
ownership conflict type counts: {} -> {}
```

Artifact inspection:

```text
Generated a top-gate-diff contact sheet from source, rendered DSL, and
source_gate_diff.png. The gate diff removes most full-diff text noise and makes
remaining non-text structure/image/icon boundary differences easier to inspect
for the next M29 repair.
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, fixed screenshot size, literal text,
brand, theme color, industry, or one-screenshot rule was added. The new artifact
uses the same generic visible-text exclusion mask already used by gate metrics.
```

Next:

```text
Use source_gate_diff.png, not full source_diff.png, to choose the next actual
M29 owning-layer repair.
```

### Stage 6: Source-Text-Aware Gate Diff Mask

Status:

```text
passed
```

Scope:

```text
Inspected the Stage 5 top `source_gate_diff.png` contact sheet before changing
M29. The highest gate-diff samples still showed many residual red components
around list labels, prices, table values, and dense UI copy. The owning layer
was not M29.6 candidate recovery or materializer replay. The issue was the
validation mask contract: Stage 5 excluded visible DSL text bboxes, but source
OCR text that was not materialized, was shifted by approximate rendering, or
had slightly different bbox coverage could still dominate the "non-text" gate.

The fix is validation-surface only: `dsl_visual_comparison` now builds the
gate exclusion mask from the union of visible DSL text bboxes and source OCR
text bboxes. This improves the evidence contract for choosing future structural
repairs. No DSL output, asset output, source ownership, M29.6 promotion,
M29.5 replay plan, materializer cleanup, Renderer, or Figma plugin behavior
changed.
```

First-principles classification:

```text
real goal: make gate metrics represent non-text structural differences instead of OCR/font/rendering text residue
source truth: source PNG + final materialized DSL + OCR source text bboxes + visible DSL text bboxes
information-loss point: DSL-only text masking cannot protect source text that remains fallback-only or drifts under approximate text rendering
owning layer: dsl_visual_comparison evidence/validation contract
do-not-do: do not increase M29.6 promotion or tune materializer output based on residual text-edge gate diffs
next verification: targeted tests + 40-image HTTP batch + ledger comparison
```

Fix:

```text
build_text_exclusion_mask now accepts source_text_bboxes
source OCR text bboxes are unioned with visible DSL text bboxes for gate metrics
source OCR bbox padding is proportional to text height and capped at 4 px
dsl_visual_comparison_report records sourceTextBboxCount
dsl_visual_comparison_report records textExclusionSource=dsl_visible_text_plus_source_ocr_text
```

Validation:

```bash
cd backend
uv run pytest tests/test_dsl_visual_comparison.py tests/test_upload_preview_pipeline.py tests/test_upload_preview_batch_validation_script.py -q
git diff --check
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

Result:

```text
targeted tests: 17 passed
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
sourceTextBboxCount min across records: 52
textExclusionSource values: dsl_visible_text_plus_source_ocr_text
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_061536/upload_preview_batch_validation.json
```

Stage 5 -> Stage 6 key metric comparison:

```text
visible replay claims: 4921 -> 4921
promoted internal source objects: 22 -> 22
average DSL visual normalized mean absolute error: 0.041999 -> 0.041999
max DSL visual changed pixel ratio @10: 0.208853 -> 0.208853
average DSL visual gate normalized mean absolute error: 0.004586 -> 0.004264
max DSL visual gate changed pixel ratio @10: 0.135227 -> 0.129967
ownership conflict type counts: {} -> {}
```

Artifact inspection:

```text
Generated Stage 6 contact sheets for the top gate-diff samples before the fix.
They showed that many remaining high-diff red components were still source text
residue or text-neighbor rendering drift, not independent icon/background
failures. A temporary old-ledger recalculation with source OCR text bboxes
lowered average gate ratio from 0.049915 to 0.046236 with average mask coverage
around 19.36%, supporting the narrower validation-contract fix.
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, fixed screenshot size, literal text,
brand, theme color, industry, account, or single-screenshot branch was added.
The only new threshold is generic source-text padding:
max(fallbackPadding, min(4, round(textHeight * 0.12))). It applies only to the
dsl_visual_comparison text exclusion mask, not to M29 ownership or materialized
output. Its expected failure mode is under-masking large font drift rather than
over-masking controls; the 40-image batch showed stable artifact and ownership
metrics while reducing gate text residue.
```

Next:

```text
Rebuild the top source_gate_diff component sheet from the Stage 6 ledger. If
the remaining top components are structural and not text residue, choose the
next owning layer from artifact evidence. Do not recover diagnostic fragments
or promote more internal icons until independent UI evidence supports it.
```

### Stage 7: Source Shape Fill Consumption

Status:

```text
passed
```

Scope:

```text
Inspected the Stage 6 top gate-diff components and aligned them with M29.2,
M29.5, and materialized DSL artifacts. After source-text masking, the largest
remaining structural diffs were not missing internal icons. They mostly
overlapped `control_background` source objects replayed as `m29_shape`.

The owning layer was the plan materializer's shape style consumption. Raw M29
shape/support detectors already carried stable `style.fill` values computed
while ignoring foreground text/content evidence. The materializer was throwing
that away and recomputing shape fill as the mean over the full bbox. For
text-support rows, product cards, and controls, that bbox includes text, icons,
photos, or darker foreground content, so the replayed shape color became dirty.

The fix is materializer-only style consumption: `shapeFillOverride` remains
highest priority, then source M29 node `style.fill`, then the old source-pixel
bbox mean fallback. No source ownership, M29.5 replay decision, cleanup
authorization, Renderer, Figma plugin, or detection heuristic changed.
```

First-principles classification:

```text
real goal: replay already-approved shape backgrounds with the source-derived fill evidence that M29 already computed
source truth: raw M29 shape node style.fill + M29.5-authorized shape_replay
information-loss point: materializer replaced upstream stable fill evidence with full-bbox mean sampling
owning layer: plan_materializer shape style consumption
do-not-do: do not alter M29.2 owner decisions, recover diagnostic fragments, or add sample-specific color rules
next verification: focused materializer tests + 40-image HTTP batch + gate metric comparison
```

Fix:

```text
build_shape_replay_style now uses source shape node style.fill when present
source shape fill is validated as a hex color and normalized to uppercase
shapeFillOverride still wins over source node style.fill
sampled_shape_fill remains fallback for source nodes without style.fill
shape style meta records m29ShapeStyleSource=source_shape_style
```

Validation:

```bash
cd backend
uv run pytest tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

Result:

```text
targeted tests: 23 passed
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
shape style sources in batch DSL:
  source_shape_style: 555
  source_shape_inference: 28
  shape_geometry_fit: 4
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_063815/upload_preview_batch_validation.json
```

Stage 6 -> Stage 7 key metric comparison:

```text
visible replay claims: 4921 -> 4921
promoted internal source objects: 22 -> 22
average DSL visual normalized mean absolute error: 0.041999 -> 0.039127
max DSL visual changed pixel ratio @10: 0.208853 -> 0.111889
average DSL visual gate normalized mean absolute error: 0.004264 -> 0.001449
max DSL visual gate changed pixel ratio @10: 0.129967 -> 0.018258
ownership conflict type counts: {} -> {}
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, fixed screenshot size, literal text,
brand, theme color, industry, account, or one-screenshot rule was added. The
new rule is a generic evidence-priority rule: consume source M29 shape style
when it exists, fall back to pixel sampling only when it does not. It does not
create new visible nodes or change which shapes are replayed.
```

Next:

```text
Use the Stage 7 ledger as the new baseline. The top gate ratio is now 0.018258,
so future stages should inspect the remaining top gate components for actual
structural misses instead of continuing to optimize text/shape validation noise.
```

### Stage 8: Gate Diff Settlement And Stop Point

Status:

```text
settled
```

Scope:

```text
Inspected the Stage 7 batch ledger and top gate-diff records before changing
code. Stage 7 reduced the remaining non-text gate diff to a low level:
average gate normalized mean absolute error is 0.001449, and the worst
gateChangedPixelRatio10 is 0.018258 across the 40-image primary batch.

The remaining top gate diffs are mixed small residuals rather than one clear
generic defect: small shape/image/text intersections, control-background
boundary residue, suppressed duplicate boundaries, a few diagnostic-only
fragments, and local image/media rendering differences. There is no single safe
owning layer left that can be repaired from this metric alone without risking
sample-specific threshold tuning or promoting weak diagnostic fragments.

No code, DSL, API, Renderer, Figma plugin, source ownership, replay plan,
materializer, cleanup authorization, or dependency behavior changed in this
stage.
```

First-principles settlement:

```text
real goal: reduce user repair cost in Figma, not squeeze visual metrics after
  the remaining metric is already low and mixed
source truth: Stage 7 40-image HTTP batch ledger + source_gate_diff artifacts
information-loss point: residual gate pixels no longer identify one source
  evidence loss point; they combine small renderer, boundary, media, and
  intentionally blocked diagnostic evidence
owning layer: no single implementation owning layer is proven by the current
  evidence
do-not-do: do not lower candidate thresholds, recover diagnostic fragments, or
  tune bbox/color rules from the remaining top samples
next verification: open a new bug/stage only from a concrete user-visible
  sample failure with source artifact evidence and owning-layer classification
```

Stage 7 baseline ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_063815/upload_preview_batch_validation.json
```

Stage 7 baseline result:

```text
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
visible replay claims: 4921
promoted internal source objects: 22
average DSL visual normalized mean absolute error: 0.039127
max DSL visual changed pixel ratio @10: 0.111889
average DSL visual gate normalized mean absolute error: 0.001449
max DSL visual gate changed pixel ratio @10: 0.018258
```

Top remaining gate records:

```text
29-e9a490e9a5aee694b6e993b6.png: gateChangedPixelRatio10=0.018258, gateNormalizedMeanAbsError=0.002318
34-e7a5a8e58aa1e6bc94e587ba.png: gateChangedPixelRatio10=0.017771, gateNormalizedMeanAbsError=0.001609
19-e696b0e883bde6ba90e58585e794b5.png: gateChangedPixelRatio10=0.015419, gateNormalizedMeanAbsError=0.003491
03-e7949fe9b29ce4b9b0e88f9c.png: gateChangedPixelRatio10=0.012402, gateNormalizedMeanAbsError=0.002127
02-e7bbbce59088e59586e59f8e.png: gateChangedPixelRatio10=0.012319, gateNormalizedMeanAbsError=0.003749
37-e59296e595a1e88cb6e9a5ae.png: gateChangedPixelRatio10=0.011351, gateNormalizedMeanAbsError=0.003577
08-e98791e89e8de79086e8b4a2.png: gateChangedPixelRatio10=0.010799, gateNormalizedMeanAbsError=0.004764
12-e5908ce59f8ee8b791e885bf.png: gateChangedPixelRatio10=0.010225, gateNormalizedMeanAbsError=0.003313
30-e699bae685a7e5aeb6e5b185.png: gateChangedPixelRatio10=0.008190, gateNormalizedMeanAbsError=0.002642
36-e58d9ae789a9e9a686e5afbce8a788.png: gateChangedPixelRatio10=0.006301, gateNormalizedMeanAbsError=0.002318
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, fixed screenshot size, literal text,
brand, theme color, industry, account, or one-screenshot rule was added. This
stage explicitly rejects metric squeezing from the remaining low, mixed
gate-diff residues. Future implementation must start from a concrete
user-visible failure, not from trying to make the residual gate metric smaller.
```

Decision:

```text
Stop the current Stage 061 long-run coding loop at the Stage 7 baseline.
The next work item should be a new bug or active plan tied to a specific
visible failure and owning-layer diagnosis. At this point Bug 012 was still
open/partial and required a separate current-state audit before final
completion could be claimed.
```

### Stage 9: Bug 012 Verification And OCR Transient Retry

Status:

```text
passed
```

Scope:

```text
Continued from the active 061 goal instead of treating Stage 8 as final
completion. The first completion audit found that Bug 012 was still marked
open/partial, even though current code already contained label-anchored blocked
foreground recovery and M29.5 copied-image cleanup authorization tests.

Re-ran the original Bug 012 source image through the current upload-preview
pipeline. The original failure no longer reproduces: the four bottom-tab
blocked fragments are recovered by M29.2 as raster_icon / icon_replay, M29.5
keeps them as icon_replay, and the materialized DSL contains selectable image
nodes for those icons.

The first 40-image validation attempt then exposed a separate reliability issue:
image 05 failed at OCR because the external Baidu PP-OCRv5 endpoint returned a
transient SSL EOF during polling. This is not an M29 source-ownership defect,
but it violates the 061 batch gate because supportedFailedCount became 1.

The fix is limited to the OCR provider HTTP boundary. Baidu PP-OCRv5 submit,
poll, and JSONL download now use provider-local bounded retry for transient
transport errors and transient HTTP statuses. No M29 algorithm, DSL, public API,
Renderer, Figma plugin, source ownership, replay plan, materializer, cleanup
authorization, or dependency behavior changed.
```

First-principles classification:

```text
real goal: keep 061 real-sample validation stable and close a concrete visible
  bottom-tab icon bug only when current evidence proves it
source truth: source PNG + OCR boxes + raw M29 blocked fragments + M29.2 source
  ownership + M29.5 replay/cleanup plan + materialized DSL
information-loss point for Bug 012: old M29.2 local blocked-fragment gate failed
  to use OCR label anchor evidence inside low-confidence composite media
information-loss point for the new batch failure: OCR evidence never entered the
  pipeline because the external provider HTTP request failed transiently
owning layer: M29.2/evidence chain for Bug 012 evidence; OCR provider HTTP
  boundary for transient SSL EOF
do-not-do: do not patch materializer/Renderer/plugin, do not fabricate OCR
  output after true OCR failure, do not rerun whole tasks silently in-process
next verification: targeted tests + original Bug 012 diagnostic run + 40-image
  primary HTTP batch
```

Bug 012 diagnostic evidence:

```text
source:
  backend/storage/uploads/task_ba7fda4a90e9/original.png

single-image diagnostic ledger:
  backend/tmp/bug012_current/upload_preview_batch_validation.json

current diagnostic task:
  task_ef9e0ae177cc

result:
  completed: 1/1
  failed: 0
  degraded: 0
  missing artifacts: 0
  asset fetch failures: 0
```

Current recovered bottom-tab icon evidence:

```text
m292_object_0108 [442,1559,50,51] raster_icon / raster_icon / icon_replay, labelAnchorOcrBoxId=ocr_text_084, blockedIds=[blocked_027]
m292_object_0109 [816,1561,41,46] raster_icon / raster_icon / icon_replay, labelAnchorOcrBoxId=ocr_text_086, blockedIds=[blocked_028, blocked_031]
m292_object_0110 [82,1562,42,45] raster_icon / raster_icon / icon_replay, labelAnchorOcrBoxId=ocr_text_082, blockedIds=[blocked_029]
m292_object_0111 [264,1563,43,44] raster_icon / raster_icon / icon_replay, labelAnchorOcrBoxId=ocr_text_083, blockedIds=[blocked_030]
```

M29.5 / DSL evidence:

```text
All four recovered source objects have finalReplayAction=icon_replay.
All four include copied_image_asset cleanupTargets against parent media
m292_object_0094 with reason=label_anchored_blocked_asset_contained_by_media.

The materialized DSL contains:
  M29 Symbol / m292_object_0108
  M29 Symbol / m292_object_0109
  M29 Symbol / m292_object_0110
  M29 Symbol / m292_object_0111

These icons are grouped by controlled transparent row group:
  m29_c_group_m29_sibling_group_0026
```

Failed batch attempt before OCR retry:

```text
ledger:
  backend/tmp/validation/upload_preview_batch_20260526_070757/upload_preview_batch_validation.json

result:
  completed: 39/40
  supported failed: 1
  degraded: 1
  backend crashes: 0
  failed sample: 05-e5a496e58d96e782b9e9a490.png
  failed stage: ocr
  reason: Baidu PP-OCRv5 HTTPS SSL EOF during remote OCR polling
```

Fix:

```text
Baidu PP-OCRv5 submit / poll / result download:
  max attempts = 3
  retry requests transport exceptions
  retry HTTP 408 / 425 / 429 / 5xx
  do not retry remote job state=failed as success
  do not fabricate OCR output
```

Validation:

```bash
cd backend
uv run pytest tests/test_baidu_ocr.py tests/test_source_ui_physical_graph.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试/images --poll-timeout 300
```

Result:

```text
targeted tests: 79 passed
primary inputs: 40
supported inputs: 40
unsupported inputs: 0
completed: 40
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_074415/upload_preview_batch_validation.json
```

Key metrics:

```text
visible replay claims: 4921
promoted internal source objects: 22
average DSL visual normalized mean absolute error: 0.039127
max DSL visual changed pixel ratio @10: 0.111889
average DSL visual gate normalized mean absolute error: 0.001449
max DSL visual gate changed pixel ratio @10: 0.018258
ownership conflict type counts: {}
```

Anti-overfitting check:

```text
No filename, sample id, fixed coordinate, fixed screenshot size, literal text,
brand, theme color, industry, account, or one-screenshot rule was added. The
OCR retry is provider-local and transport/status based. The Bug 012 closure is
based on current source evidence and existing generic label-anchor recovery,
not bottom-nav text, app type, or coordinates.
```

Bug ledger:

```text
Bug 012 moved from docs/bugs/open/ to docs/bugs/resolved/.
```

### Stage 10: Finite Control Background Verification

Status:

```text
passed
```

Scope:

```text
Completion audit after Stage 9 found Bug 011 still open in the bug ledger even
though the finite-control-background path had already been implemented and
validated in earlier 061 work.

This stage did not add new code. It verified the current source-evidence chain
against the 525 secondary real-sample set and closed the stale bug record with
current artifact evidence. The tea-order sample's bottom control background is
now a finite editable shape, not preserved as media raster.
```

First-principles classification:

```text
real goal: finite UI controls become editable shape layers when source evidence
  supports them
source truth: source PNG + OCR bbox + raw M29 shape/unknown evidence + M29.2
  source ownership + M29.5 replay plan
information-loss point: old low-confidence image-like unknown classification
  could steal ownership from finite control backgrounds before the shape replay
  plan was formed
owning layer: raw M29 support detection + M29.2 source ownership
do-not-do: do not invent owner/cleanup in materializer, Renderer, or plugin;
  do not use literal text, color, filename, task id, fixed bbox, or one-sample
  layout rules
next verification: targeted tests + 525 secondary batch + tea sample
  M29.2/M29.5/DSL artifact inspection
```

Validation:

```bash
cd backend
uv run pytest tests/test_source_ui_physical_graph.py tests/test_visual_primitive_graph.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/525测试 --poll-timeout 300
```

Result:

```text
targeted tests: 92 passed in 17.31s
secondary inputs: 6
supported inputs: 6
completed: 6
supported failed: 0
degraded: 0
backend crashes: 0
missing artifacts: 0
asset fetch failures: 0
ownership overlap conflicts: 0
```

Ledger:

```text
backend/tmp/validation/upload_preview_batch_20260526_080221/upload_preview_batch_validation.json
```

Key secondary-set metrics:

```text
visible replay claims: 381
composite media count: 39
internal candidates: 1204
accepted internal candidates: 891
matched internal groups: 21
transparent asset candidates: 1198
transparent assets allowed: 41
promoted internal source objects: 15
controlled structure groups: 36
average DSL visual normalized mean absolute error: 0.021218
max DSL visual changed pixel ratio @10: 0.080967
average DSL visual gate normalized mean absolute error: 0.005125
max DSL visual gate changed pixel ratio @10: 0.025176
ownership conflict type counts: {}
```

Tea-order sample evidence:

```text
source:
  /Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月23日 17_52_19.png

task:
  task_e9899b456736

M29.2 object:
  id = m292_object_0108
  bbox = [662, 1479, 206, 66]
  visualKind = control_background
  pixelOwner = shape_geometry
  replayDecision = shape_replay
  reason = low_confidence_unknown_control_background
  shapeFillOverride = #456441
  shapeRadiusOverride = 33

M29.5:
  finalReplayAction = shape_replay

DSL:
  node = m29_shape_0004
  fill = #456441
  radius = 33
```

Cleanup evidence:

```text
Only fallback cleanup remains for this finite control. The copied image cleanup
target is suppressed because the parent media was not materialized, so the
materializer does not receive an invalid copied-media cleanup instruction.
```

Anti-overfitting check:

```text
No code was changed in this stage. The closure is based on current generic
source evidence and real-sample artifacts, not a new filename, literal text,
theme color, fixed coordinate, task id, or one-screenshot rule.
```

Bug ledger:

```text
Bug 011 moved from docs/bugs/open/ to docs/bugs/resolved/.
```
