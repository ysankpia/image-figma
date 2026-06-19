# Slice Studio Frontend Function Inventory

This document is the current frontend handoff contract for redesign work. It is derived from the active `app/`, `components/`, `server/`, `shared/`, and database code. It is not a visual design brief.

Current product scope after plan 196 is user-only:

```text
home
-> login/register
-> owned projects
-> review workbench
-> save slices
-> AI-assisted boxes
-> assets.zip / project.zip / design.pen export
-> account settings
```

Do not add admin, billing, payment, entitlement, usage, order, quota, or XPay UI from older docs. Those surfaces are not in the current runtime.

## Routes

Current user-visible routes:

```text
/
/login
/register
/projects
/projects/:projectId/review
/settings
```

Removed routes:

```text
/billing
/admin
```

## `/` Home

Purpose:

- public product entry for Slice Studio;
- explain that the product turns UI screenshots/design images into reusable asset packages and editable Pencil handoff packages;
- route users to `/projects`, `/login`, or `/register`.

Function requirements:

- no authenticated API is required;
- can show product workflow and output artifacts;
- must not show live billing, admin, payment, or quota state.

## `/login`

Component:

```text
AuthFormCard mode="sign-in"
```

Fields:

```ts
email: string
password: string
showPassword: boolean
status: string
busy: boolean
```

Actions:

- toggle password visibility;
- submit credentials;
- on success, redirect to `/projects`;
- on failure, show server error.

API:

```text
POST /api/auth/sign-in
```

Request:

```ts
{ email: string; password: string }
```

Response:

```ts
{ user: { email: string; name: string } }
```

Auth:

- server writes the session cookie;
- development owner defaults are still shown only as login help:

```text
local@slicestudio.dev
slice-studio-local-owner
```

## `/register`

Component:

```text
AuthFormCard mode="sign-up"
```

Fields:

```ts
name: string
email: string
password: string
showPassword: boolean
status: string
busy: boolean
```

Actions:

- create account;
- on success, redirect to `/projects`;
- allow navigation back to `/login`.

API:

```text
POST /api/auth/sign-up
```

Request:

```ts
{ name: string; email: string; password: string }
```

Validation:

- `name`: non-empty;
- `email`: at least 3 characters;
- `password`: at least 8 characters.

Response:

```ts
{ user: { email: string; name: string } }
```

## `/projects`

Auth:

- protected route;
- unauthenticated users redirect to `/login`.

Main component:

```text
ProjectWorkspace
```

State:

```ts
projects: ProjectCardModel[]
name: string
status: string
query: string
filter: "recent" | "all" | "withSlices"
sortMode: "updated" | "name" | "pages"
viewMode: "grid" | "list"
editingProjectId: string | null
editingName: string
pendingDeleteProject: ProjectCardModel | null
createDialogOpen: boolean
account: { email: string; name: string } | null
```

Displayed project fields:

```ts
project.id
project.name
project.createdAt
project.updatedAt
project.pageCount
project.sliceCount
project.firstPage?.sourceUrl
project.firstPage?.displayName
project.firstPage?.originalName
project.firstPage?.width
project.firstPage?.height
```

Derived fields:

```ts
previewUrl: string | null
firstPageName: string | null
firstPageSize: string | null
```

Functions:

- load current session;
- load project cards;
- create project;
- rename project;
- delete project with confirmation;
- sign out;
- search by project name or first page name;
- filter recent/all/with slices;
- sort by updated time, name, or page count;
- switch grid/list view;
- open a project at `/projects/:projectId/review`;
- navigate to `/settings`.

APIs:

```text
GET    /api/auth/session
GET    /api/projects
POST   /api/projects
PATCH  /api/projects/:projectId
DELETE /api/projects/:projectId
POST   /api/auth/sign-out
```

Create project request:

```ts
{ name?: string }
```

Rename request:

```ts
{ name: string }
```

Explicit non-features:

- no billing entry;
- no admin entry;
- no visible quota or usage counters.

## `/projects/:projectId/review`

Auth:

- protected route;
- every API call must authorize through `projects.user_id`;
- this page is the main product workflow and must not be reduced to a demo.

Core records:

```ts
ProjectDetail.project
ProjectDetail.pages[]
PageRecord
SliceRecord[]
```

Core UI state:

```ts
activePageId: string | null
activeSliceId: string | null
selectedSliceIds: string[]
tool: "select" | "draw" | "pan"
saveState: "idle" | "saving" | "saved" | "error"
language: "zh" | "en"
scale: number
stagePosition: { x: number; y: number }
undoStack: unknown[]
bboxDraft: { x: string; y: string; width: string; height: string }
aiRunning: boolean
aiProgress: AiProgress | null
inspectorCollapsed: boolean
assetListCollapsed: boolean
assetSearch: string
cutModeFilter: "all" | "rect" | "subject" | "card"
assetSortMode: "order" | "name" | "area"
sliceColors: { normal: string; active: string }
```

Page fields:

```ts
id: string
projectId: string
pageIndex: number
originalName: string
displayName: string
width: number
height: number
sourceUrl: string
thumbnailUrl: string
slices: SliceRecord[]
```

Slice fields:

```ts
id: string
projectId: string
pageId: string
sliceIndex: number
name: string
kind: "image"
cutMode: "rect" | "subject" | "card"
bbox: { x: number; y: number; width: number; height: number }
selected: true
```

Canvas functions:

- upload one or more page images;
- load original image into the canvas;
- switch active page from page rail;
- drag page rail items to reorder pages;
- rename page with debounce;
- replace current page source image; replacing clears slices on that page;
- delete page;
- select, drag, and transform bbox in `select` mode;
- additive multi-select with Cmd/Ctrl-click and range multi-select with Shift-click;
- drag-create bbox in `draw` mode; minimum `8x8`;
- copy selected slices with `Cmd/Ctrl+C`;
- paste copied slices with `Cmd/Ctrl+V`;
- delete all selected slices with Delete/Backspace;
- nudge selected slices with arrow keys;
- nudge selected slices by a larger step with Shift+arrow;
- snap drag/resize commits to image edges and nearby slice edges;
- move stage in `pan` mode;
- zoom with buttons and `Cmd/Ctrl + wheel`;
- fit stage to viewport;
- focus active asset renaming with Enter or F2;
- save with `Cmd/Ctrl+S`;
- undo with `Cmd/Ctrl+Z`;
- reload project when file-level source operations cannot be undone locally.

Asset list functions:

- show all slices for the current page;
- search asset names;
- filter by cut mode;
- sort by order, name, or area;
- rename asset;
- selecting from the list centers the canvas on that slice;
- change asset cut mode;
- delete asset;
- open asset gallery/overview;
- show slice preview image.

Inspector functions:

- show page metadata: page order, size, display name, original name;
- rename page;
- replace page;
- delete page;
- edit active slice bbox numeric fields `X/Y/W/H`;
- bbox numeric fields use a local draft and commit on blur/Enter so partial typing does not save invalid geometry;
- edit active slice cut mode;
- edit normal and active bbox outline colors;
- persist color preferences in browser local storage.

AI functions:

- run AI-assisted boxes for current page;
- run AI-assisted boxes for all pages;
- AI provider settings are available from `/api/ai-slice-settings`;
- batch concurrency is returned by backend and clamped to `1..8` in frontend;
- merge AI results into normal unsaved slices;
- AI-generated slices default to `cutMode = "rect"`;
- local YOLO experimental provider may return `reason: "yolo:<ClassName>"`;
- default local YOLO class whitelist is `Image,BackgroundImage,Map,Icon,Modal,Drawer`; `Card` is intentionally not default because it tends to capture text/buttons/images as a container;
- AI progress UI tracks:

```ts
mode: "page" | "batch"
total: number
completed: number
failed: number
added: number
skipped: number
currentLabel: string
message: string
minimized: boolean
hidden: boolean
```

Export functions:

- export `assets.zip`;
- export full project package `project.zip / design.pen`;
- export current page `project.zip / design.pen`;
- full project package includes `project.json`, `manifest.json`, `design.pen`, original PNGs, visible remainder PNGs, and slice PNGs;
- download URL is returned by the export API and may be a signed `/api/storage-download?token=...` URL.

APIs:

```text
GET    /api/projects/:projectId
POST   /api/projects/:projectId/pages
PATCH  /api/projects/:projectId/pages/order
PATCH  /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/replace
DELETE /api/projects/:projectId/pages/:pageId
POST   /api/projects/:projectId/pages/:pageId/ai-boxes
GET    /api/projects/:projectId/pages/:pageId/source
GET    /api/projects/:projectId/pages/:pageId/thumbnail
PUT    /api/projects/:projectId/slices
GET    /api/projects/:projectId/slices/:sliceId/preview.png
POST   /api/projects/:projectId/export-assets
GET    /api/projects/:projectId/assets.zip
POST   /api/projects/:projectId/export-project
POST   /api/projects/:projectId/pages/:pageId/export-project
GET    /api/projects/:projectId/pages/:pageId/project.zip
GET    /api/projects/:projectId/project.zip
```

Upload requests:

```text
POST /api/projects/:projectId/pages
multipart field: files

POST /api/projects/:projectId/pages/:pageId/replace
multipart field: file
```

Save slices request:

```ts
{
  activePageId?: string | null
  pages: Array<{
    pageId: string
    slices: Array<{
      id: string
      name: string
      kind: "image"
      cutMode?: "rect" | "subject" | "card"
      bbox: { x: number; y: number; width: number; height: number }
      selected: true
    }>
  }>
}
```

## `/settings`

Auth:

- protected route;
- unauthenticated users redirect to `/login`.

Purpose:

- minimal account settings and browser-local Review Workbench preferences;
- no admin role display;
- no billing, payment, usage, quota, or entitlement copy.

Displayed fields:

```ts
user.email
user.name
user.status
```

Functions:

- show current account identity;
- show active/suspended status;
- set default Review Workbench cut mode: `rect`, `subject`, or `card`;
- set whether the Review Workbench right inspector starts collapsed;
- set whether the Review Workbench asset list starts collapsed;
- choose which bottom status bar items are visible: page size, zoom, save/task status;
- persist those workbench preferences in browser `localStorage`;
- sign out current session.

Local storage key:

```text
sliceStudio.workbenchPreferences.v1
```

Workbench preference shape:

```ts
{
  defaultCutMode: "rect" | "subject" | "card"
  inspectorCollapsed: boolean
  assetListCollapsed: boolean
  stageFooterItems: Array<"size" | "zoom" | "status">
}
```

APIs:

```text
GET  /api/auth/session
POST /api/auth/sign-out
```

No API is used for workbench preferences in the current runtime.

Future account functions may include password change, data export, and deletion request, but they are not in the current runtime.

## Shared Data Contracts

### ProjectSummary

```ts
{
  id: string
  name: string
  createdAt: string
  updatedAt: string
  pageCount: number
  sliceCount: number
}
```

### ProjectListItem

```ts
ProjectSummary & {
  firstPage: PageRecord | null
}
```

### PageRecord

```ts
{
  id: string
  projectId: string
  pageIndex: number
  originalName: string
  displayName: string
  width: number
  height: number
  sourceUrl: string
  thumbnailUrl: string
}
```

### SliceRecord

```ts
{
  id: string
  projectId: string
  pageId: string
  sliceIndex: number
  name: string
  kind: "image"
  cutMode: "rect" | "subject" | "card"
  bbox: { x: number; y: number; width: number; height: number }
  selected: true
}
```

### ProjectDetail

