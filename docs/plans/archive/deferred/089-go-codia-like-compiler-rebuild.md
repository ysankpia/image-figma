# 089 Go Codia-like Compiler Rebuild

## Status

deferred / paused at Beta checkpoint

This plan is no longer an active execution plan. The current branch is preserved as a Beta / best-effort Go Codia-like compiler line, but further investment is paused. Future work should resume from the checkpoint and Beta wiring plan below, not from chat history.

Reason for pause:

- The offline Go compiler path is useful and measurable.
- The product runtime still uses the existing Python/FastAPI upload-preview -> DSL v0.1 -> Renderer mainline.
- The remaining Codia-like quality ceiling is dominated by upstream UI role detection / `ImageView` source recall, not by `xycut`, final tree ordering, or local threshold tuning.
- The next work is either Beta productization or detector-backed role-aware evidence; both are larger than the current branch should continue absorbing opportunistically.

## 2026-05-30 VLM Detector Probe Checkpoint

This deferred plan remains the Go Codia-like compiler checkpoint. The resumed detector work is now tracked in the active plan:

```text
docs/plans/active/090-openai-compatible-ui-detector-short-pass.md
```

The practical conclusion from the 2026-05-30 probes:

```text
Use an OpenAI-compatible VLM short-pass detector as the immediate upstream candidate provider.
Defer RICO/YOLO self-training as a future replacement or cost-reduction path.
Do not return to XY-cut tuning or tree-level fabrication for missing ImageView leaves.
```

Observed provider results:

| probe | sample | result | decision |
| --- | --- | --- | --- |
| OpenAI-compatible GPT-5.5 full-image simple prompt | Tencent 022 | `ImageView` 19/37 matched@0.5; `EditText` and `BottomNavigation` bbox quality acceptable; `Button` detector count 19 for 4 golden buttons | useful but Button extra-prone |
| OpenAI-compatible GPT-5.5 long prompt | Tencent 018 | failed with SSL record layer error under large image + long prompt + large JSON | reject long single-pass route |
| Qwen3-VL-8B compact prompt | Tencent 018 | 50 candidates, but `ImageView` 0/39 matched@0.5 and `TextView` 1/48 matched@0.5 | not primary detector |
| OpenAI-compatible GPT-5.5 short prompt multi-pass | Tencent 018 | `ImageView` 26/39 matched@0.5, `Background` 7/9 matched@0.5, `BottomNavigation` 1/1 matched@0.5 | current preferred route |

The successful shape is:

```text
short prompt + role-focused multi-pass
-> ui_detector_candidates.v1.json
-> report-only eval
-> permission-gated merge
-> existing Codia leaf/control/tree/emitter pipeline
```

The first merge target should remain narrow:

```text
ImageView-only permission merge after report-only coverage proves value.
Button, Background, ViewGroup, and ListView remain report-only or hint-only until backed by M29 source/pixel evidence and ownership gates.
```

This update does not change the active product mainline. The formal runtime remains Python/FastAPI `/api/upload-preview` -> DSL v0.1 -> Renderer. The VLM detector is an offline/Beta side-path candidate provider for `services/backend-go`.

## Source Of Truth

- Product spec: `docs/product/codia_compiler_buildability_audit_zh.md`
- Runtime target: `services/backend-go`
- Golden source data: raw Codia/Figma canvas JSON files only.

Do not use `docs/reference` prose/spec articles as implementation truth for this plan. Raw `.canvas.json` files may be used as golden samples because they are source artifacts, not reference commentary.

## Goal

Build a Go backend path capable of producing a Codia-like structure:

```text
screenshot / source evidence
-> role-aware IR
-> Codia-like tree
-> Figma-like emission
-> structural and visual validation
```

This replaces the previous idea that `m29visualtree` can reach parity through XY-cut tuning. Existing M29 primitives, tokens, relations, traces, and eval tools may be reused as evidence and diagnostics, but the final Codia-like structure contract is the product spec's role IR contract.

## Non-goals

- Do not tune `spatial_group.go` thresholds as the main solution.
- Do not make text bbox alone synthesize structural Button/EditText backgrounds.
- Do not hand-write complete Figma internal `.canvas.json` serialization as the primary output.
- Do not hardcode sample name, file path, visible text, exact bbox, fixed screen size, theme color, or brand-specific rules in production logic.
- Do not treat visible Figma names as semantic truth; semantic role belongs in schema-like identity and IR.

## Current Code Audit

The current Go codebase already has useful pieces, but it is not yet a complete Codia-like compiler.

Keep and harden:

- `internal/codia/canvas`: raw Codia/Figma canvas analyzer. It is the source-truth reader for golden structure, role vocabulary, schema suffixes, background last-child checks, overlap/overflow facts, and per-sample baselines.
- `internal/codia/ir`: role-aware IR. It already carries `role`, `source_bbox`, `figma_bbox`, `schema_id`, `seq`, source identity, evidence, style, text, asset, and ordered children.
- `internal/codia/emitter`: controlled Figma-like tree emitter. It is the first emission contract for `FRAME`, `TEXT`, `ROUNDED_RECTANGLE`, visible-name closure, relative bbox, and dual bbox preservation.
- `internal/codia/leaf`: M29 evidence token to Codia leaf bridge. It should remain a leaf/source evidence adapter, not a final tree builder.
- `internal/m29/*`: evidence provider. It may produce OCR text, surfaces, image/symbol crops, relations, masks, crops, and diagnostics, but it must not own final Codia tree structure.

Refactor or replace:

- `internal/codia/control`: current implementation flattens synthesized controls back into root children and y/x-sorts the mixed result. That conflicts with the product contract. It must become an intermediate control-synthesis stage that returns controls plus remaining leaves; region/list/tree ownership belongs in a new tree builder.
- `cmd/codiacontrols`: current CLI remains useful for Phase 4 diagnostics, but it is not the final compiler entrypoint.
- `cmd/m29visualtree` and `internal/m29/visualtree`: keep as legacy diagnostics and eval attribution only. They must not be promoted as the Codia-like compiler mainline.

