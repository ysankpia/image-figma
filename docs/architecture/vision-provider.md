# Vision Provider

Vision provider is a candidate and review subsystem. It is not the final UI tree builder.

## Role

Vision models can help with:

- semantic labels for local image/icon/avatar/cover candidates;
- identifying missing visual objects from M29 evidence;
- suggesting candidate merges;
- suggesting candidate suppression;
- refining obviously wrong candidate roles;
- identifying region-level tags such as bottom navigation, card, top region, search field, or floating action region.

Vision models must not:

- generate final Figma trees;
- generate final Draft Runtime DSL;
- read Codia golden during generation;
- become bbox authority without physical evidence or explicit review reason;
- create Button/ListView/ActionBar/BottomNavigation as structural owners.

## Contracts

First-pass detector output:

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

Review decisions are inputs to Draft assembly. They are not final layers.

## Provider Configuration

Use provider-neutral environment variables:

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

Detector passes are independent crop/prompt/model calls. They should run concurrently with a bounded semaphore:

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

Vision can propose bbox, but Draft assembly should prefer M29/OCR bbox when available.

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
