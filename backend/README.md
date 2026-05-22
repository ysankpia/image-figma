# Image-to-Figma Backend

FastAPI backend for the current Image-to-Figma preview pipeline.

The product runtime is now:

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR + M29 evidence pipeline
-> M29.2 source-level UI physical graph
-> M29 Direct Replay experiment variant
-> M31 reconstruction diagnostics
-> M30 materialized DSL with raster layer deduplication
-> M39 content/chrome boundary classification
-> M37 hierarchy readiness diagnostics
-> M38 controlled hierarchy materialization
-> M39.1 unit structure readiness audit
-> GET /api/tasks/{taskId}/dsl
-> Renderer writes Figma nodes
```

The frozen pre-M29 upload chain has been removed from runtime source. `POST /api/upload` and the old task debug endpoints are not product contracts.

M31 is attached as a diagnostic side path after M29. It builds a reconstruction UI tree from source PNG, OCR JSON, and M29 `nodes.json`; it does not change M30 DSL or Figma output.

OCR text evidence is preserved through M29/M31. M30 decides whether each text member is editable text or graphic text that must remain in fallback; graphic text is not erased and not redrawn with a generic Figma text layer.

M34.2 makes that M30 decision context-aware. Light OCR angle noise and broad image overlap can be overridden by generic geometry signals such as aligned text rows, compact overlay badges, metadata text clusters, and stable local background. The policy does not inspect business words or fixed screen coordinates.

M36 samples text foreground color from source PNG pixels for emitted editable text nodes. This replaces the old single dark default for colored and dark backgrounds while keeping preserved graphic text inside fallback.

M30 materializes safe text, shapes, images, and composite media into DSL layers, then deduplicates raster pixels that would otherwise be drawn twice. Editable text remains a top layer; if it sits inside a copied media asset, M30.7 erases that text bbox from the copied asset only. M29.0.5 source assets are never modified.

M37 reads M31 and final M30 artifacts to produce a hierarchy readiness report. It does not create frames, move DSL nodes, or change Figma output.

M38 consumes the M37 safe direct-match bridge and rewrites the final DSL into transparent hierarchy groups. It only moves existing materialized M30 nodes, preserves absolute bboxes through parent-local coordinates, and does not change image assets or run new recognition.

M39 runs between M30 asset publishing and M37. It labels materialized M30 text, shape, visual image, and composite media nodes as `chrome` or `content` using generic relative geometry plus an optional ONNX proposer. The proposer is not a truth source: missing `numpy`, `Pillow`, `onnxruntime`, model file, bad output shape, or inference failure only records `modelSkippedReason` and falls back to rule-only classification.

M39.1 runs after M38 as a read-only unit structure readiness audit. It explains existing safe groups, blocked/micro units, product-card/banner/chrome/content candidates, and ONNX box candidates. It does not create visible nodes, move DSL nodes, edit assets, promote units, implement M40, or emit Codia schema.

On `experiment/m29-direct-replay`, the same upload task also writes an experimental M29 direct variant for Figma side-by-side comparison. Before replay it runs M29.2, which classifies source pixel ownership into editable text, preserved raster text, media, raster icons, stable UI shapes, and diagnostic-only objects. This variant reuses the same OCR and raw M29 evidence, writes `m29_direct/m29_direct_replay_dsl.json`, publishes assets under `/files/assets/{taskId}/m29_direct/`, and is available through `GET /api/tasks/{taskId}/m29-direct-dsl`. It does not replace the mainline `/dsl` result. M29.2/M29 direct failures are non-blocking; the mainline task can still complete and the variant endpoint then returns `M29_DIRECT_DSL_NOT_FOUND` only if the direct variant is unavailable.

## Run

```bash
uv sync
M30_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Test

```bash
uv run pytest -q
```

Focused current-chain checks:

```bash
uv run pytest \
  tests/test_m30_upload_pipeline.py \
  tests/test_evidence_grounded_dsl_materialization.py \
  tests/test_upload_flow.py \
  tests/test_config_env.py \
  tests/test_assets.py \
  tests/test_baidu_ocr.py -q
```

## Current API

```text
GET  /api/health
POST /api/upload-m30-preview
GET  /api/tasks/{taskId}
GET  /api/tasks/{taskId}/dsl
GET  /api/tasks/{taskId}/m29-direct-dsl
GET  /api/tasks/{taskId}/m30-materialization
GET  /api/tasks/{taskId}/m31-reconstruction
GET  /api/tasks/{taskId}/m39-boundary-classification
GET  /api/tasks/{taskId}/m39-1-unit-structure-readiness
GET  /api/assets/{assetId}
GET  /files/uploads/*
GET  /files/assets/*
```