Missing:

- role-aware structural diff between generated Codia IR and raw golden Codia IR;
- compiler orchestration API / CLI that runs screenshot evidence -> leaves -> controls -> tree -> emission -> validation;
- `ActionBar` / `StatusBar` / `BottomNavigation` / `ListView` / residual `ViewGroup` classifier;
- tree builder that attaches controls/leaves to regions while allowing overlap and overflow;
- parent-edge validation, background-order validation, and role-aware bbox metrics;
- render/pixel diff hook after the Figma/API emitter exists.

## Phase Plan

### Phase 0: Codia Canvas Analyzer

Create a Go analyzer that reads raw Codia/Figma canvas JSON and writes:

```text
codia_canvas_analysis.v1.json
codia_canvas_analysis_report.md
```

The analyzer must locate `Figma design - ... / Root`, compute absolute bboxes, parse `schema:id` into `role/x/y/seq`, and report:

- node count, max depth, root child count;
- Figma type/name/role counts;
- `guid` and `schema:id` coverage;
- suffix continuity and duplicate suffixes;
- child suffix ordering;
- Background / bg_Button / bg_EditText last-child checks;
- Button/EditText child role modes;
- TextView name/characters checks;
- IMAGE fill and unique hash counts;
- corner radius counts by role;
- parent-child overflow and sibling overlap diagnostics;
- role-to-visible mapping violations.

### Phase 1: Golden Canvas To Codia IR

Add a Codia IR package and importer:

```text
raw canvas JSON -> Codia IR
```

Every IR node must have `id`, `role`, `source_bbox`, `figma_bbox`, `schema_id`, `seq`, `evidence[]`, style/text/asset data where available, and ordered children.

Phase 1 artifact:

```text
codia_ir.v1.json
```

### Phase 2: IR To Figma-like Tree Emitter

Emit a controlled Figma-like tree from IR using only:

```text
FRAME
TEXT
ROUNDED_RECTANGLE
```

Visible names are limited to `Root`, `Groups`, `Button`, `Text`, `Image`, `Background`, or literal text. Golden IR replay must pass analyzer hard checks before screenshot inference is attempted.

Phase 2 artifact:

```text
codia_figma_like_tree.v1.json
```

This artifact is intentionally not full Figma internal canvas serialization. It is the compiler-owned emitted tree used to validate type/name/role/schema/bbox/order before a Figma Plugin API emitter is introduced.

### Phase 3: M29 Evidence To Codia Leaves

Consume current Go M29 artifacts as source evidence to generate `TextView`, `ImageView`, and `Background` leaf candidates with source evidence and dual bbox tracking.

Phase 3 artifacts:

```text
codia_leaf_ir.v1.json
codia_leaf_ir_report.md
codia_figma_like_tree.v1.json
```

`codia_leaf_ir.v1.json` is still a `CodiaIR` document. The distinct filename marks that it was generated from M29 evidence tokens rather than golden canvas replay. Phase 3 does not synthesize `Button`, `EditText`, `ListView`, or region containers; those require explicit control/list evidence in later phases.

### Phase 4: Control Synthesis

Synthesize `Button` and `EditText` from explicit background evidence plus foreground text/image/icon evidence before generic grouping. `bg_Button` and `bg_EditText` must be owner-local and last child.

Phase 4 artifacts:

```text
codia_control_stage.v1.json
codia_control_ir.v1.json
codia_control_ir_report.md
codia_figma_like_tree.v1.json
```

Phase 4 consumes `CodiaIR` leaves and emits a control-stage result with `controls`, `remaining`, `rejections`, and `diagnostics`. `codia_control_ir.v1.json` remains a compatibility/debug snapshot assembled from that stage result, but it is no longer the final tree contract. It is intentionally evidence-gated: it can only synthesize controls when a Background/control-surface candidate already exists. If a sample has OCR/icon foreground but no background surface token, the correct fix is upstream physical evidence/control-surface detection, not text-bbox-only control creation.

Current Phase 4 implementation also extends Go M29 physical evidence with reportable control-surface candidates for:

- OCR-local same-color low-texture controls;
- horizontal control surfaces anchored by compact foreground glyphs, such as search fields;
- local contrast surfaces for colored/gradient pill controls.

Control synthesis preserves this upstream evidence as `control_surface_background`, prefers wide `EditText` candidates over local glyph buttons, prefers wide action-button surfaces over inner text-only surfaces, consumes duplicate owner-local backgrounds, and rejects obvious pure numeric/price text-only controls. These rules are permission gates over pixel evidence; they still do not create a background from text bbox alone.

### Phase 5: Region/List Classifier

Classify `ActionBar`, `StatusBar`, `BottomNavigation`, `ListView`, and residual `ViewGroup` using collection/body/rail/control evidence. Parent-child overlap and overflow are allowed.

Phase 5 must also separate true controls from card-internal reward/price/equity panels. Phase 4 validation shows the control-surface detector can now expose enough pixel evidence, but without region/list/card context it still over-materializes some nested panels as `Button`.

### Phase 6: Closed-loop Validation

Run structure validation, render validation, and failure attribution by stage. Existing `compare_trees.py` can remain a historical diagnostic, but release gates must be role-aware.

## Implementation Gate From Current Planning Pass

The next implementation must start with validation and compiler structure, not more local heuristics inside `control` or `spatial_group.go`.

### Stage A: Role-aware structure diff

Add a Go validation package, expected location:

```text
services/backend-go/internal/codia/diff
services/backend-go/cmd/codiadiff
```

The diff reads generated `CodiaIR` and golden `CodiaIR`, then writes:

```text
codia_structure_diff.v1.json
codia_structure_diff_report.md
```

Required checks:

