# 144 Assisted Slice Project Workspace

Status: completed

## Summary

Move the assisted slice path from a single review page into a batch project workspace:

```text
images
-> candidates.v1.json
-> user-confirmed manual_slices.v1.json
-> project.zip + selected-assets.zip
```

The product truth source remains `manual_slices.v1.json`. Automatic evidence only creates candidates. This plan keeps the current plain HTML + Canvas implementation and does not introduce a frontend build chain.

## Scope

- Add a workspace entry page and project list API.
- Support project resume, rename, clone, and delete.
- Add review state for rejected candidates, filters, and last active page.
- Add candidate tiers and bulk candidate operations in the review page.
- Improve selected asset management with search, bulk delete, batch rename, kind/tag editing, and stable export metadata.
- Add export preview/contact sheet and clearer project vs selected-assets download links.

## Non-Goals

- Do not modify the Figma plugin.
- Do not restore Codia product routes.
- Do not modify `services/pencil-go`.
- Do not make YOLO a final owner/judge.
- Do not default to transparent export.
- Do not introduce React, Vue, or a frontend build system.

## Validation

Required commands:

```bash
cd services/pencil-python-backend
make check
git diff --check
git status --short --branch
```

Browser smoke:

```text
open /api/pencil/slice-projects/workspace
create or resume a project
bulk-select candidates
reject/restore candidates
edit selected asset metadata
generate export preview
export and download project.zip + selected-assets.zip
```

## Implementation Summary

Implemented the batch assisted-slice project workspace in `services/pencil-python-backend` without adding a frontend build chain.

The backend now exposes project indexing and management APIs:

```text
GET    /api/pencil/slice-projects
GET    /api/pencil/slice-projects/workspace
PUT    /api/pencil/slice-projects/{projectId}
POST   /api/pencil/slice-projects/{projectId}/clone
DELETE /api/pencil/slice-projects/{projectId}
GET    /api/pencil/slice-projects/{projectId}/review-state
PUT    /api/pencil/slice-projects/{projectId}/review-state
POST   /api/pencil/slice-projects/{projectId}/export-preview
GET    /api/pencil/slice-projects/{projectId}/export-preview/contact-sheet.png
GET    /api/pencil/slice-projects/{projectId}/export-preview/index.html
GET    /api/pencil/slice-projects/{projectId}/selected-assets.zip
```

The review page now supports candidate box selection, bulk add, bulk reject/restore, page-level filters, selected asset search, batch rename/delete, display names, tags, export preview, and separate project-package/resource-package download links.

`review_state.v1.json` stores only workbench state such as rejected candidates and last active page. `manual_slices.v1.json` remains the final export truth source.

Export now writes a contact sheet into the project ZIP resource kit and keeps `selected-assets.zip` focused on user-confirmed assets plus its manifest.

## Completion Evidence

Backend validation:

```text
cd services/pencil-python-backend
make check
34 passed, 2 warnings
```

Repository validation:

```text
git diff --check
clean
```

Browser smoke used:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
projectId: slice_20260604181136_712cd20cea
```

Smoke result:

```json
{
  "selected": 3,
  "rejected": 1,
  "previewAssets": 3,
  "exportedAssets": 3,
  "projectZipUrl": "/api/pencil/slice-projects/slice_20260604181136_712cd20cea/download.zip",
  "selectedAssetsZipUrl": "/api/pencil/slice-projects/slice_20260604181136_712cd20cea/selected-assets.zip"
}
```

Artifact check:

```text
project.zip exists
selected-assets.zip exists
resource-kit/contact-sheet.png exists
selected asset PNGs:
  page_0001/slice_0001.png
  page_0001/slice_0002.png
  page_0001/slice_0003.png
selected_manifest_assets=3
badRefs=0
missingRefs=0
```

Screenshot:

```text
/Volumes/WorkDrive/pencil-exports/assisted-slice-workspace-144-smoke.png
```
