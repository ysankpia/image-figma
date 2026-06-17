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
GET    /api/me
GET    /api/billing/plans
POST   /api/billing/orders
POST   /api/billing/webhooks/xpay
GET    /api/admin/overview
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

- `/api/health`, `/api/auth/session`, `/api/auth/sign-up`, `/api/auth/sign-in`, `/api/auth/sign-out`, `/api/billing/plans`, and `/api/billing/webhooks/xpay` are public or session-discovery routes. The webhook route is public only because the provider cannot send a session cookie; it must verify the provider signature before fulfillment.
- `/api/me`, project APIs, source image download, slice preview, assets zip download, project zip download, AI boxes, and exports require an authenticated session.
- `/api/admin/overview` requires an authenticated admin user.
- Every project-scoped route must authorize through `projects.user_id`; unguessable project ids are not an authorization boundary.
- Browser requests should normally go through Next.js same-origin `/api` rewrite so the `slice_studio_session` cookie is first-party.

Saved projects, pages, and slices are the live truth source. Export reads persisted slices and original source images; it must not crop from browser thumbnails, canvas state, AI raw output, or OCR/M29 evidence.

AI boxes are a calculation result from `/ai-boxes`. The route does not write database state. The Review Workbench converts accepted boxes into ordinary `SliceRecord` entries and saves them through `PUT /api/projects/:projectId/slices`.

AI boxes consume AI entitlement and write a `usage_events` row before provider execution starts.

Export routes consume export entitlement and write a `usage_events` row before ZIP materialization starts.

Project creation checks the current user's project quota. Page upload and page replacement check per-project page count plus account storage quota before writing source files. `/api/me` returns project count, page count, and current original-image storage bytes for the account billing surface.

`POST /api/billing/orders` creates a provider-neutral local `payment_orders` row. When XPay env vars are configured, it also returns a checkout URL built from the local order id. Creating the order never grants entitlement.

`POST /api/billing/webhooks/xpay` accepts XPay / 易支付 style payment notifications, verifies the MD5 signature server-side, writes a raw `payment_events` row, and marks the order paid only for verified success events. Paid orders update the user's entitlement from the local plan table. Forged callbacks must return `fail` and must not grant entitlement.

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
