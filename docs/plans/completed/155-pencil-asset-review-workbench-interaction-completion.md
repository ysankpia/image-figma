# 155 Pencil Asset Review Workbench Interaction Completion

Status: completed

## Summary

Complete the slim Pencil asset backend Review page as a usable interaction workbench. The backend contracts are already in place:

```text
candidate = automatic suggestion layer
selected slice = user-confirmed delivery layer
manual_slices.v1.json = final export truth
review_state.v1.json = review UI state only
```

This step fixes the Review interaction layer only. It does not change YOLO, M29, PSD-like, OCR, export ZIP contracts, or Pencil `.pen` output shape.

## Scope

- Left click a candidate to create a selected asset.
- Right click a candidate to open a context menu instead of immediately hiding it.
- Right click overlapping selected/candidate areas to show separate selected-asset and candidate actions.
- Move and resize selected slices directly on the canvas.
- Show 8 resize handles on the active selected slice.
- Draw manual slices in draw mode with a high-contrast black/white draft box.
- Persist frame colors in `review_state.filters.colors`.
- Keep candidate rejection separate from selected asset deletion.

## Acceptance

- Candidate and selected-slice layers are visually distinct.
- Overlapping candidates use smallest-area hit priority.
- Selected slices have priority over candidates for selection, move, and resize.
- Hidden candidates persist in `review_state.v1.json` and never enter export.
- Selected slices persist in `manual_slices.v1.json` and drive all exports.
- Browser validation covers draw, add, right-click menu, hide, restore, move, resize, save, reload, and export.

## Validation

```bash
cd services/pencil-asset-backend
make check
make asset-acceptance \
  IMAGE="/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月25日 18_42_52 1.png" \
  OUT=/Volumes/WorkDrive/pencil-exports/asset-review-workbench-155/acceptance-525
cd ../..
git diff --check
git status --short --branch
```

## Completion Evidence

Implemented:

- Review Canvas now distinguishes automatic candidates from user-confirmed selected slices.
- Left click confirms a candidate as a selected asset.
- Right click opens a context menu with separate candidate and selected-asset actions.
- Selected slices can be moved and resized with 8 visible handles.
- Draw mode creates manual slices over any canvas region with a black/white draft box.
- Candidate hit testing uses smallest-area priority for overlapping candidates.
- Selected slices take interaction priority over candidates.
- Frame colors persist under `review_state.filters.colors`.
- Candidate hiding and selected asset deletion remain separate state changes.

Validation:

```bash
cd services/pencil-asset-backend
make check
make asset-acceptance \
  IMAGE="/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月25日 18_42_52 1.png" \
  OUT=/Volumes/WorkDrive/pencil-exports/asset-review-workbench-155/acceptance-525
cd ../..
git diff --check
```

Result:

```text
8 passed, 1 warning
assetAcceptance=ok
badRefs=0
missingRefs=0
```

Browser verification:

```text
Sample:
/Users/luhui/Library/Application Support/PixPin/Temp/PixPin_2026-06-09_02-51-06.png

Review URL:
http://127.0.0.1:8110/api/asset-projects/asset_20260608194100_0916e1376f/review

Observed:
candidateCount=17
left-click candidate created selected slice
right-click candidate menu showed add/hide actions
hidden candidate persisted after refresh
manual draw created selected slice
selected slice moved from x=98,y=98 to x=165,y=143
selected slice resized from 80x60 to 125x91
color persisted as #ff00ff
selectedAssetCount=2
refCheck badRefs=0 missingRefs=0
refresh preserved 2 selected slices and 1 hidden candidate
```