- role vocabulary and visible-name closure;
- role precision/recall by `Button`, `EditText`, `TextView`, `ImageView`, `Background`, `ListView`, `ActionBar`, `StatusBar`, `BottomNavigation`, `ViewGroup`;
- generated-node and golden-node best IoU by same role;
- parent edge matching where both sides have a matched node;
- `Button` -> `bg_Button` ownership and last-child accuracy;
- `EditText` -> `bg_EditText` ownership and last-child accuracy;
- background-late ordering;
- root/region overlap must be reported, not treated as invalid by default;
- extra/missed nodes by role and by parent role.

The report must make it obvious whether a failure belongs to OCR/leaf extraction, control synthesis, region/list classification, tree construction, ordering/sequence, or emitter validation.

### Stage B: Compiler orchestration skeleton

Add a Go compiler package and CLI, expected location:

```text
services/backend-go/internal/codia/compiler
services/backend-go/cmd/codiacompile
```

Initial pipeline:

```text
input PNG + OCR
-> m29 physical evidence
-> m29 evidence tokens
-> codia leaves
-> codia controls
-> codia tree builder
-> codia figma-like tree
-> optional golden diff
```

The CLI should accept:

```bash
go run ./cmd/codiacompile \
  -input /path/source.png \
  -ocr /path/ocr.json \
  -golden /path/codia_ir.v1.json \
  -out /tmp/codia-compile
```

Required artifacts:

```text
m29_physical_evidence.v1.json
evidence_tokens.v1.json
codia_leaf_ir.v1.json
codia_control_stage.v1.json
codia_control_ir.v1.json
codia_tree_ir.v1.json
codia_figma_like_tree.v1.json
codia_structure_diff.v1.json
codia_structure_diff_report.md
codia_failure_audit.v1.json
codia_failure_audit_report.md
```

`-golden` is optional for normal compilation but required for golden validation. The compiler must not read Codia golden data during normal generation decisions; golden data is only for validation.

### Stage C: Control synthesis refactor

Refactor `internal/codia/control` so it no longer claims to build final root children. It should expose a stage result similar to:

```go
type Result struct {
    RootBBox   ir.BBox
    Controls   []ir.Node
    Remaining  []ir.Node
    Diagnostics Diagnostics
}
```

Contract:

- synthesize `Button` / `EditText` only from explicit `Background` / control-surface evidence plus foreground text/image/icon;
- keep `bg_Button` / `bg_EditText` owner-local and last child;
- do not attach synthesized controls to root as final structure;
- do not sort final mixed tree by y/x;
- reject text-bbox-only backgrounds;
- reject obvious same-bbox/same-foreground-color pseudo controls unless independent surface evidence exists;
- keep all rejections diagnostic and source-evidence based, not text/content/sample based.

Current implementation status: complete for the stage boundary. `internal/codia/control` now returns `CodiaControlStage` with `controls`, `remaining`, `rejections`, and `diagnostics`; `codia_control_stage.v1.json` is written next to the compatibility `codia_control_ir.v1.json` snapshot; `internal/codia/tree` and `internal/codia/compiler` consume the stage result rather than treating control synthesis as the final root tree.

### Stage D: Tree builder v1

Add a tree builder, expected location:

```text
services/backend-go/internal/codia/tree
```

Inputs:

```text
TextView leaves
ImageView leaves
Background leaves
Button/EditText controls
region candidates
list/repeated-cell candidates
chrome/bottom-nav candidates
```

First implementation target:

- root is viewport;
- detect top chrome / `ActionBar` / optional `StatusBar` from top-band controls/text/background evidence;
- detect `BottomNavigation` from bottom-band repeated image+text tab slots, not as Buttons;
- detect main body and horizontal/vertical repeated regions as `ListView`;
- attach controls to best region/list/card owner, not root;
- attach leaves to best region/card/control owner while allowing overflow;
- keep large image/background nodes as leaf siblings or region children, never universal parents;
- use foreground-first/background-late ordering;
- assign deterministic schema sequence with reverse-children DFS.

### Stage E: Golden sample regression

Run both golden replay and screenshot-derived compilation on 018 and 022.

Golden replay must pass analyzer/emitter checks:

```bash
cd services/backend-go
go run ./cmd/codiaanalyze \
  -input /Users/luhui/Downloads/figma/json/腾讯动漫_018_1440.json \
  -out /tmp/codia-golden-018 \
  -expect tencent-comic-018

go run ./cmd/codiaanalyze \
  -input /Users/luhui/Downloads/figma/json/腾讯动漫主要.canvas.json \
  -out /tmp/codia-golden-022
```

Screenshot-derived compiler validation must run:

```bash
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -ocr /tmp/eval_4img/t018/ocr.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/codia-compile-018

go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_022_1440.png \
  -ocr /tmp/eval_4img/t022/ocr.json \
  -golden /tmp/codia-golden-022/codia_ir.v1.json \
  -out /tmp/codia-compile-022
```

Initial acceptance for Stage E:

- emitted tree passes visible type/name closure;
- every node has `role`, `source_bbox`, `figma_bbox`, `schema_id`, and evidence;
- `Button`/`EditText` background last-child accuracy is 100%;
- controls are no longer emitted as root-flat final children unless golden root really owns them;
- 022 no longer materializes the known cover/title label pattern as a standalone `Button`;
- 018 keeps currently matched URL, offer, price-label, and payment controls while reducing obvious reward/price panel extras;
- failures are reported by stage in `codia_structure_diff_report.md`.

This is not the final 1:1 target. It is the first executable compiler skeleton that makes further convergence measurable.

### Stage F: Failure audit and owning-layer routing

Add a read-only failure audit over `codia_structure_diff.v1.json`:

```text
services/backend-go/internal/codia/audit
services/backend-go/cmd/codiaaudit
```

The audit must not read raw Codia canvas JSON, must not participate in generation decisions, and must only classify existing generated-vs-golden diff failures into owning layers:

```text
m29_physical_evidence_or_codia_leaf
background_detection_or_permission
control_synthesis
codia_tree_builder
```

Required artifacts:

```text
codia_failure_audit.v1.json
codia_failure_audit_report.md
```

The report must aggregate failures by stage, diagnosis, role, evidence kind, IoU bucket, and action item. Its job is to stop blind tree/threshold edits and route each next fix to the layer that actually lost information.

## Phase 0 Acceptance

Commands:

```bash
cd services/backend-go
go test ./internal/codia/... ./cmd/codiaanalyze/...
go run ./cmd/codiaanalyze -input /Users/luhui/Downloads/figma/json/腾讯动漫_018_1440.json -out /tmp/codia-analyze-018 -expect tencent-comic-018
go run ./cmd/codiaanalyze -input /Users/luhui/Downloads/figma/json/腾讯动漫主要.canvas.json -out /tmp/codia-analyze-022
```

The 018 expectation must verify:

- Root size `665 x 1440`;
- Root direct children `3`;
- design nodes `146`;
- max depth `6`;
- types `FRAME 41`, `TEXT 48`, `ROUNDED_RECTANGLE 57`;
- roles `TextView 48`, `ImageView 39`, `ViewGroup 24`, `Button 9`, `bg_Button 9`, `Background 9`, `ListView 5`, `ActionBar 1`, `BottomNavigation 1`, `root 1`;
- schema coverage `146/146`;
- suffix range `0..145`, no missing;
- multi-child suffix descending `41/41`;
- `Background 9/9` last child and `bg_Button 9/9` last child;
- Button modes `2` text+image+bg and `7` text+bg;
- TextView name/characters `48/48`;
- IMAGE fill count `48` and unique image hashes `48`.
- corner radius node count `8`, by role `Background 4`, `bg_Button 4`.

## Current Validation Snapshot

Commands run during Stage A-D:

```bash
cd services/backend-go
go test ./internal/codia/... ./cmd/codiaanalyze ./cmd/codialeaves ./cmd/codiacontrols ./cmd/codiadiff ./cmd/codiacompile ./cmd/codiaaudit

rm -rf /tmp/codia-golden-018 /tmp/codia-golden-022 /tmp/codia-compile-018 /tmp/codia-compile-022
go run ./cmd/codiaanalyze \
  -input /Users/luhui/Downloads/figma/json/腾讯动漫_018_1440.json \
  -out /tmp/codia-golden-018 \
  -expect tencent-comic-018
go run ./cmd/codiaanalyze \
  -input /Users/luhui/Downloads/figma/json/腾讯动漫主要.canvas.json \
  -out /tmp/codia-golden-022
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -ocr /tmp/eval_4img/t018/ocr.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/codia-compile-018
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_022_1440.png \
  -ocr /tmp/eval_4img/t022/ocr.json \
  -golden /tmp/codia-golden-022/codia_ir.v1.json \
  -out /tmp/codia-compile-022
```

Current screenshot-derived compiler diff:

| sample | generated nodes | golden nodes | matched | extra | missed | parent edge precision | parent edge recall | status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Tencent 018 | 150 | 146 | 90 | 60 | 56 | 0.409 | 0.421 | `ActionBar`, `BottomNavigation`, `ListView`, and `ViewGroup` now have matches; generated `Button` precision is now 1.00 |
| Tencent 022 | 102 | 120 | 82 | 20 | 38 | 0.554 | 0.471 | `StatusBar`, `BottomNavigation`, `ListView`, side rail `ListView`, and `ViewGroup` now have matches; generated `Button` precision is now 1.00 |

Current failure audit:

| sample | top owning layer | top diagnosis | count | next implication |
| --- | --- | --- | ---: | --- |
| Tencent 018 | `m29_physical_evidence_or_codia_leaf` | `upstream_leaf_missing ImageView` | 14 | Fix source primitive / Codia leaf crop extraction before tree ownership. |
| Tencent 018 | `m29_physical_evidence_or_codia_leaf` | `leaf_bbox_too_large_or_shifted ImageView` | 8 | Existing generated crops are too coarse or shifted. |
| Tencent 018 | `background_detection_or_permission` | `background_fragment_extra` | 16 | Merge/consume/suppress unmatched background fragments before final tree emission. |
| Tencent 022 | `m29_physical_evidence_or_codia_leaf` | `upstream_leaf_missing ImageView` | 20 | Right rail and body internal image crops are missing upstream evidence. |
| Tencent 022 | `codia_tree_builder` | `tree_container_bbox_mismatch ViewGroup` | 8 | Tree containers need evidence-derived bbox fitting after leaf crop recall improves. |

Stage F follow-up now adds a conservative M29 physical-evidence pass for repeated internal raster slots inside large raster parents. It is report-free source evidence, not a tree/golden patch: candidates are emitted as ordinary `image_region` primitives with reasons such as `internal_raster_crop_candidate`, `repeated_internal_raster_slot`, and `side_rail_crop_candidate`; the existing evidence and Codia leaf bridge then convert them into `ImageView` candidates. The gate requires repeated column evidence after duplicate removal, strong raster texture, and either left-cover-column position or right-side rail position. A post-gate height normalizer expands terminal repeated-row slots to the same column's median height, which fixes truncated bottom rail crops without changing tree ownership. It does not read Codia golden data and does not use sample names, literal text, fixed bboxes, fixed screen sizes, or brand/theme rules.

Validation after this pass:

```bash
cd services/backend-go
go test ./internal/m29/pipeline ./internal/m29/evidence ./internal/codia/... ./cmd/codiacompile

go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_022_1440.png \
  -ocr /tmp/eval_4img/t022/ocr.json \
  -golden /tmp/codia-golden-022/codia_ir.v1.json \
  -out /tmp/codia-compile-022

go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -ocr /tmp/eval_4img/t018/ocr.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/codia-compile-018
```

Result:

| sample | before internal raster slots | after internal raster slots | audit delta |
| --- | --- | --- | --- |
| Tencent 018 | 90 / 60 / 56 | 90 / 60 / 56 | no new internal crop remains after final repeat gate |
| Tencent 022 | 82 / 20 / 38 | 89 / 20 / 31 | `upstream_leaf_missing ImageView` drops from 20 to 13; image bbox mismatch drops back to 1 after repeated-slot height normalization |

Remaining implication: the source-evidence layer now recovers the major repeated cover crops and side-rail crops in 022 without regressing 018 or increasing total extras. The remaining missed ImageView nodes are mostly small icons and inner card/thumb crops; the next fix should keep working upstream in physical evidence/leaf extraction, especially small image/icon crop recall and the oversized parent raster token, before changing tree ownership.

A second source-evidence pass promotes large textured `symbol_region` primitives into `raster_region_token`s before symbol clustering. This repairs cases where connected-component extraction already found the true image/thumb pixels, but evidence tokenization swallowed them into oversized or nearby symbol clusters. The promotion gate requires sufficient area, width/height, fill ratio, texture, color count, and edge density; a dedup pass suppresses contained or same-column half-fragments when a more complete textured primitive exists. This is still upstream evidence routing, not tree ownership or golden replay logic.

Validation after this pass:

| sample | previous | after large textured symbol promotion | audit delta |
| --- | --- | --- | --- |
| Tencent 018 | 90 / 60 / 56 | 93 / 62 / 53 | ImageView matched 17 -> 20, generated ImageView precision 0.35 -> 0.37, recall 0.44 -> 0.51 |
| Tencent 022 | 90 / 20 / 30 | 90 / 20 / 30 | unchanged |

Remaining implication: 018 now exposes several card-internal ImageView thumbs as proper raster leaves. Remaining 018 misses include large/background-like raster bboxes and small icon/pill fragments; these need either bbox fitting or suppression/ownership cleanup, not generic tree grouping.

Stage D implemented `internal/codia/tree` and connected it through `cmd/codiacompile`. The tree builder now creates role-aware top chrome, bottom navigation, body/list/card containers, foreground-first/background-late ordering, deterministic sequence assignment, and final-tree physical-noise filtering without reading golden canvas data. Tree-created containers now carry proposal evidence such as `body_list_owner`, `bottom_navigation_candidate`, `repeated_row_list`, `repeated_row_item`, and `major_section_owner`; `codia_tree_ir_report.md` summarizes those counts under `Tree Evidence`, and `codia_structure_diff` preserves `evidenceKind` on generated/golden node matches. A conservative repeated-row proposal scorer now keeps rich repeated rows while rejecting weak text-only rows and single mixed catch-all rows.

The current control permission pass rejects content-panel-like Button candidates: tall non-wide-action surfaces whose foreground cluster is vertically biased or multi-line content. It also rejects text-only near-fill surfaces that lack meaningful backplate padding, while preserving URL-like chrome pills. These are geometry/evidence gates, not sample-name/text/bbox rules. On Tencent 018 it rejects six reward/price/equity panel candidates, removes all generated `Button` extras, and improves the screenshot-derived diff from `88 / 73 / 58` to `90 / 62 / 56`. On Tencent 022 it rejects the remaining text-only pseudo Button and improves `79 / 21 / 41` to `79 / 20 / 41`.

The tree builder also merges vertically adjacent, horizontally aligned `control_surface_background` fragments inside the same repeated-row item into one card `Background`. This is a card/background ownership normalization, not a control permission rule. On Tencent 018 it turns two split price-card backgrounds into high-IoU matches (`0.96+`) and moves the overall diff to `90 / 60 / 56` without changing Tencent 022.

The tree builder now also detects a right-side rail when a search-top page has right-edge marker evidence plus rail-local image/control/text evidence. It emits a root-level side `ListView`, an inner `ListView` using the IR dual-bbox contract, and a stack `ViewGroup`. On Tencent 022 this matches the golden side rail outer `ListView`, inner `ListView`, and stack `ViewGroup`, moving the screenshot-derived diff from `79 / 20 / 41` to `82 / 20 / 38`. The remaining missed rail item groups require upstream leaf evidence for the individual vertical cover crops; the current M29 evidence only exposes a large body image and small edge fragments, so the tree builder must not fabricate those image leaves.

This is measurable progress over the control pass-through baseline:

| sample | pass-through matched/extra/missed | tree v1 matched/extra/missed |
| --- | --- | --- |
| Tencent 018 | 73 / 108 / 73 | 90 / 60 / 56 |
| Tencent 022 | 59 / 41 / 61 | 82 / 20 / 38 |

Remaining failure owners:

- physical leaf bbox mismatch: large screenshot crops and some OCR/icon bboxes do not match Codia's emitted leaf bbox;
- missing/background mismatch: large Codia `Background` surfaces are not yet reconstructed from source evidence in the right role and bbox;
- over-broad card/row ownership: `tree_section_*` and some `tree_row_*` containers merge multiple Codia cards or split side rails incorrectly;
- side rail/list nesting: Tencent 022 now has matched rail-level `ListView` / `ViewGroup` containers, but individual vertical rail item groups are still missed because leaf extraction does not yet expose those crops;
- rejected control-surface backgrounds: some reward/price/equity panels are no longer synthesized as `Button`, but their background leaves may still be extra or bbox-mismatched `Background` nodes;

These gaps must be fixed in physical evidence, control permission, and `internal/codia/tree` ownership. Do not push them into `m29visualtree`, `xycut`, sample names, visible text, or Codia golden identity.

Latest evidence-kind breakdown for extra generated nodes:

| sample | dominant structural extra evidence | dominant leaf/control extra evidence |
| --- | --- | --- |
| Tencent 018 | `repeated_row_item 1`, `major_section_owner 1` | `image_or_icon_crop 24`, `ocr_text 9`, `control_surface_background 9`, `solid_background 5` |
| Tencent 022 | none from repeated row/list or side rail containers | `ocr_text 10`, `control_surface_background 4`, `image_or_icon_crop 3`, `solid_background 1` |

