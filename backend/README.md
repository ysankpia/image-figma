# Image-to-Figma Backend

Backend for the Image-to-Figma MVP. It accepts one PNG, stores local files, creates a completed task, builds deterministic region fallback DSL from real PNG dimensions, saves visual primitive candidates, saves OCR, DSL patch, text replacement candidates, uses UI-aware sampling to reduce text replacement false rejections, quality-gates visible replacements, builds text-to-container binding reports, builds component structure reports, annotates DSL elements with component structure metadata, builds layer separation candidate reports, builds local asset slice candidate reports, builds icon candidate crop reports, builds icon coverage audit reports, builds region-guided icon gap candidate reports, builds icon placement plan reports, optionally runs visible icon fallback replay, builds region-guided business icon candidate reports, optionally runs visual perception provider benchmark reports, and serves local asset URLs.

## Run

```bash
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Test

```bash
uv run pytest
```

## M8 Primitives

Default extraction uses the deterministic fake provider:

```bash
VISUAL_PRIMITIVE_PROVIDER=fake
```

Optional OpenAI smoke must be explicitly enabled:

```bash
VISUAL_PRIMITIVE_PROVIDER=openai OPENAI_API_KEY=... uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## OCR And Patch

Default OCR and patch harness:

```bash
OCR_PROVIDER=fake
DSL_PATCH_MODE=debug
```

Optional Baidu PP-OCRv5 async OCR smoke:

```bash
OCR_PROVIDER=baidu_ppocrv5 \
BAIDU_PADDLE_OCR_TOKEN=... \
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Debug endpoints:

```bash
curl http://localhost:8000/api/tasks/{taskId}/ocr
curl http://localhost:8000/api/tasks/{taskId}/dsl-patch
curl http://localhost:8000/api/tasks/{taskId}/text-replacements
curl http://localhost:8000/api/tasks/{taskId}/text-bindings
curl http://localhost:8000/api/tasks/{taskId}/component-structures
curl http://localhost:8000/api/tasks/{taskId}/component-annotations
curl http://localhost:8000/api/tasks/{taskId}/layer-separation-candidates
curl http://localhost:8000/api/tasks/{taskId}/asset-slice-candidates
curl http://localhost:8000/api/tasks/{taskId}/icon-candidates
curl http://localhost:8000/api/tasks/{taskId}/icon-coverage-audit
curl http://localhost:8000/api/tasks/{taskId}/icon-gap-candidates
curl http://localhost:8000/api/tasks/{taskId}/icon-placement-plan
curl http://localhost:8000/api/tasks/{taskId}/icon-visible-fallback
curl http://localhost:8000/api/tasks/{taskId}/icon-business-candidates
curl http://localhost:8000/api/tasks/{taskId}/perception-benchmark
```

Visible text replacement is debug-only by default:

```bash
TEXT_REPLACEMENT_MODE=debug
```

Use `TEXT_REPLACEMENT_MODE=apply` only for local smoke. It keeps fallback regions and blocks only high-risk accepted replacements; medium-risk replacements are applied with caution metadata. M14 UI-aware sampling is enabled by default with `TEXT_REPLACEMENT_UI_AWARE_SAMPLING=true` and records the sampling strategy used for badge, legend, outline button, card/tip, and bottom nav text. `GET /api/tasks/{taskId}/text-replacements` explains accepted, rejected, applied, blocked, and strategy decisions.

M15 text binding is enabled by default:

```bash
TEXT_BINDING_ENABLED=true
TEXT_BINDING_MIN_CONFIDENCE=0.70
```

It writes `backend/storage/text_bindings/{taskId}.json` and exposes `GET /api/tasks/{taskId}/text-bindings`. Binding reports connect OCR/replacement text to visual primitives or inferred UI containers for M16. They do not change Figma-visible output or write inferred containers back into visual primitives. The current inferred roles include page header, hero profile, activity card, summary stat card, primary/outline button, shortcut/preview/tip card, legend group, and bottom nav item; button binding requires action-style evidence and should not absorb summary/stat text.

M16 component structure is enabled by default:

```bash
COMPONENT_STRUCTURE_ENABLED=true
COMPONENT_STRUCTURE_MIN_CONFIDENCE=0.70
```

It writes `backend/storage/component_structures/{taskId}.json` and exposes `GET /api/tasks/{taskId}/component-structures`. Structure reports aggregate M15 containers and bindings into component candidates and layout groups for M17+. They do not change Figma-visible output, do not create Figma Component/Instance nodes, do not delete fallback regions, and do not write inferred components back into visual primitives.

M17 component annotation is enabled by default:

```bash
COMPONENT_ANNOTATION_ENABLED=true
COMPONENT_ANNOTATION_LAYER_NAMING=true
COMPONENT_ANNOTATION_MIN_CONFIDENCE=0.70
```

It writes `backend/storage/component_annotations/{taskId}.json` and exposes `GET /api/tasks/{taskId}/component-annotations`. Annotation reports connect M16 components/groups back to existing DSL elements and update DSL `name`/`meta` only. They do not slice images, create Figma groups/components, delete fallback regions, change visible layout/style/content, or reconstruct icons, circles, triangles, stars, or complex shapes.

M18 layer separation candidates are enabled by default:

```bash
LAYER_SEPARATION_ENABLED=true
LAYER_SEPARATION_MIN_CONFIDENCE=0.70
LAYER_SEPARATION_SIMPLE_FILL_TOLERANCE=24
LAYER_SEPARATION_MAX_COMPONENT_AREA_RATIO=0.35
```

It writes `backend/storage/layer_separation_candidates/{taskId}.json` and exposes `GET /api/tasks/{taskId}/layer-separation-candidates`. M18 consumes M14 replacement evidence plus M15/M16/M17 structure facts to decide whether each component should later use shape + editable text, image slice with simple fill candidate, future repair, embedded text, or no text. M18 only updates top-level DSL meta. It does not slice images, generate filled PNGs, delete fallback regions, change existing DSL elements, create Figma groups/components, do AI inpainting, introduce Pillow/OpenCV, or reconstruct icons and complex shapes.

M19 local asset slice candidates are enabled by default:

```bash
ASSET_SLICE_ENABLED=true
ASSET_SLICE_MAX_CANDIDATES=24
ASSET_SLICE_MIN_CONFIDENCE=0.70
ASSET_SLICE_MAX_AREA_RATIO=0.25
ASSET_SLICE_GENERATE_FILLED=true
```

It writes `backend/storage/asset_slice_candidates/{taskId}.json`, emits PNGs under `backend/storage/assets/{taskId}/slices/`, and exposes `GET /api/tasks/{taskId}/asset-slice-candidates`. M19 consumes M18 layer separation candidates and only slices low-risk component roles that are suitable for future image-slice replacement. It can generate original slice PNGs plus solid-color filled slice PNGs for simple fill candidates. M19 only updates top-level DSL meta and never adds those experimental slices to DSL `assets`, so Figma-visible output stays identical to M18. It does not delete fallback regions, create Figma groups/components, do AI inpainting, introduce Pillow/OpenCV, or reconstruct icons and complex shapes.

M20 icon candidates are enabled by default:

```bash
ICON_CANDIDATE_ENABLED=true
ICON_CANDIDATE_MIN_CONFIDENCE=0.70
ICON_CANDIDATE_MAX_CANDIDATES=64
ICON_CANDIDATE_MIN_SIZE=8
ICON_CANDIDATE_MAX_SIZE=96
ICON_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_CANDIDATE_MAX_COMPONENT_AREA_RATIO=0.20
```

It writes `backend/storage/icon_candidates/{taskId}.json`, emits PNGs under `backend/storage/assets/{taskId}/icons/`, and exposes `GET /api/tasks/{taskId}/icon-candidates`. M20 consumes M15-M17 structure/index facts plus local PNG pixels to find high-confidence small icon bboxes inside components, then crops icon PNG candidates with the standard-library PNG tools. M20 only updates top-level DSL meta and never adds those icon assets to DSL `assets`, so Figma-visible output stays identical to M19. It does not do SVG/icon semantic recognition, icon library matching, visible icon replacement, AI inpainting, Pillow/OpenCV, or complex shape reconstruction.

M21 icon coverage audit is enabled by default:

```bash
ICON_COVERAGE_AUDIT_ENABLED=true
ICON_COVERAGE_OVERLAY_ENABLED=true
ICON_COVERAGE_MISSED_HINTS_ENABLED=true
ICON_COVERAGE_MIN_HINT_CONFIDENCE=0.60
ICON_COVERAGE_MAX_MISSED_HINTS=80
ICON_COVERAGE_FOREGROUND_DISTANCE=32
```

It writes `backend/storage/icon_coverage_audits/{taskId}.json`, emits a debug overlay at `backend/storage/assets/{taskId}/debug/icon_coverage_overlay.png`, and exposes `GET /api/tasks/{taskId}/icon-coverage-audit`. M21 consumes M20 icon candidates, M19 slice candidates, current DSL, and local PNG pixels to report placement readiness and missed icon hints. M21 only updates top-level DSL meta and never adds overlay or icon assets to DSL `assets`, so Figma-visible output stays identical to M20. It does not put M20 icons on canvas, delete fallback, do SVG/icon semantic recognition, icon library matching, AI inpainting, Pillow/OpenCV, or complex shape reconstruction. The overlay only draws colored bbox rectangles; labels live in JSON.

M22 icon gap candidates are enabled by default:

```bash
ICON_GAP_CANDIDATE_ENABLED=true
ICON_GAP_CANDIDATE_MIN_CONFIDENCE=0.72
ICON_GAP_CANDIDATE_MAX_CANDIDATES=48
ICON_GAP_CANDIDATE_MIN_SIZE=8
ICON_GAP_CANDIDATE_MAX_SIZE=80
ICON_GAP_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_GAP_CANDIDATE_RETRY_PADDING=12
ICON_GAP_CANDIDATE_EDGE_CLIP_TOLERANCE=3
ICON_GAP_CANDIDATE_OVERLAY_ENABLED=true
```

It writes `backend/storage/icon_gap_candidates/{taskId}.json`, emits PNGs under `backend/storage/assets/{taskId}/icons_gap/`, emits a debug overlay at `backend/storage/assets/{taskId}/debug/icon_gap_overlay.png`, and exposes `GET /api/tasks/{taskId}/icon-gap-candidates`. M22 consumes M21 missed icon hints and a few region-guided probes to crop reliable header, bottom-nav, shortcut, and trailing icon gaps. M22 only updates top-level DSL meta and never adds gap icons or overlays to DSL `assets`, so Figma-visible output stays identical to M21. It does not do global icon detection, Codia-style all-layer extraction, SVG/icon semantic recognition, icon library matching, visible icon replacement, AI inpainting, Pillow/OpenCV, or complex shape reconstruction.

M23 icon placement plan is enabled by default:

```bash
ICON_PLACEMENT_PLAN_ENABLED=true
ICON_PLACEMENT_PLAN_OVERLAY_ENABLED=true
ICON_PLACEMENT_PLAN_DEDUP_IOU=0.50
ICON_PLACEMENT_PLAN_TEXT_OVERLAP_IOU=0.10
ICON_PLACEMENT_PLAN_SLICE_OVERLAP_IOU=0.50
ICON_PLACEMENT_PLAN_MAX_PLACEMENTS=128
```

It writes `backend/storage/icon_placement_plans/{taskId}.json`, emits a debug overlay at `backend/storage/assets/{taskId}/debug/icon_placement_overlay.png`, and exposes `GET /api/tasks/{taskId}/icon-placement-plan`. M23 consumes M20 icon candidates, M22 gap icon candidates, M19 slice candidates and current DSL collision facts to produce a placement plan with dedupe, blocked, fallback-mask, slice-coordination and future DSL node hints. M23 only updates top-level DSL meta and never adds icon nodes or placement overlays to DSL `assets`, so Figma-visible output stays identical to M22. It does not crop new icons, put icons on canvas, remove fallback, do global icon detection, Codia-style all-layer extraction, SVG/icon semantic recognition, icon library matching, AI inpainting, Pillow/OpenCV, or complex shape reconstruction.

M24 visible icon fallback replay is disabled by default because it changes visible DSL/Figma output:

```bash
ICON_VISIBLE_FALLBACK_ENABLED=false
ICON_VISIBLE_FALLBACK_MAX_PLACEMENTS=12
ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE=0.85
ICON_VISIBLE_FALLBACK_MASK_PADDING=2
ICON_VISIBLE_FALLBACK_MAX_MASK_SIZE=96
ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE=28
ICON_VISIBLE_FALLBACK_ALLOWED_ROLES=nav_icon,header_nav_icon,header_action_icon,leading_icon
ICON_VISIBLE_FALLBACK_OVERLAY_ENABLED=true
```

When explicitly enabled, it writes `backend/storage/icon_visible_fallbacks/{taskId}.json`, emits a debug overlay at `backend/storage/assets/{taskId}/debug/icon_visible_fallback_overlay.png`, and exposes `GET /api/tasks/{taskId}/icon-visible-fallback`. M24 consumes only M23 placement plan items that already point to M20/M22 cropped icon assets. It appends `icon_fallback_cover` shape nodes and `visible_icon_fallback` image nodes, and appends only actually used icon assets to DSL `assets`. M24 does not handle missing icons, M21 missed hints, M22 blocked hints, new icon crop, global icon detection, Codia-style all-layer extraction, transparent PNG/SVG/icon semantic recognition, icon library matching, AI inpainting, Pillow/OpenCV, or complex shape reconstruction.

M25 region-guided business icon candidates are enabled by default because they do not change visible output:

```bash
ICON_BUSINESS_CANDIDATE_ENABLED=true
ICON_BUSINESS_CANDIDATE_MAX_CANDIDATES=80
ICON_BUSINESS_CANDIDATE_MIN_CONFIDENCE=0.70
ICON_BUSINESS_CANDIDATE_MIN_SIZE=8
ICON_BUSINESS_CANDIDATE_MAX_SIZE=96
ICON_BUSINESS_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_BUSINESS_CANDIDATE_RETRY_PADDING=12
ICON_BUSINESS_CANDIDATE_EDGE_CLIP_TOLERANCE=3
ICON_BUSINESS_CANDIDATE_OVERLAY_ENABLED=true
ICON_BUSINESS_BOTTOM_NAV_ENABLED=true
ICON_BUSINESS_PRIMARY_BUTTON_ENABLED=true
ICON_BUSINESS_SHORTCUT_CARD_ENABLED=true
ICON_BUSINESS_METRIC_CARD_ENABLED=true
ICON_BUSINESS_ROOM_CARD_ENABLED=true
ICON_BUSINESS_TRAILING_ENABLED=true
ICON_BUSINESS_TIP_INFO_ENABLED=true
```

It writes `backend/storage/icon_business_candidates/{taskId}.json`, emits PNGs under `backend/storage/assets/{taskId}/icons_business/`, emits a debug overlay at `backend/storage/assets/{taskId}/debug/icon_business_overlay.png`, and exposes `GET /api/tasks/{taskId}/icon-business-candidates`. M25 bypasses weak business component recognition by probing stable regions such as bottom nav, primary button trailing arrow, shortcut tile, metric card, room card, trailing icon, and tip/info zones. M25 only updates top-level DSL meta and never adds business icon assets to DSL `assets`, so Figma-visible output stays identical to M24/M23. It does not do visible replay, global icon detection, Codia-style all-layer extraction, illustration/avatar/building/bed-map extraction, SVG/icon semantic recognition, icon library matching, AI inpainting, Pillow/OpenCV, or complex shape reconstruction.

M26 visual perception provider benchmark is disabled by default because it is an evaluation layer:

```bash
PERCEPTION_BENCHMARK_ENABLED=false
PERCEPTION_BENCHMARK_PROVIDERS=current_rules,opencv
PERCEPTION_BENCHMARK_MAX_CANDIDATES_PER_PROVIDER=300
PERCEPTION_BENCHMARK_OVERLAY_ENABLED=true
PERCEPTION_OPENCV_ENABLED=false
PERCEPTION_OPENCV_IMPORT_NAME=cv2
PERCEPTION_SAM2_ENABLED=false
PERCEPTION_SAM2_MODEL_CFG=
PERCEPTION_SAM2_CHECKPOINT=
PERCEPTION_SAM2_DEVICE=auto
PERCEPTION_SAM2_MAX_IMAGE_EDGE=1280
PERCEPTION_SAM2_MAX_MASKS=300
PERCEPTION_UIED_ENABLED=false
PERCEPTION_UIED_COMMAND=
```

When explicitly enabled, it writes `backend/storage/perception_benchmarks/{taskId}.json`, emits provider overlays under `backend/storage/assets/{taskId}/debug/perception_overlay_*.png`, and exposes `GET /api/tasks/{taskId}/perception-benchmark`. M26 compares `current_rules`, optional OpenCV, optional SAM2 automatic masks, and optional UIED command adapter under one candidate contract. It does not modify DSL, does not append DSL meta, does not crop new icon assets, does not feed Renderer, and does not add OpenCV/SAM2/UIED as production dependencies. Local smoke evidence shows OpenCV is fast but noisy, SAM2 is slower but cleaner, and UIED is not worth vendoring beyond an external adapter.

M27 SAM2-guided visual candidate filtering is disabled by default because it needs the local SAM2 runtime and checkpoint:

```bash
SAM_VISUAL_CANDIDATE_ENABLED=false
SAM_VISUAL_CANDIDATE_MODEL_CFG=
SAM_VISUAL_CANDIDATE_CHECKPOINT=
SAM_VISUAL_CANDIDATE_DEVICE=auto
SAM_VISUAL_CANDIDATE_MAX_IMAGE_EDGE=960
SAM_VISUAL_CANDIDATE_MAX_MASKS=300
SAM_VISUAL_CANDIDATE_POINTS_PER_SIDE=8
SAM_VISUAL_CANDIDATE_POINTS_PER_BATCH=64
SAM_VISUAL_CANDIDATE_MAX_CANDIDATES=120
SAM_VISUAL_CANDIDATE_MIN_CONFIDENCE=0.72
SAM_VISUAL_CANDIDATE_MIN_AREA=64
SAM_VISUAL_CANDIDATE_MAX_AREA_RATIO=0.12
SAM_VISUAL_CANDIDATE_TEXT_OVERLAP_IOU=0.10
SAM_VISUAL_CANDIDATE_EXISTING_ICON_IOU=0.50
SAM_VISUAL_CANDIDATE_OVERLAY_ENABLED=true
```

When explicitly enabled, it writes `backend/storage/sam_visual_candidates/{taskId}.json`, emits `backend/storage/assets/{taskId}/debug/sam_visual_candidate_overlay.png`, and exposes `GET /api/tasks/{taskId}/sam-visual-candidates`. M27 runs SAM2 automatic masks and filters them against visible text, text covers, hidden candidate text, existing M20/M22/M23/M24/M25 icon bboxes, status/header/illustration/bed-map exclusion zones, and line/border/background-like masks. The SAM2 runtime is cached per checkpoint/config/device inside the backend process; `points_per_side=8` and `max_image_edge=960` are the default UI-bbox benchmark settings. M27 does not modify DSL, does not append DSL meta, does not crop new icon assets, does not generate transparent PNG, and does not feed Renderer. The local development checkpoint is kept outside tracked files at `/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt`.

M28 single-image SAM2 UI visual extraction is a script-only evidence harness, not an upload stage:

```bash
cd backend
uv run python scripts/run_m28_single_visual_extraction.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --checkpoint "/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt" \
  --output-dir "storage/m28_single_visual_extraction"
