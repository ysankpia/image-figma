# 153 Pencil Asset Review Candidate Correction

Status: completed

## Summary

Fix the slim Pencil asset backend review step so users can correct auto candidates directly:

```text
auto candidates
-> confirm good candidates
-> hide wrong candidates
-> draw missing slices manually
-> manual_slices.v1.json
-> project.zip + selected-assets.zip
```

`manual_slices.v1.json` remains the final export truth source. The new `review_state.v1.json` stores only workbench state such as rejected candidates and filters.

## Scope

- Add `review_state.v1.json` to `services/pencil-asset-backend`.
- Add `GET/PUT /api/asset-projects/{projectId}/review-state`.
- Let users hide wrong candidates with right click or `Alt+click`.
- Let users show and restore hidden candidates.
- Keep manual drawing and candidate confirmation behavior.
- Keep export reading only selected image/icon slices from `manual_slices.v1.json`.

## Non-Goals

- Do not change YOLO, M29, PSD-like, or OCR candidate generation.
- Do not rebuild the larger assisted slice workspace.
- Do not add SVG, transparent cutout, Codia-like tree, or Figma reconstruction.
- Do not store rejected candidates in `manual_slices.v1.json`.

## Acceptance

- New projects have a default review state.
- Existing projects missing `review_state.v1.json` recover a default state on read.
- A rejected candidate disappears from the canvas and stays hidden after refresh.
- Rejected candidates can be shown as gray dashed boxes and restored.
- Manual drawing still creates selected slices.
- Rejected candidates do not enter `selected-assets.zip`.
- `project.zip` and `selected-assets.zip` still pass ref and count checks.

## Validation

```bash
cd services/pencil-asset-backend
make check
make asset-acceptance \
  IMAGE="/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月25日 18_42_52 1.png" \
  OUT=/Volumes/WorkDrive/pencil-exports/asset-review-correction-153/acceptance
cd ../..
git diff --check
git status --short --branch
```

## Completion Evidence

Implemented:

- `review_state.v1.json` is created for new asset projects.
- Missing review state files are recovered on `GET review-state`.
- `GET/PUT /api/asset-projects/{projectId}/review-state` persist rejected candidate IDs.
- Review Canvas supports `Alt+click` and right click to hide wrong candidates.
- Hidden candidates persist after refresh, can be shown as gray dashed boxes, and can be restored per page.
- `Delete` and `Backspace` remove the active selected slice when focus is not inside a form control.
- Export continues to use only `manual_slices.v1.json`.

Validation:

```bash
cd services/pencil-asset-backend
make check
make asset-acceptance \
  IMAGE="/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月25日 18_42_52 1.png" \
  OUT=/Volumes/WorkDrive/pencil-exports/asset-review-correction-153/acceptance
```

Result:

```text
8 passed, 1 warning
sample_01_ChatGPT_Image_2026年5月25日_18_42_52_1: passed
pages=1 candidates=339 selected=3 reference=1 preview=3 exported=3 pngs=3 badRefs=0 missingRefs=0
```

Browser verification:

```text
Review URL: http://127.0.0.1:8110/api/asset-projects/asset_20260608182918_2d6005070f/review
Alt/right-click hide persisted page_0001__candidate_0001.
Refresh preserved rejectedCandidateIds.
Restore cleared rejectedCandidateIds and hiddenCandidateIds.
Console errors: none.
```