```ts
{
  project: ProjectSummary
  pages: Array<PageRecord & { slices: SliceRecord[] }>
}
```

### AiSliceBoxesResponse

```ts
{
  ok: true
  pageId: string
  boxes: Array<{
    bbox: { x: number; y: number; width: number; height: number }
    name?: string
    confidence?: number
    reason?: string
    sourceTileId: string
  }>
  diagnostics: {
    tileCount: number
    rawBoxCount: number
    acceptedBoxCount: number
    rejectedBoxCount: number
  }
}
```

### ExportManifest

```ts
{
  schema: "manual_ui_slices.v1"
  exportedAt: string
  project: ProjectSummary
  pages: Array<{
    pageId: string
    originalName: string
    displayName: string
    pageDirectory: string
    original: string
    width: number
    height: number
    slices: Array<{
      id: string
      name: string
      kind: "image"
      cutMode: "rect" | "subject" | "card"
      filename: string
      placement: { x: number; y: number; width: number; height: number }
      selected: true
    }>
  }>
}
```

## Backend Business Constraints

Auth:

- session cookie name is controlled by the backend;
- session discovery uses `GET /api/auth/session`;
- unauthenticated users cannot access projects, settings, review, source images, previews, AI boxes, or exports;
- suspended users cannot continue as current users;
- local bootstrap owner is ensured on API startup.

Projects:

- project ownership is bound to `projects.user_id`;
- project list only returns the current user's projects;
- project create/rename/delete requires the current user;
- page upload checks file type, single-file size, and batch size;
- uploaded images are normalized to PNG;
- replacing a page clears that page's slices;
- deleting a page reindexes `pageIndex`;
- saving slices is project-level full replacement, not partial patch;
- bbox values are clamped to page dimensions;
- slice ids cannot duplicate within a project.

Storage and downloads:

- new writes use user-scoped storage keys under `users/{userId}/projects/{projectId}/...`;
- legacy project-only storage paths can still be read for old local data;
- export APIs return download URLs;
- `/api/storage-download?token=...` resolves short-lived signed local storage tokens;
- exported `.pen` visible refs must be package-local.

AI and export:

- AI boxes are transient and become durable only through the normal slice save path;
- AI execution is controlled by provider config, not entitlement counters;
- assets and Pencil export are gated by saved slices and project ownership, not billing credits;
- export reads source images from storage, never from canvas thumbnails.

## API Surface

Current user-side API:

```text
GET    /api/health
GET    /api/storage-download?token=...
GET    /api/auth/session
POST   /api/auth/sign-up
POST   /api/auth/sign-in
POST   /api/auth/sign-out
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
GET    /api/projects/:projectId/pages/:pageId/thumbnail
PUT    /api/projects/:projectId/slices
GET    /api/projects/:projectId/slices/:sliceId/preview.png
POST   /api/projects/:projectId/export-assets
GET    /api/projects/:projectId/assets.zip
POST   /api/projects/:projectId/export-project
POST   /api/projects/:projectId/pages/:pageId/export-project
GET    /api/projects/:projectId/pages/:pageId/project.zip
GET    /api/projects/:projectId/project.zip
```

Removed API:

```text
GET  /api/me
/api/billing/*
/api/admin/*
/api/billing/webhooks/xpay
```

## Redesign Boundaries

The frontend may change:

- visual system;
- layout;
- component split;
- animation;
- responsive behavior;
- wording, as long as the product semantics remain true.

The frontend must not change without backend coordination:

- API paths;
- request field names;
- response field names;
- `ProjectSummary`, `PageRecord`, `SliceRecord`, `ProjectDetail`, `SaveSlicesRequest`;
- project-level full-replacement save semantics;
- export endpoint semantics;
- signed download behavior;
- database schema.

Do not add placeholder admin, billing, payment, quota, entitlement, usage, order, or XPay screens to the redesign. If those return later, they need a new implementation plan and new function inventory.