`/api/upload-m30-preview` validates a PNG, stores it at `storage/uploads/{taskId}/original.png`, creates a `processing` task, and runs the M30 preview pipeline in a FastAPI background task. The initial response keeps the existing upload result shape with `taskId`, `status`, `stage`, `progress`, and file metadata.

On success, the task reaches:

```text
status = completed
stage = m30_completed
progress = 100
```

`GET /api/tasks/{taskId}/dsl` then returns `storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json`.

`GET /api/tasks/{taskId}/m29-direct-dsl` returns the experiment variant from `storage/m30_1_uploads/{taskId}/m29_direct/m29_direct_replay_dsl.json` plus report summary, warnings, output report path, and stage timings. It is used by plugin `Generate Compare`; it is not the default product DSL.

`GET /api/tasks/{taskId}/m30-materialization` returns the M30 report summary, warnings, skipped items, output DSL path, optional debug preview path, and `stage_timings.json`.

The M30 report also exposes `textEditabilityDecisions`, `preservedGraphicTextItems`, and `reviewTextItems`. These fields explain why a text evidence item became an editable `m30_text_member` or stayed in fallback.

M34.3 adds `textSymbolLeakageDecisions` and summary counts for high-confidence leading OCR symbol leakage cleanup. It keeps OCR/M29/M31 evidence unchanged and only changes emitted M30 text content/bbox when source pixels show a projection gap.

M30 text nodes also report `textForegroundColorSource` in node meta. The M30 report summary counts sampled foreground colors, contrast fallbacks, and hard fallback-to-default cases.

`GET /api/tasks/{taskId}/m31-reconstruction` returns M31 reconstruction summary metrics, warnings, review buckets, unit summaries, the full tree path, optional debug overlay path, and `stage_timings.json`. It does not return the full tree JSON.

`GET /api/tasks/{taskId}/m39-boundary-classification` returns M39 summary metrics, warnings, `modelSkippedReason`, classified node entries, output report path, and `stage_timings.json`. If M39 is disabled or no report exists, it returns `M39_BOUNDARY_CLASSIFICATION_NOT_FOUND`.

`GET /api/tasks/{taskId}/m39-1-unit-structure-readiness` returns M39.1 summary metrics, warnings, `modelSkippedReason`, candidate units, promotion hints, output report path, and `stage_timings.json`. If M39.1 is disabled or no report exists, it returns `M39_1_UNIT_STRUCTURE_READINESS_NOT_FOUND`.

## Current Pipeline

The upload preview pipeline runs:

```text
OCR
-> M29 visual primitive graph
-> M29.2 source-level UI physical graph
-> M29 direct replay variant
-> publish M29 direct assets under /files/assets/{taskId}/m29_direct/
-> M31 reconstruction diagnostics
-> M29.1 symbol fragment grouping
-> M29.0.2 text-masked media audit
-> M29.0.3 visual evidence normalization with lineage
-> M29.0.7 text/visual ownership gate
-> M29.0.4 visual object candidate audit with ownership routing
-> M29.0.5 text-aware visual object refinement
-> M30 evidence-grounded DSL materialization with accepted images, copied media text cleanup, and composite media
-> M30.2 conservative text cover
-> publish M30 image assets under /files/assets/{taskId}/m30/
-> M39 content-chrome boundary classification
-> M37 hierarchy readiness diagnostic
-> M38 controlled hierarchy materialization
-> M39.1 unit structure readiness audit
```

It deliberately does not run old pre-M29 diagnostic stages, mixed/residual acceptance audits, fallback masking, Auto Layout, Figma Components, SVG/vectorization, or icon recovery.

## OCR

Default OCR provider:

```bash
OCR_PROVIDER=fake
```

Optional Baidu PP-OCRv5 async OCR:

```bash
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In the M30 preview pipeline, OCR is required evidence. If the configured OCR provider fails, the task is marked `failed`; the backend does not create a fake completed M30 DSL.

Baidu OCR polygon metadata is kept as evidence:

```text
OCRBlock.meta.angle
OCRBlock.meta.polygon
```

M34.1 no longer drops rotated or graphic text before M29. Those text boxes remain auditable, then M30 decides whether they are safe to materialize as editable text.

## M30 Preview Profile

```bash
M30_PREVIEW_PROFILE=production   # default plugin preview runtime
M30_PREVIEW_PROFILE=development  # full diagnostics for local debugging
```

`production` keeps OCR JSON, structured M29/M30 JSON, M29.0.5 formal visual assets needed by M30, published renderer assets, M30 DSL/report, and `stage_timings.json`. It skips overlays, preview sheets, review/contact sheets, and M30 preview PNGs.

`development` preserves full diagnostic output. Single-stage M29/M30 scripts still default to development-style output through their own function defaults.

## M31 Upload Diagnostics

```bash
M31_UPLOAD_DIAGNOSTICS_ENABLED=true   # default
M31_UPLOAD_DIAGNOSTICS_STRICT=false   # default
```

When enabled, `/api/upload-m30-preview` writes:

```text
storage/m30_1_uploads/{taskId}/m31/m31_reconstruction_tree.json
storage/m30_1_uploads/{taskId}/m31/m31_reconstruction_tree_report.json
storage/m30_1_uploads/{taskId}/m31/m31_unit_fallback_assets/
```

`M30_PREVIEW_PROFILE=production` skips the M31 overlay. `M30_PREVIEW_PROFILE=development` also writes `m31_reconstruction_tree_overlay.png`.

M31 failures are optional by default: they write failed stage timing and an error log, then the pipeline continues to M30. With `M31_UPLOAD_DIAGNOSTICS_STRICT=true`, M31 failure marks the task failed at `stage=m31_reconstruction`.

M31.1.1 crops unit fallback assets from the already decoded `PngPixels`, so source PNG decode happens once per M31 run instead of once per reconstruction unit.

## M30 Materialization

M30 is the bridge from trusted M29.0.5 evidence into existing DSL v0.1. It consumes:

```text
textMembers
shapeCandidates
safe visualAssets
```

It does not consume mixed/future/audit-only evidence as visible DSL children. Those references may appear only in reports or DSL meta.

Safe visual assets are emitted as DSL `image` nodes, not `icon` nodes, because the current renderer does not implement an `icon` DSL type for this path.

M30 text materialization now has an explicit editability decision:

```text
editable_text
graphic_text_preserve_in_fallback
review_text
```

Only `editable_text` creates a visible `m30_text_member`. `graphic_text_preserve_in_fallback` and `review_text` stay in fallback and are reported; they are not included in fallback pixel erasure. This prevents stylized media text from being erased and redrawn as plain UI text while keeping OCR/M29/M31 evidence intact.

Each text editability decision also reports `metrics.preserveSignals` and `metrics.editableCounterSignals`. M34.2 uses those fields to show when a weak preserve signal, such as mild OCR rotation or image containment, was overridden by generic UI geometry.

M36 samples `style.color` for each emitted editable text node from source pixels:

```text
local dominant background
-> high-contrast bbox interior pixels
-> dominant foreground bucket
```

If no foreground pixels are available, it falls back to black or white based on background brightness. If sampling fails, it uses the configured default text color and records that fallback in node meta/report summary.

M30.2 adds conservative `m30_text_cover` shape nodes only when source PNG background sampling is stable and overlap risk is low. It does not hide fallback, mask fallback regions, or do inpainting.

M30.6 adds a narrow accepted-image materialization policy inside M30. Large `assetUse=image_asset` entries from M29.0.5 can become `m30_visual_asset` DSL image nodes when their text overlap is below `M30_ACCEPTED_IMAGE_MAX_TEXT_OVERLAP`, their bbox area is above `M30_ACCEPTED_IMAGE_MIN_AREA`, they have no high-risk text/boundary flags, and lineage resolves back to a raw M29 image node. This makes product/banner images draggable as independent Figma image layers. It is not OCR, not image-internal overlay recovery, not a `1/6` fix, not parent asset cleanup, and not M38 grouping.

M30.7 keeps those independent media layers clean. It fills editable text bboxes inside copied `m30_visual_asset`/`m30_composite_media_asset` PNGs with sampled local background, so dragging the text does not reveal baked duplicate text underneath. It also materializes large `decision=partially_separated` objects with `combinedAssetPath` as `m30_composite_media_asset`, which makes carousel/banner raster blocks draggable without pretending their internal art text is editable.

## M39 Content-Chrome Boundary Classification

```bash
M39_CONTENT_CHROME_CLASSIFICATION_ENABLED=true
M39_ONNX_PROPOSER_ENABLED=true
M39_ONNX_MODEL_PATH=/Volumes/WorkDrive/Models/model_fp16.onnx
```

M39 writes `meta.boundaryClassification` on materialized `m30_text_member`, `m30_shape_candidate`, `m30_visual_asset`, and `m30_composite_media_asset` nodes. It does not classify or move `fallback_region` or `original_reference`.

The built-in geometry rules cover top/bottom 12% full-width chrome and right-edge floating chrome, with a center-page safety override. The optional ONNX model can only propose chrome boxes; it cannot override the safety rules or become DSL truth. `M39_CONTENT_CHROME_CLASSIFICATION_ENABLED=false` skips the stage and returns the pipeline to M39-before behavior.

## M39.1 Unit Structure Readiness Audit

```bash
M39_1_UNIT_STRUCTURE_READINESS_ENABLED=true
M39_1_ONNX_UNIT_PROPOSER_ENABLED=true
M39_1_ONNX_MODEL_PATH=/Volumes/WorkDrive/Models/model_fp16.onnx
```

M39.1 writes:

```text
storage/m30_1_uploads/{taskId}/m39_1/unit_structure_readiness_report.json
```

It normalizes M37 safe/unsafe units into candidate units, derives diagnostic product-card/banner/chrome-shell/content-section candidates from existing M30/M39 evidence, and records future promotion hints. ONNX proposals are optional and remain diagnostic unless corroborated by rule evidence. M39.1 is not M40, not a visual fix, not a single-element hack, not a model truth source, and not a Codia adapter.

## M31 Reconstruction UI Tree

M31 starts the next abstraction layer:

```text
source PNG + OCR JSON + M29 nodes.json
-> reconstruction UI tree
-> reconstruction units with fallback crops
-> ownership/report/overlay
```

Run it manually:

```bash
uv run python scripts/run_m31_reconstruction_ui_tree.py \
  --source-image storage/uploads/{taskId}/original.png \
  --ocr-json storage/m30_1_uploads/{taskId}/ocr/ocr.json \
  --m29-nodes-json storage/m30_1_uploads/{taskId}/m29/nodes.json \
  --out storage/m31_runs/{taskId} \
  --profile development
