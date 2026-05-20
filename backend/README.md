# Image-to-Figma Backend

FastAPI backend for the current Image-to-Figma preview pipeline.

The product runtime is now:

```text
Figma plugin
-> POST /api/upload-m30-preview
-> OCR + M29 evidence pipeline
-> M31 reconstruction diagnostics
-> M29.2 small overlay text miss audit
-> M30 materialized DSL
-> M37 hierarchy readiness diagnostics
-> GET /api/tasks/{taskId}/dsl
-> Renderer writes Figma nodes
```

The frozen pre-M29 upload chain has been removed from runtime source. `POST /api/upload` and the old task debug endpoints are not product contracts.

M31 is attached as a diagnostic side path after M29. It builds a reconstruction UI tree from source PNG, OCR JSON, and M29 `nodes.json`; it does not change M30 DSL or Figma output.

M29.2 is attached as an audit side path after M29.0.2. It looks for OCR-missed small overlay text proposals inside accepted image regions, writes `m29_2/small_overlay_text_candidates.json`, and does not change OCR, M29, M30, M31, M37, or Figma output.

OCR text evidence is preserved through M29/M31. M30 decides whether each text member is editable text or graphic text that must remain in fallback; graphic text is not erased and not redrawn with a generic Figma text layer.

M34.2 makes that M30 decision context-aware. Light OCR angle noise and broad image overlap can be overridden by generic geometry signals such as aligned text rows, compact overlay badges, metadata text clusters, and stable local background. The policy does not inspect business words or fixed screen coordinates.

M36 samples text foreground color from source PNG pixels for emitted editable text nodes. This replaces the old single dark default for colored and dark backgrounds while keeping preserved graphic text inside fallback.

M37 reads M31 and final M30 artifacts to produce a hierarchy readiness report. It does not create frames, move DSL nodes, or change Figma output.

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
GET  /api/tasks/{taskId}/m30-materialization
GET  /api/tasks/{taskId}/m31-reconstruction
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

`GET /api/tasks/{taskId}/m30-materialization` returns the M30 report summary, warnings, skipped items, output DSL path, optional debug preview path, and `stage_timings.json`.

The M30 report also exposes `textEditabilityDecisions`, `preservedGraphicTextItems`, and `reviewTextItems`. These fields explain why a text evidence item became an editable `m30_text_member` or stayed in fallback.

M34.3 adds `textSymbolLeakageDecisions` and summary counts for high-confidence leading OCR symbol leakage cleanup. It keeps OCR/M29/M31 evidence unchanged and only changes emitted M30 text content/bbox when source pixels show a projection gap.

M29.2 reports `small_overlay_text_candidates.json` for OCR-missed tiny overlay text proposals. The guard summary keeps `materializedTextCount=0`, `createdNewBBoxCount=0`, and `dslChanged=false`.

M30 text nodes also report `textForegroundColorSource` in node meta. The M30 report summary counts sampled foreground colors, contrast fallbacks, and hard fallback-to-default cases.

`GET /api/tasks/{taskId}/m31-reconstruction` returns M31 reconstruction summary metrics, warnings, review buckets, unit summaries, the full tree path, optional debug overlay path, and `stage_timings.json`. It does not return the full tree JSON.

## Current Pipeline

The upload preview pipeline runs:

```text
OCR
-> M29 visual primitive graph
-> M31 reconstruction diagnostics
-> M29.1 symbol fragment grouping
-> M29.0.2 text-masked media audit
-> M29.2 small overlay text proposal audit
-> M29.0.3 visual evidence normalization with lineage
-> M29.0.7 text/visual ownership gate
-> M29.0.4 visual object candidate audit with ownership routing
-> M29.0.5 text-aware visual object refinement
-> M30 evidence-grounded DSL materialization
-> M30.2 conservative text cover
-> M37 hierarchy readiness diagnostic
-> publish M30 image assets under /files/assets/{taskId}/m30/
```

It deliberately does not run old pre-M29 diagnostic stages, mixed/residual acceptance audits, fallback masking, Auto Layout, Figma Components, SVG/vectorization, or icon recovery.

M29.2 is audit/proposal only. It does not patch `ocr/ocr.json`, does not create M30 text nodes, and does not make small overlay text editable in this stage. Optional local crop OCR re-probe is controlled by `M29_SMALL_OVERLAY_TEXT_REPROBE_ENABLED=false`.

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

## M29.2 Small Overlay Text Audit

```bash
M29_SMALL_OVERLAY_TEXT_AUDIT_ENABLED=true
M29_SMALL_OVERLAY_TEXT_AUDIT_STRICT=false
M29_SMALL_OVERLAY_TEXT_REPROBE_ENABLED=false
M29_SMALL_OVERLAY_TEXT_MAX_CANDIDATES=12
M29_SMALL_OVERLAY_TEXT_UPSCALE_FACTOR=3
```

When enabled, `/api/upload-m30-preview` writes:

```text
storage/m30_1_uploads/{taskId}/m29_2/small_overlay_text_candidates.json
storage/m30_1_uploads/{taskId}/m29_2/small_overlay_text_candidates.md
```

`M30_PREVIEW_PROFILE=production` skips M29.2 overlay/crop PNGs. `M30_PREVIEW_PROFILE=development` writes the overlay and crop debug assets. M29.2 failures are optional by default; strict mode fails the task at `stage=m29_2_small_overlay_text_audit`.

M29.2 ranks candidates per accepted image before applying the global report cap. This keeps later image cards from being starved by earlier noisy image regions. Tiny overlay candidates with vertical component spread can remain proposals and record `baseline_spread_penalty`; this is still audit-only and does not materialize text.

## M29.3 Image Internal Overlay Ownership

```bash
M29_IMAGE_INTERNAL_OVERLAY_AUDIT_ENABLED=true
M29_IMAGE_INTERNAL_OVERLAY_AUDIT_STRICT=false
M29_IMAGE_INTERNAL_OVERLAY_MAX_OVERLAYS=12
```

M29.3 records parent-bound overlay evidence inside M29.0.2 accepted images. It writes:

```text
storage/m30_1_uploads/{taskId}/m29_3/image_internal_overlays.json
storage/m30_1_uploads/{taskId}/m29_3/image_internal_overlays.md
```

The stage binds each overlay to its accepted image parent, for example `sourceImageNodeId=m29_image_003` and `sourceM29NodeId=image_003`. It does not recognize text, does not rewrite OCR or M29 artifacts, and does not feed M30 materialization. Production skips overlay/crop PNGs; development writes them for inspection.

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