Latest control/tree permission pass:

- `internal/codia/control` now separates accepted foreground from suppressed owner-local image fragments. Background-edge slices and tiny image specks inside accepted Button/EditText candidates are consumed as source evidence but are not emitted as `ImageView` children. This fixes a real contract issue: Codia Buttons own content foreground plus `bg_Button`, not rounded-background edge fragments.
- `internal/codia/tree` now converts the right-side rail marker into a local `Background` when and only when `buildSideRail` has already identified it as top marker evidence. This matches the raw 022 golden role for the same bbox without changing global ImageView leaf semantics.

Validation:

```bash
cd services/backend-go
go test ./internal/codia/control ./internal/codia/tree ./internal/codia/... ./cmd/codiacompile

rm -rf /tmp/codia-compile-018 /tmp/codia-compile-022
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -ocr /tmp/eval_4img/t018/ocr.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/codia-compile-018
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_022_1440.png \
  -ocr /tmp/eval_4img/t022/ocr.json \
  -golden /tmp/codia-golden-022/codia_ir.v1.json \
  -out /tmp/codia-compile-022
```

Result:

| sample | previous latest | after control/tree permission | key delta |
| --- | --- | --- | --- |
| Tencent 018 | `93 / 62 / 53` | `93 / 56 / 53` | `ImageView` generated `54 -> 48`, extras `34 -> 28`; matched/missed unchanged. |
| Tencent 022 | `90 / 20 / 30` | `91 / 17 / 29` | Side rail marker matches golden `Background_652_236_20`; `ImageView` precision reaches `0.96`; `image_or_icon_crop` extras drop to `0`. |

Remaining implication: this pass removed non-content control fragments and corrected a side-rail role error without hurting recall. It does not solve 018's remaining `ImageView` misses or background fragment extras. The next owning layer is still source leaf crop fitting and background permission/merge, especially 018 large/card image bboxes and rejected card-surface backgrounds. Do not add global small-image filtering: raw golden includes legitimate small `ImageView` nodes such as 022 `9x17` / `10x17` and 018 `20x4` markers.

Commands run during Phase 4:

```bash
cd services/backend-go
go test ./internal/m29/pipeline ./internal/m29/evidence ./internal/codia/... ./cmd/codiaanalyze ./cmd/codialeaves ./cmd/codiacontrols

rm -rf /tmp/codia-phase4-t022 /tmp/codia-phase4-t018
go run ./cmd/m29extract -input ../../docs/reference/codia-samples/images/腾讯动漫_022_1440.png -ocr /tmp/eval_4img/t022/ocr.json -out /tmp/codia-phase4-t022/extract
go run ./cmd/m29tokens -input /tmp/codia-phase4-t022/extract/m29_physical_evidence.v1.json -out /tmp/codia-phase4-t022/tokens
go run ./cmd/codialeaves -tokens /tmp/codia-phase4-t022/tokens/evidence_tokens.v1.json -out /tmp/codia-phase4-t022/leaves
go run ./cmd/codiacontrols -input /tmp/codia-phase4-t022/leaves/codia_leaf_ir.v1.json -out /tmp/codia-phase4-t022/controls

go run ./cmd/m29extract -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png -ocr /tmp/eval_4img/t018/ocr.json -out /tmp/codia-phase4-t018/extract
go run ./cmd/m29tokens -input /tmp/codia-phase4-t018/extract/m29_physical_evidence.v1.json -out /tmp/codia-phase4-t018/tokens
go run ./cmd/codialeaves -tokens /tmp/codia-phase4-t018/tokens/evidence_tokens.v1.json -out /tmp/codia-phase4-t018/leaves
go run ./cmd/codiacontrols -input /tmp/codia-phase4-t018/leaves/codia_leaf_ir.v1.json -out /tmp/codia-phase4-t018/controls
```

Observed control matching against golden Codia IR:

| sample | golden controls | synthesized controls | matched @ IoU >= 0.6 | remaining issue |
| --- | ---: | ---: | ---: | --- |
| Tencent 022 | 5 | 5 | 5 | no remaining generated `Button` extra in the current 022 smoke |
| Tencent 018 | 9 | 7 | 7 | two bottom benefit buttons still missing; rejected panel backgrounds still need background/card ownership cleanup |

This is not 1:1 complete. The next owning layer is Phase 5 region/list/card permission, not more XY-cut tuning and not text-bbox background synthesis.

Latest regression cleanup and failed experiment:

- Removed the second-pass `symbol_region` suppression inside promoted textured rasters. Local unit tests passed, but real 018 smoke had regressed from `93 / 56 / 53` to `93 / 58 / 53`; the rule suppressed or reshaped source fragments in a way that added generated extras. Keep the earlier large textured symbol promotion, but do not keep this post-promotion fragment suppression without a smoke-proven improvement.
- Tested an upstream `ocr_mixed_icon_text_split` idea for URL/control pills where OCR merges a leading icon into a text bbox. The concept is valid as a future direction, but the attempted implementation did not improve real 018/022 smoke and either produced a duplicate matched icon as an extra or no generated candidate after de-duplication. That path was removed instead of leaving dead complexity.

Current smoke after cleanup:

| sample | generated | matched | extra | missed |
| --- | ---: | ---: | ---: | ---: |
| Tencent 018 | 149 | 93 | 56 | 53 |
| Tencent 022 | 108 | 91 | 17 | 29 |

Current highest-value next layer remains source leaf extraction and crop fitting:

- 018 still has many `ImageView` misses where golden crops are absent or generated crops are too large/shifted.
- 022 `ImageView` precision is already high, so broad small-image filtering is the wrong direction.
- Background extras are still dominated by `control_surface_background`, `solid_background`, and `control_background_candidate`; those need background permission/merge/consume rules, not text-bbox-only button synthesis.
- Any future OCR mixed icon/text split must prove improvement in smoke, not just pass synthetic unit tests. It must also adjust the corresponding TextView bbox and avoid duplicating existing matched image/icon leaves.