```

M31.1 is a runtime diagnostic API, not a Renderer input. It deliberately does not consume M29.0.2/M29.0.3/M29.0.4/M29.0.5 or M30 DSL as structural truth. Those stages remain in the current product runtime until later M32-M34 stages replace their responsibility.

M31 unit fallback crops are cut from decoded source pixels. Do not route M31 fallback asset generation through compressed PNG crop helpers.

## M37 Hierarchy Readiness

M37 is a diagnostic bridge from M31 reconstruction units to M30 visible DSL nodes:

```text
M31 tree/report + final M30 DSL/report
-> m37_hierarchy_readiness_report.json
```

It writes:

```text
storage/m30_1_uploads/{taskId}/m37/m37_hierarchy_readiness_report.json
```

It records safe and unsafe future hierarchy candidates, mapping coverage, duplicate unit bboxes, micro units, relative coordinate violations, and fallback conflict risks.

M37 does not change `/api/tasks/{taskId}/dsl`, create visible frames, enable nested DSL, or feed Renderer. The report keeps `createdVisibleFrameCount=0` and `dslChanged=false`.

## M38 Controlled Hierarchy Materialization

M38 is the first production hierarchy stage:

```text
flat M30 DSL + M37 safe direct-match candidates
-> transparent DSL group containers
-> final nested m30_materialized_dsl.json
```

It writes:

```text
storage/m30_1_uploads/{taskId}/m38/hierarchy_materialization_report.json
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl_flat.json
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
```

`m30_materialized_dsl_flat.json` is written only when M38 changes the DSL. M38 does not run OCR, create new bboxes, create assets, erase pixels, recover icons, or change M37 artifacts.

Runtime switches:

```bash
M38_HIERARCHY_MATERIALIZATION_ENABLED=true
M38_HIERARCHY_MATERIALIZATION_STRICT=false
M38_HIERARCHY_MAX_CONTAINERS=8
```

## Storage

Runtime storage lives under `backend/storage/` by default and is not committed.

Current runtime directories:

```text
storage/uploads/
storage/assets/
storage/dsl/
storage/ocr/
storage/logs/
storage/m30_1_uploads/
storage/m31_runs/
```

Each upload task may now include:

```text
storage/m30_1_uploads/{taskId}/m31/
```

M30 preview tasks also publish renderer-fetchable image assets to:

```text
storage/assets/{taskId}/m30/
http://localhost:8000/files/assets/{taskId}/m30/...
```

## Removed Legacy Surface

M30.2.2 permanently removed the frozen pre-M29 backend chain from active source:

```text
POST /api/upload
old M8-M28 task debug endpoints
LEGACY_PRE_M29_UPLOAD_ENABLED
legacy app modules
legacy smoke scripts
legacy module tests
```

History remains in git, old ADRs, and `docs/reference/legacy/`. The active backend no longer provides an environment flag to revive the old path.
