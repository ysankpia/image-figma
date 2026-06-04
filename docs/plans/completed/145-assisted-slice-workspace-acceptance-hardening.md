# 145 Assisted Slice Workspace Acceptance Hardening

Status: completed

## Summary

Harden the assisted slice workspace from "usable UI" into a repeatable acceptance surface:

```text
images
-> candidates.v1.json
-> review_state.v1.json
-> manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

`manual_slices.v1.json` remains the delivery truth source. `review_state.v1.json` remains workbench state only.

## Scope

- Add a dedicated slice workspace acceptance script.
- Add a Makefile entry for the script.
- Add regression tests for empty preview, review-state recovery, selected asset count consistency, and exported clone cleanup.
- Record acceptance outputs in a Markdown and JSON report under the caller-provided output directory.
- Fix only P0/P1 defects found by acceptance.

## Non-Goals

- Do not introduce React, Vue, or a frontend build system.
- Do not change the candidate generation algorithm.
- Do not restore full automatic ownership as the product judge.
- Do not make YOLO a final owner.
- Do not default to transparent export.

## Required Validation

```bash
cd services/pencil-python-backend
uv run pytest -q tests/test_api.py
make check
make slice-acceptance \
  IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png \
  OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-145/tencent-comic
git diff --check
git status --short --branch
```

Batch sample validation should use:

```bash
cd services/pencil-python-backend
uv run python scripts/slice_workspace_acceptance.py \
  --base-url http://127.0.0.1:8100 \
  --input "/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages" \
  --input "/Users/luhui/Downloads/dorm_selection_ui_assets 2" \
  --out /Volumes/WorkDrive/pencil-exports/slice-acceptance-145/batch
```

## Implementation Summary

Implemented a repeatable acceptance surface for the assisted slice workspace:

- Added `scripts/slice_workspace_acceptance.py`.
- Added `make slice-acceptance`.
- Added API regressions for empty export preview, review-state recovery, selected asset/contact-sheet count consistency, and clone cleanup after export.
- Updated Pencil backend README and API reference with the new acceptance command.

The acceptance script creates slice projects through `/api/pencil/slice-projects`, saves `manual_slices.v1.json`, persists `review_state.v1.json`, generates export preview, exports both ZIPs, verifies `.pen` visible image refs, and writes both Markdown and JSON reports under the caller-provided output directory.

## Completion Evidence

Unit/API validation:

```text
cd services/pencil-python-backend
uv run pytest -q tests/test_api.py tests/test_build_deploy_bundle.py
18 passed, 2 warnings
```

Full backend validation:

```text
cd services/pencil-python-backend
make check
34 passed, 2 warnings
```

Single complex image acceptance:

```text
make slice-acceptance IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-145/tencent-comic
sliceWorkspaceAcceptance=ok
```

Report:

```text
/Volumes/WorkDrive/pencil-exports/slice-acceptance-145/tencent-comic/acceptance_report.md
sample_01_腾讯动漫_018_1440 passed
pages=1 candidates=63 selected=3 rejected=1 preview=3 exported=3 pngs=3 badRefs=0 missingRefs=0
```

Batch acceptance:

```text
uv run python scripts/slice_workspace_acceptance.py --base-url http://127.0.0.1:8100 --input "/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages" --input "/Users/luhui/Downloads/dorm_selection_ui_assets 2" --out /Volumes/WorkDrive/pencil-exports/slice-acceptance-145/batch
sliceWorkspaceAcceptance=ok
```

Report:

```text
/Volumes/WorkDrive/pencil-exports/slice-acceptance-145/batch/acceptance_report.md
sample_01_01_UI_Pages passed pages=6 candidates=776 selected=18 rejected=1 preview=18 exported=18 pngs=18 badRefs=0 missingRefs=0
sample_02_dorm_selection_ui_assets_2 passed pages=6 candidates=68 selected=11 rejected=1 preview=11 exported=11 pngs=11 badRefs=0 missingRefs=0
```

Browser smoke:

```text
GET /api/pencil/slice-projects/workspace rendered project cards
cardCount=15
hasCreateForm=true
hasReviewLink=true
hasProjectZipLink=true
hasAssetsZipLink=true
screenshot=/Volumes/WorkDrive/pencil-exports/slice-acceptance-145/workspace-smoke.png
```
