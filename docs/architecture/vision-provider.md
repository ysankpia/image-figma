# Vision Provider

Vision/AI providers are candidate and review subsystems. In current Slice Studio, the only default provider-backed product feature is AI rectangular slice boxes under `server/ai-slice-boxes/`.

Providers are not final UI tree builders and do not bypass saved SliceRecord truth.

## Role

Current Slice Studio AI models can help with:

- proposing rectangular boxes for visual assets from compressed tiles;
- identifying cross-tile large assets through an overview review;
- returning confidence and short reasons for candidate boxes.

Historical Draft vision models can help with:

- semantic labels for local image/icon/avatar/cover candidates;
- identifying missing visual objects from M29 evidence;
- suggesting candidate merges;
- suggesting candidate suppression;
- refining obviously wrong candidate roles;
- identifying region-level tags such as bottom navigation, card, top region, search field, or floating action region.

Vision models must not:

- generate final Figma trees;
- generate final Draft Runtime DSL;
- write Slice Studio database state directly;
- read Codia golden during generation;
- become bbox authority without physical evidence or explicit review reason;
- create Button/ListView/ActionBar/BottomNavigation as structural owners.

## Contracts

Current Slice Studio output:

```text
/api/projects/:projectId/pages/:pageId/ai-boxes response
```

Historical first-pass detector output:

```text
ui_detector_candidates.v1.json
```

Second-pass review output:

```text
ui_candidate_review.v1.json
```

Review actions:

```text
promote_m29_candidate
suppress_vlm_candidate
refine_bbox
merge_candidates
keep_candidate
classify_semantic_tag
```

Slice Studio AI boxes become durable only when the frontend saves them as ordinary slices. Historical review decisions are inputs to Draft assembly. They are not final layers.

## Provider Configuration

Use Slice Studio provider-neutral environment variables for current AI boxes:

```text
SLICE_STUDIO_AI_SLICE_PROVIDER=openai_responses
SLICE_STUDIO_AI_SLICE_BASE_URL=https://api.openai.com
SLICE_STUDIO_AI_SLICE_MODEL=...
SLICE_STUDIO_AI_SLICE_API_KEY=...
SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY=4
SLICE_STUDIO_AI_SLICE_TILE_COUNT=6
```

Historical Draft vision variables:

```text
VISION_PROVIDER=openai-compatible
VISION_WIRE_API=responses
VISION_BASE_URL=https://api.openai.com
VISION_MODEL=...
VISION_API_KEY=...
VISION_DETECTOR_PASSES=layout,imageview,background,bottom_nav
VISION_DETECTOR_CONCURRENCY=3
VISION_TIMEOUT_SECONDS=90
VISION_STREAM=false
VISION_REVIEW_ENABLED=false
```

Provider, base URL, model id, and API key must never be hardcoded. Local credentials must stay in untracked env files.

## Multi-Pass Execution

Current Slice Studio AI uses tiled image requests plus optional overview review. Historical detector passes are independent crop/prompt/model calls. They should run concurrently with a bounded semaphore:

```text
default concurrency: 3
```

Requirements:

- deterministic output ordering after collection;
- per-pass timeout;
- per-pass error artifact;
- fallback to M29/OCR-only assembly when optional vision fails;
- no task-wide failure unless the request explicitly requires vision.

## BBox Authority

Vision can propose bbox. In Slice Studio, a proposed bbox is only a normal slice candidate until saved through the existing slice state. In historical Draft, assembly should prefer M29/OCR bbox when available.

Good pattern:

```text
M29 crop bbox + VLM semantic label -> RasterLayer with bboxAuthority=m29
```

Risky pattern:

```text
VLM bbox alone -> final visible layer
```

Use VLM-only boxes conservatively and preserve them as hints when physical support is weak.

## Prompt Boundary

Prompts should ask for candidates and review decisions, not page reconstruction.

Do not ask the model for:

```text
complete Figma hierarchy
complete Codia tree
final DSL
exact plugin node order
```

Ask for:

```text
visible UI candidates
semantic role labels
missing compact image/icon candidates
merge/suppress/refine decisions
short reasons
```

Current Slice Studio prompt strategy is recorded in [../reference/slice-studio-ai-slice-prompt-strategies.md](../reference/slice-studio-ai-slice-prompt-strategies.md).
