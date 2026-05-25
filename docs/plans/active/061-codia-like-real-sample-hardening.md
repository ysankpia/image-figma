
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
/Users/luhui/Downloads/测试
```

Requirements:

* Treat every PNG/JPG/JPEG/WebP image inside this folder as part of the batch unless the current upload code only accepts PNG.
* If non-PNG files exist and the current product only accepts PNG, record them as `unsupported_input_format` in the ledger. Do not silently skip them.
* Do not test one image and claim completion.
* Single-image testing is allowed only for diagnosis.
* Final acceptance for each stage requires rerunning the full batch.

If these folders exist locally, run them as secondary regression sets after the primary set:

```text
/Users/luhui/Downloads/m29
/Users/luhui/Downloads/525测试
```

If they do not exist, record `not_found` and continue with `/Users/luhui/Downloads/测试`.

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

Create or improve a batch ledger for `/Users/luhui/Downloads/测试`.

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
all supported images in /Users/luhui/Downloads/测试 complete upload-preview
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
Run /Users/luhui/Downloads/测试 through upload-preview and produce a real batch ledger.
```

Required:

```text
discover input images
run full batch
record completed/failed/degraded
record all artifact paths
record missing artifacts
record current metrics
do not change algorithms unless required to make the batch runner work
```

Validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/测试
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
rerun full batch
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
full batch
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
3. Full /Users/luhui/Downloads/测试 batch has been rerun.
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
- batch: /Users/luhui/Downloads/测试
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
1. /Users/luhui/Downloads/测试 has a complete batch ledger.
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