```

It writes `icons/*.png`, `images/*.png`, `controls/*.png`, `m28_visual_extraction.json`, `m28_visual_extraction_overlay.png`, and `m28_visual_extraction_preview_sheet.png`. M28 treats SAM2 masks as proposals, first protects whole image assets such as hero/product/supplier images, then extracts UI icons and controls while blocking text, numeric labels, image-internal fragments, line/background/card fragments and status bar. It does not modify DSL, does not add assets to DSL, does not call Renderer, does not do visible replay, and does not enter batch processing.

M29 visual primitive graph is also a script-only evidence harness, not an upload stage and not a replacement for the M8 `/primitives` API:

```bash
cd backend
uv run python scripts/run_m29_visual_primitive_graph.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --output-dir "storage/m29_visual_primitive_graph"
```

It writes `nodes.json`, `preview_sheet.png`, `assets/images/*.png`, `assets/symbols/*.png`, and debug overlays under `overlays/`. M29 separates decoded PNG pixels into `text`, `shape`, `image`, `symbol`, and `unknown` primitive nodes with metrics and reasons. It keeps image detection conservative, creates protection zones only for high-confidence image primitives, and runs symbol detection only on remaining foreground. M29 does not modify DSL, does not write database rows, does not expose an API, does not call Renderer, does not use SAM2/OpenCV/OCR providers by default, and does not migrate the existing M8 `VisualPrimitiveDocument` contract.