Latest tree bbox fitting pass:

- `homeIndicatorBBox` now uses a bottom inset derived from root height instead of a hardcoded `root.Height - 25` y-position. For 1440px mobile screenshots this moves the 8px home indicator from y=1415 to y=1418, matching both 018 and 022 golden backgrounds.
- Added `TestHomeIndicatorBBoxUsesBottomInset` so this does not drift back to the old offset.

Latest validation hardening pass:

- Added `services/backend-go/tools/codia_smoke_2img.sh` as the role-aware compiler smoke gate for the two Tencent samples. It regenerates golden Codia IR from raw canvas JSON, compiles PNG+OCR through `cmd/codiacompile`, runs structural diff/audit, and enforces the current non-regression floor:
  - Tencent 018: `matched >= 94`, `extra <= 55`, `missed <= 52`
  - Tencent 022: `matched >= 92`, `extra <= 16`, `missed <= 28`
- The smoke gate keeps golden data out of generation decisions. Golden IR is passed only to `codiadiff` through `cmd/codiacompile -golden`.
- Clarified `internal/codia/tree` evidence semantics: the physical-noise gate that checks `layer_background_token` now reads `Evidence.Notes` explicitly via `firstEvidenceNotes`, while reports and matching continue to use `Evidence.Kind`. `TestDiscardPhysicalNoiseUsesEvidenceNotesForTokenType` protects this distinction.
- Extended `internal/codia/diff` and `internal/codia/audit` with leaf debug provenance. `codia_failure_audit.v1.json` and `codia_failure_audit_report.md` now include `leafDebugSamples` with node bbox, parent, best same-role bbox, best IoU, evidence kind, evidence source id, evidence notes, and source path/guid where available.
- This is report/validation hardening only. The screenshot-derived metrics intentionally remain unchanged:

| sample | generated | matched | extra | missed | parent edge precision | parent edge recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tencent 018 | 149 | 94 | 55 | 52 | 0.419 | 0.428 |
| Tencent 022 | 108 | 92 | 16 | 28 | 0.533 | 0.479 |

Immediate next implementation layer:

- Work upstream in `m29_physical_evidence_or_codia_leaf`, not in `internal/codia/tree` first.
- The new leaf debug samples show that many missed `ImageView` nodes either have no nearby generated crop or point to oversized raster tokens such as `token_0077` / `token_0030`. The next pass should split or fit image crops at the physical evidence / token / leaf adapter layer before changing tree ownership.

Validation:

```bash
cd services/backend-go
go test ./internal/codia/tree ./internal/m29/evidence ./internal/m29/pipeline ./internal/codia/... ./cmd/codiacompile

rm -rf /tmp/codia-compile-018 /tmp/codia-compile-022
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_018_1440.png \
  -ocr /tmp/eval_4img/t018/ocr.json \
  -golden /tmp/codia-golden-018/codia_ir.v1.json \
  -out /tmp/codia-compile-018
go run ./cmd/codiacompile \
  -input ../../docs/reference/codia-samples/images/腾讯动漫_022_1440.png \
  -ocr /tmp/eval_4img/t022/ocr.json \
  -golden /tmp/codia-golden-022/codia_ir.v1.json \
  -out /tmp/codia-compile-022
```

Result:

| sample | previous | after home indicator bbox fitting | key delta |
| --- | --- | --- | --- |
| Tencent 018 | `149 / 93 / 56 / 53` | `149 / 94 / 55 / 52` | `Background` matched `6 -> 7`; home indicator no longer appears as an extra/missed pair. |
| Tencent 022 | `108 / 91 / 17 / 29` | `108 / 92 / 16 / 28` | `Background` recall reaches `1.0`; home indicator no longer appears as an extra/missed pair. |

Latest Beta-quality checkpoint on 2026-05-30:

```bash
bash services/backend-go/tools/codia_smoke_2img.sh
```

Result:

| sample | generated | matched | extra | missed | parent edge precision | parent edge recall | topAction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Tencent 018 | 149 | 95 | 54 | 51 | 0.419 | 0.428 | `m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView:13` |
| Tencent 022 | 106 | 92 | 14 | 28 | 0.619 | 0.546 | `m29_physical_evidence_or_codia_leaf:upstream_leaf_missing:ImageView:13` |

This branch is usable as a Beta / best-effort Codia-like reconstruction path, but this checkpoint records the current quality ceiling: the dominant remaining failure is upstream ImageView source recall, not tree ordering or XY-cut. The detailed release-quality debt, do-not-fix paths, detector dataset plan, and future closure criteria are tracked in [bug 017](../../../bugs/open/017-codia-like-beta-ui-role-detector-gap.md).

## Pause Checkpoint And Resume Plan

This project line is paused after the 2026-05-30 Beta-quality checkpoint. Do not treat the pause as a failed implementation or as permission to revive old VisualTree tuning. The current branch contains a working offline compiler and diagnostics; what it lacks is product wiring and a stronger perception source for Codia-like small visual elements.

Current usable contract:

```text
Beta screenshot-to-Figma reconstruction.
The output is editable and structured on a best-effort basis.
Small icons, fine UI glyphs, internal image crops, and exact Codia-like hierarchy may be incomplete.
```

Forbidden claim:

```text
Codia 1:1
complete ImageView recall
complete Button/EditText/Background ownership parity
complete hierarchy parity
```

The correct next work is not another local threshold pass. It is one of two explicit tracks:

1. Productize the current compiler as a separate Beta side path.
2. Improve the source evidence layer with a detector-backed role-aware candidate path.

### Recommended Beta Productization

Default route: keep the existing formal product mainline unchanged and expose the Go Codia-like compiler as a separate Beta path first.

