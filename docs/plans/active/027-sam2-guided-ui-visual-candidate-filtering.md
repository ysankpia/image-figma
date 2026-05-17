# M27 SAM2-Guided UI Visual Candidate Filtering Harness

## Summary

M27 adds a SAM2-guided visual candidate filtering harness. It consumes the current DSL, original PNG bytes and existing M20/M22/M23/M24/M25 icon facts, runs optional local SAM2 automatic mask generation, filters masks through the same text/cover/candidate/existing-icon/exclusion gates, and writes a report plus debug overlay.

M27 is not visible replay. It does not modify DSL, does not append DSL meta, does not crop icon assets, does not generate transparent PNGs, and does not feed Renderer. Its output is evidence for M28 candidate-pool merge.

## Key Changes

- Adds `backend/app/sam_visual_candidate.py`.
- Adds `backend/storage/sam_visual_candidates/{taskId}.json`.
- Adds `backend/storage/assets/{taskId}/debug/sam_visual_candidate_overlay.png`.
- Adds `GET /api/tasks/{taskId}/sam-visual-candidates`.
- Adds SQLite table `sam_visual_candidate_results`.
- Adds asset role `asset_sam_visual_candidate_overlay`.
- Adds smoke script `backend/scripts/run_m27_sam_visual_smoke.py`.

Default config:

```bash
SAM_VISUAL_CANDIDATE_ENABLED=false
SAM_VISUAL_CANDIDATE_MODEL_CFG=
SAM_VISUAL_CANDIDATE_CHECKPOINT=
SAM_VISUAL_CANDIDATE_DEVICE=auto
SAM_VISUAL_CANDIDATE_MAX_IMAGE_EDGE=1280
SAM_VISUAL_CANDIDATE_MAX_MASKS=300
SAM_VISUAL_CANDIDATE_MAX_CANDIDATES=120
SAM_VISUAL_CANDIDATE_MIN_CONFIDENCE=0.72
SAM_VISUAL_CANDIDATE_MIN_AREA=64
SAM_VISUAL_CANDIDATE_MAX_AREA_RATIO=0.12
SAM_VISUAL_CANDIDATE_TEXT_OVERLAP_IOU=0.10
SAM_VISUAL_CANDIDATE_EXISTING_ICON_IOU=0.50
SAM_VISUAL_CANDIDATE_OVERLAY_ENABLED=true
```

The local development backend installs SAM2 runtime in the `perception-sam2` uv dependency group. The checkpoint is stored outside repo-tracked files at `/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt`. No checkpoint is committed.

## Behavior

M27 only runs when `SAM_VISUAL_CANDIDATE_ENABLED=true`. Missing dependencies or checkpoint produce a skipped report with `SAM_VISUAL_PROVIDER_UNAVAILABLE`; upload still completes and DSL remains unchanged.

The document contract is `SamVisualCandidateDocument v0.1` with:

- `sam`: model/device/checkpoint status/runtime/raw mask count.
- `candidates`: accepted visual candidates with bbox, maskArea, kind, confidence, role hint and quality reasons.
- `blockedCandidates`: rejected masks with bbox and stable reason codes.
- `overlay`: optional debug overlay asset.
- `meta`: candidate/block/raw mask counts and summaries.

Accepted kinds are:

```text
business_icon_candidate
component_candidate
image_candidate
button_candidate
card_candidate
nav_candidate
text_like
unknown_visual
```

Blocking rules cover text/cover/candidate_text overlap, existing M20/M22/M23/M24/M25 icon duplicate, status bar, header title, banner/illustration, bed map, text strokes, lines, borders, background-like masks, whole button/card backgrounds, invalid bbox, too-small mask and low confidence.

## API

`GET /api/tasks/{taskId}/sam-visual-candidates`:

- task missing -> `TASK_NOT_FOUND`.
- result missing -> `SAM_VISUAL_CANDIDATE_NOT_FOUND`.
- result file missing -> `SAM_VISUAL_CANDIDATE_NOT_FOUND`.
- completed -> returns `sam`, `candidates`, `blockedCandidates`, `overlay`, `warnings`, `meta`.
- failed/skipped -> returns `status`, `warnings`, `meta`, `error`.

Errors:

```text
SAM_VISUAL_CANDIDATE_NOT_FOUND
SAM_VISUAL_CANDIDATE_FAILED
SAM_VISUAL_CANDIDATE_VALIDATION_FAILED
SAM_VISUAL_PROVIDER_UNAVAILABLE
```

## Validation And Tests

Validation checks document version/status, unique ids, bbox bounds, enum values, non-negative areas, meta summaries, overlay file existence and overlay asset id.

Regression constraints:

- No new `root.children`.
- No changes to existing DSL elements.
- No changes to DSL `assets`.
- No DSL meta changes.
- No Renderer input changes.

Tests cover disabled default, missing result/file, missing checkpoint, missing dependency, mock mask filtering, overlay asset registration and DSL regression.

Required validation:

```bash
cd backend && uv run pytest
pnpm run check
git diff --check
```

Optional smoke:

```bash
cd backend
uv run python scripts/run_m27_sam_visual_smoke.py \
  --input-dir "/Users/luhui/Downloads/宿舍床位可视化选择系统_UI设计图/学生端/" \
  --checkpoint "/Volumes/WorkDrive/Models/sam2/sam2.1_hiera_tiny.pt"
```

The smoke script writes timestamped output if the target directory already exists, preserving earlier evidence.
