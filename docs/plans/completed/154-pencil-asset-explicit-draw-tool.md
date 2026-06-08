# 154 Pencil Asset Explicit Draw Tool

Status: completed

## Summary

Fix the slim Pencil asset backend Review UI so manual drawing is an explicit tool, not a hidden fallback that only works on empty canvas space.

Current failure:

```text
candidate overlay is dense
-> user drags on a candidate region
-> UI treats it as candidate confirm/reject path
-> no visible manual draw box appears
```

The Review page must expose the same basic tool model as the older assisted workspace:

```text
Select
Draw Box
Pan
```

## Scope

- Add visible mode buttons to `services/pencil-asset-backend` Review header or side panel.
- Add a `toolMode` state with `select`, `draw`, and `pan`.
- In draw mode, dragging always creates a manual slice draft, even if candidates exist under the pointer.
- In select mode, left click confirms candidates and `Alt+click`/right click hides wrong candidates.
- In pan mode, drag pans the canvas.
- Keep Space/middle-button pan shortcut.
- Keep `manual_slices.v1.json` as export truth and `review_state.v1.json` as review state only.

## Non-Goals

- Do not change YOLO/M29/PSD-like/OCR candidate generation.
- Do not rebuild the old full assisted workspace.
- Do not add batch candidate box-select in this step.
- Do not change Pencil export output shape.

## Acceptance

- User can see a `画框` button.
- Clicking `画框` visibly marks draw mode active.
- Dragging over an existing candidate creates a white draft box instead of confirming the candidate.
- Mouseup creates a manual slice with `source: manual`.
- Saving persists that manual slice.
- Refresh shows the manual slice again.
- Candidate hide/recover behavior from 153 still works.

## Validation

```bash
cd services/pencil-asset-backend
make check
cd ../..
git diff --check
```

Browser smoke:

```text
Open a Review URL.
Click 画框.
Drag over an area that contains candidate boxes.
Confirm manual slice count increases and the newest slice has source=manual.
Save and reload.
Confirm manual slice persists.
```

## Completion Evidence

Implemented:

- The Review header now exposes `选择`, `画框`, and `拖动` tool buttons.
- `toolMode=draw` bypasses candidate hit testing and always starts a manual slice draft.
- `toolMode=pan` pans the canvas by drag.
- Existing Space, middle-button pan, candidate confirm, and candidate hide/recover behavior remain.
- Keyboard shortcuts are available when focus is outside form controls: `V` select, `B` draw, `H` pan.

Validation:

```bash
cd services/pencil-asset-backend
make check
cd ../..
git diff --check
```

Result:

```text
8 passed, 1 warning
```

Browser verification:

```text
Review URL:
http://127.0.0.1:8110/api/asset-projects/asset_20260608182918_2d6005070f/review

Clicked draw mode through setToolMode("draw").
Created a manual slice over an existing candidate region.
Newest slice:
source=manual
candidateIds=[]
bbox={x:57,y:651,width:80,height:60}
Save result selectedSliceCount=4.
Reload preserved the manual slice.
Cleanup removed the temporary manual slice and saved selectedSliceCount=3.
Console errors: none.
```
