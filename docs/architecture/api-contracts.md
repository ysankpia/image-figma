# API Contracts

Current product runtime is Slice Studio at the repository root.

Development defaults:

```text
Next web:  http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
```

## Slice Studio API Surface

```text
GET    /api/health
GET    /api/auth/session
POST   /api/auth/sign-up
POST   /api/auth/sign-in
POST   /api/auth/sign-out
GET    /api/storage-download?token=...
GET    /api/ai-slice-settings
GET    /api/projects
POST   /api/projects
GET    /api/projects/:projectId
PATCH  /api/projects/:projectId
DELETE /api/projects/:projectId
POST   /api/projects/:projectId/pages
PATCH  /api/projects/:projectId/pages/order
PATCH  /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/replace
DELETE /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/ai-boxes
GET    /api/projects/:projectId/pages/:pageId/source
PUT    /api/projects/:projectId/slices
GET    /api/projects/:projectId/slices/:sliceId/preview.png
POST   /api/projects/:projectId/export-assets
GET    /api/projects/:projectId/assets.zip
POST   /api/projects/:projectId/export-project
GET    /api/projects/:projectId/project.zip
POST   /api/projects/:projectId/pages/:pageId/export-project
GET    /api/projects/:projectId/pages/:pageId/project.zip
```

## Contract Rules

Authentication rules:

- `/api/health`, `/api/auth/session`, `/api/auth/sign-up`, `/api/auth/sign-in`, and `/api/auth/sign-out` are public or session-discovery routes.
- Project APIs, source image download, slice preview, assets zip download, project zip download, AI boxes, exports, and signed storage downloads require an authenticated session or a valid short-lived signed download token.
- Every project-scoped route must authorize through `projects.user_id`; unguessable project ids are not an authorization boundary.
- Browser requests should normally go through Next.js same-origin `/api` rewrite so the `slice_studio_session` cookie is first-party.

Saved projects, pages, and slices are the live truth source. Export reads persisted slices and original source images; it must not crop from browser thumbnails, canvas state, AI raw output, or OCR/M29 evidence.

AI boxes are a calculation result from `/ai-boxes`. The route does not write database state. The Review Workbench converts accepted boxes into ordinary `SliceRecord` entries and saves them through `PUT /api/projects/:projectId/slices`.

AI boxes and export routes do not write a second proposal, usage, billing, or entitlement state. They execute only after project ownership checks pass.

OCR and M29 evidence only affect Pencil text overlays in `project.zip`. They must not modify saved slice boxes or visible raster asset ownership.

Delete project/page routes remove local project/page data. Do not call them from automation unless the user explicitly requests deletion or a test fixture owns the storage.

## AI Boxes Response

`POST /api/projects/:projectId/pages/:pageId/ai-boxes` returns short-lived boxes:

```json
{
  "ok": true,
  "pageId": "page_abc",
  "boxes": [
    {
      "bbox": { "x": 10, "y": 20, "width": 80, "height": 48 },
      "name": "icon",
      "confidence": 0.82,
      "reason": "standalone visual asset",
      "sourceTileId": "tile_001"
    }
  ],
  "diagnostics": {
    "tileCount": 6,
    "rawBoxCount": 20,
    "acceptedBoxCount": 12,
    "rejectedBoxCount": 8
  }
}
```

Returned boxes are not persistent proposals. They become durable only after the frontend saves them as normal slices.

## Export Contracts

`assets.zip` contains:

```text
originals/*
slices/*
manifest.json
project.json
```

`project.zip` contains:

```text
design.pen
manifest.json
project.json
assets/originals/*
assets/visible/remainders/*
assets/visible/slices/*
```

Visible refs inside `design.pen` must be package-local and must not reference absolute paths, debug artifacts, `source.png`, or `../`.

## Historical APIs

The old Pencil Python caller contract remains in [../reference/pencil-python-backend-api.md](../reference/pencil-python-backend-api.md). Use it only when explicitly maintaining `archive/legacy-code/services/pencil-python-backend`.

The old Go Draft Preview contract remains historical/deferred:

```text
POST /api/draft-preview
GET  /api/draft-preview/{taskId}
GET  /api/draft-preview/{taskId}/dsl
GET  /api/draft-preview/{taskId}/assets/{assetId}.png
```

Removed or historical product endpoints:

```text
POST /api/codia-preview
GET  /api/codia-preview/{taskId}
GET  /api/codia-preview/{taskId}/dsl
POST /api/upload-preview
GET  /api/tasks/{taskId}/dsl
```

Do not restore these as current product routes without a new active plan and validation contract.