Current formal mainline remains:

```text
POST /api/upload-preview
GET /api/tasks/{taskId}/dsl
```

Do not replace that output yet. It produces DSL v0.1 for the current Renderer. The Go Codia compiler currently emits Codia IR and controlled Figma-like tree artifacts, not the existing Renderer DSL contract.

Recommended Beta API surface:

```text
POST /api/upload-preview-codia-beta
GET  /api/tasks/{taskId}/codia-beta
GET  /api/tasks/{taskId}/codia-beta/artifacts
```

Behavior:

```text
user PNG upload
-> Python FastAPI saves task
-> Python runner invokes services/backend-go/cmd/codiacompile
-> Go compiler writes Codia artifacts
-> API returns taskId, status, quality notice, and artifact index
```

The API response must label the path honestly:

```text
mode = "codia_beta"
quality = "best_effort"
notices = [
  "small_icons_may_be_missing",
  "not_codia_1_to_1"
]
```

### Required Beta Artifacts

Each Beta task must write a complete evidence bundle under:

```text
backend/storage/upload_previews/{taskId}/codia_beta/
```

Required files:

```text
input.png
ocr.json
extract/m29_physical_evidence.v1.json
tokens/evidence_tokens.v1.json
leaves/codia_leaf_ir.v1.json
controls/codia_control_stage.v1.json
tree/codia_tree_ir.v1.json
emitter/codia_figma_like_tree.v1.json
audit/codia_failure_audit.v1.json
audit/codia_failure_audit_report.md
manifest.json
logs/stdout.log
logs/stderr.log
```

`manifest.json` is required. It should record:

```text
taskId
input image path
compiler git commit
startedAt / finishedAt
status
topAction
artifact paths
known quality limitations
```

Without the manifest and logs, a bad online result cannot be replayed. That would recreate the original failure mode: guessing from the final tree instead of tracing the evidence chain.

### Python To Go Bridge

The FastAPI layer should not reimplement Codia compiler logic. It should only own task storage, subprocess execution, status, error mapping, and artifact indexing.

Expected module shape:

```text
backend/app/codia_beta/runner.py
backend/app/codia_beta/manifest.py
backend/app/routes/codia_beta.py
```

Rules:

- `cmd/codiacompile` remains the only compiler executor.
- Python must save stdout/stderr into `codia_beta/logs/`.
- Non-zero compiler exit marks the Beta task failed but preserves partial artifacts.
- Timeout, missing OCR, invalid PNG, and missing Go binary failures must have explicit failure reasons.
- No queue system is required for the first version; reuse the existing upload-preview task pattern unless real runtime evidence says otherwise.

### Rendering Strategy

Do not quietly stuff `codia_figma_like_tree.v1.json` into the current DSL endpoint. That would mix two contracts.

Use two stages:

1. First expose the artifact bundle and reports for internal use.
2. Then add a separate adapter or emitter:

```text
codia_figma_like_tree.v1.json
-> beta DSL adapter or plugin emitter
-> Figma nodes
```

Minimum adapter mapping:

```text
ViewGroup/ListView/ActionBar/StatusBar/BottomNavigation -> frame/group
TextView -> text
ImageView -> image asset
Background/bg_Button/bg_EditText -> rectangle
Button/EditText -> group/frame with owned children
```

This adapter is a separate implementation phase because it affects user-visible output. It must be validated by node count, hierarchy, bbox, text, image asset paths, and background ordering.

### Bad Case Capture

If this Beta path is used, every poor output must be capturable as a future detector/eval sample.

Recommended storage:

```text
backend/storage/codia_beta_feedback/{feedbackId}/
```

Record:

```text
taskId
issueType: missing_icon | wrong_crop | bad_grouping | text_error | background_error | other
artifactManifestPath
source PNG
audit report
user/internal notes
optional corrected output or reference JSON
createdAt
```

This is how the project turns Beta usage into future detector data. Without this loop, using the branch only produces anecdotal failures.

### Detector Track

The detector track is the path toward Codia 1:1 quality. It does not block Beta use.

Recommended sequence:

```text
RICO / Codia golden / synthetic UI samples
-> train or probe UI role detector
-> ui_detector_candidates.v1.json
-> report-only offline eval
-> permission-gated merge into leaf/control stage
-> ownership graph / tree emitter convergence
```

First useful roles:

```text
ImageView
Button
EditText
Background/control surface
StatusBar
BottomNavigation
```

Do not train or integrate a model that directly emits a full Codia tree as the first production path. The first learned component should emit normalized detector candidates only. M29 remains useful as pixel/source evidence; the detector supplies role-aware candidates that current M29 evidence misses.

### Resume Acceptance Criteria

If this paused work is resumed for Beta productization, acceptance is:

- Existing `/api/upload-preview` and `/api/tasks/{taskId}/dsl` behavior remains unchanged.
- Codia Beta has a separate API surface or explicit feature flag.
- Every Beta task writes `manifest.json`, artifact index, logs, and failure audit.
- A task ID is enough to find the complete evidence chain.
- User-facing copy says Beta / best-effort and does not claim Codia 1:1.
- `services/backend-go/tools/codia_smoke_2img.sh` still passes the current non-regression floor.
- Bad cases can be saved as detector/eval data.

If this paused work is resumed for quality improvement, acceptance is:

- The improvement targets `m29_physical_evidence_or_codia_leaf` or detector candidate integration first.
- The smoke topAction improves or remains explainable.
- No runtime generation reads Codia golden JSON.
- No sample-specific names, text, fixed bbox, theme colors, file paths, or task IDs enter production logic.

## Documentation Updates

When Phase 0 lands, update:

- `docs/index.md`
- `docs/engineering/current-mainline-code-map.md`

These docs must state that the Codia analyzer is a new validation foundation and that old Go M29 VisualTree remains legacy/diagnostic until the role-aware compiler path replaces it.
