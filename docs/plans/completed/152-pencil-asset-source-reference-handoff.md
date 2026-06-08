# 152 Pencil Asset Source Reference Handoff

Status: completed

## Summary

Fix the slim Pencil asset backend handoff shape so exported `.pen` files are usable for review:

```text
source screenshot
-> Canvas Review selected image/icon slices
-> design.pen with source reference context
-> selected slices remain independent draggable assets
-> selected-assets.zip contains selected slices only
```

The current export places selected slices on a blank page. That proves the pipeline works, but it is not usable enough because the user cannot compare selected assets against the original UI. The fix is to include the source screenshot as an explicit reference layer in `design.pen` while keeping it out of `selected-assets.zip`.

## Scope

- Add a package-local source reference image to `project.zip`.
- Add a `source_reference` image-filled rectangle/frame to each page in `design.pen`.
- Keep selected image/icon slices as independent visible nodes above the reference.
- Mark the reference node with metadata so downstream tools can ignore it as a deliverable asset.
- Keep selected asset refs under `./assets/visible/...`.
- Keep source reference refs under `./assets/reference/...`.
- Update `.pen` ref validation so reference refs are allowed but not counted as selected assets.
- Browser-test the review page with the 525 test image.
- Use Pencil MCP to open exported `design.pen` and visually verify that the reference context and selected assets are visible.

## Non-Goals

- Do not change YOLO/M29/PSD-like/OCR candidate generation.
- Do not make the source screenshot the final selected asset.
- Do not add SVG/vectorization or transparent cutout.
- Do not restore automatic ownership reconstruction.
- Do not modify the old `services/pencil-python-backend` route.

## Acceptance

- `design.pen` opens with original source reference visible behind selected slices.
- Selected slices remain independent nodes at original source coordinates.
- `selected-assets.zip` contains only selected PNG assets and manifest.
- `project.zip` contains `assets/reference/page_XXXX/source.png`.
- `.pen` visible refs have `badRefs=0` and `missingRefs=0`.
- Browser review Canvas remains high-DPI crisp.
- Pencil MCP screenshot shows enough context to judge whether slices are correct.

## Completion Evidence

Implemented:

- `design.pen` now includes one `page_XXXX__source_reference` node per page.
- Source reference images are copied to `assets/reference/page_XXXX/source.png`.
- Selected image/icon slices remain independent nodes over the reference and use `./assets/visible/...`.
- `selected-assets.zip` excludes all source reference images.
- The `.pen` ref checker and acceptance script now allow `assets/reference` only for source reference refs.
- The Canvas Review page now handles high-DPI canvas rendering and narrow browser widths without collapsing the stage.

Validation:

```bash
cd services/pencil-asset-backend
make check
make asset-acceptance \
  IMAGE="/Users/luhui/Downloads/525测试/ChatGPT Image 2026年5月25日 18_42_52 1.png" \
  OUT=/Volumes/WorkDrive/pencil-exports/asset-reference-handoff-152/acceptance
```

Result:

```text
7 passed, 1 warning
sample_01_ChatGPT_Image_2026年5月25日_18_42_52_1: passed
pages=1 candidates=339 selected=3 reference=1 preview=3 exported=3 pngs=3 badRefs=0 missingRefs=0
```

Pencil MCP verification:

```text
/Volumes/WorkDrive/pencil-exports/asset-reference-handoff-152/project/design.pen
/Volumes/WorkDrive/pencil-exports/asset-reference-handoff-152/acceptance/sample_01_ChatGPT_Image_2026年5月25日_18_42_52_1/project-unzipped/design.pen
```

Both opened successfully. `snapshot_layout` showed one full-page source
reference plus independent selected slice nodes. `get_screenshot` showed the
source reference context visible behind selected assets.
