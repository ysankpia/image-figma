# Slice Studio

正式化的本地项目制 UI 切图工具。

## Run

```bash
bun install
bun run dev
```

默认端口：

```text
Next web: http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
Text style: http://127.0.0.1:4120
```

## Product Flow

```text
1..N UI screenshots
-> project workspace
-> originals saved to storage
-> manual image slices
-> SQLite metadata
-> assets.zip for frontend assets
-> project.zip / design.pen for Pencil handoff
```

## Project Home

`/projects` is the authenticated project browser:

```text
topbar: current view title, new project button
new project: modal form
content toolbar: recent/all/with-assets filters, search, sort, grid/list view
content grid: Figma-like project cards with first-page previews
card actions: inline rename, delete confirmation
```

The public surface now starts at `/`. Anonymous users can view the landing page and `/login`; project list, review workspace, source image, previews, exports, `/settings`, `/billing`, and `/admin` require a session.

Local bootstrap login:

```text
email: local@slicestudio.dev
password: slice-studio-local-owner
```

Override this with `SLICE_STUDIO_LOCAL_OWNER_EMAIL` and `SLICE_STUDIO_LOCAL_OWNER_PASSWORD` before a real deployment.

Account surfaces:

```text
/settings: current account and role
/billing: entitlement, remaining AI/export credits, usage events, payment orders
/admin: admin-only totals for users, projects, pages, slices, usage, and orders
```

## Review Workbench

Review uses a canvas-first layout:

```text
topbar: project, upload, grouped zoom, short save state, assets/project export
left rail: page thumbnails
center: black Konva canvas with select/draw/pan floating tools
right inspector: compact active asset editor and asset list, collapsible
```

Delete is an action, not a toolbar mode. Use `Delete/Backspace`, the active asset delete icon, or the asset row delete icon.

The right inspector owns page naming and active asset details:

```text
page name: editable display name, shown with current order P1/P2
page actions: replace source image, delete page
asset list: #number, name, delete only
active asset: name, bbox x/y/w/h
```

Page management rules:

```text
delete page: removes the page source image and all slices on that page
replace page: uploads one new source image for the current page and clears that page's slices
move page: drag the horizontal handle in the left page rail; export regenerates P1/P2 from that order
```

Shortcuts:

```text
V: select and adjust slices
B: continuously draw slices
H: pan canvas
Delete/Backspace: delete active slice
Cmd/Ctrl+S: save immediately
Cmd/Ctrl+Z: undo the latest session operation
Cmd/Ctrl + wheel: zoom around cursor
```

Undo is session-local. Slice creation, move, resize, delete, rename, page rename, and page ordering are written back after undo. File-level page delete/replace cannot restore the old source image after it has been removed or overwritten; the UI reloads from current disk state and shows a warning instead of pretending the file came back.

Box colors are local Review UI preferences. Use the color controls in the right inspector to change normal and active slice outline colors; the preference is kept in browser local storage and does not affect exported assets.

Each slice supports three export modes:

```text
rect: rectangular crop
subject: remove local background and keep the foreground icon/logo/badge
card: remove only outside/edge background and preserve internal photo/card/button content
```

Use `subject` for assets like icons, logos, badges, plus buttons, cart buttons, and similar foreground shapes. Use `card` for product photos, banners, full cards, or buttons where internal fills/textures/text must remain intact. These modes are deterministic local image processing, not SVG vectorization and not AI segmentation. If one bbox contains several independent objects, draw separate boxes for separate assets.

## Storage

```text
storage/
  app.sqlite
  projects/{projectId}/originals/page_0001.png
  projects/{projectId}/exports/assets.zip
  projects/{projectId}/exports/project.zip
  projects/{projectId}/exports/pages/{pageId}/project.zip
```

`storage/` is local runtime data and must not be committed.

`assets.zip` exports by page order plus optional page display name:

```text
originals/P1-首页.png
slices/P1-首页/slice_0001.png
manifest.json
project.json
```

The exporter reads SQLite slices and original PNG files on disk. It does not crop from frontend thumbnails or canvas state. Export fails when no slices exist.

`project.zip` packages the same confirmed slice assets into a Pencil handoff project:

```text
design.pen
manifest.json
project.json
assets/originals/P1-首页.png
assets/visible/remainders/P1-首页/remainder.png
assets/visible/slices/P1-首页/slice_0001.png
```

`POST /api/projects/:projectId/pages/:pageId/export-project` writes the same package shape for only one page under `exports/pages/{pageId}/project.zip`. It exists for fast page-level debugging and delivery; it does not introduce a second Pencil schema.

`design.pen` contains one clipped frame per exported page. Each frame has a visible `remainder.png` layer, optional OCR-anchored control-surface rectangles, editable OCR text nodes when available, and confirmed slice PNG layers placed at their original source-image coordinates. Export builds a small page render/ownership plan before materialization so remainder text knockouts, control-surface source cleanup, editable text, and confirmed slice z-order come from one contract. Editable text nodes use compact fixed render bounds (`textGrowth: fixed-width-height`) through `textRenderBBox`; expanded `safeBBox` remains metadata/audit evidence instead of the visible Pencil text node box, and the original OCR/physical bbox remains the fit/knockout source. Slice PNGs use the same `rect | subject | card` crop logic as `assets.zip`; there is no second asset pipeline.

Pencil export also runs a conservative OCR pass. By default it uses the existing Baidu AI Studio PP-OCRv5 async API when `BAIDU_PADDLE_OCR_TOKEN` is available from `.env.local` or the process environment. OCR remains the text-content authority. When `SLICE_STUDIO_TEXT_BBOX_SOURCE=m29_ocr_hybrid`, Slice Studio uses M29 physical foreground evidence as physical/color evidence for OCR text, not as the default final render box. The default physical evidence provider is the internal TypeScript `m29-physical-evidence` extractor. It accepts OCR blocks as text-mask/text-region lineage, while still treating OCR-backed text regions as mask evidence instead of physical bbox truth. Editable text placement defaults to the OCR/original text region so the generated Pencil text replaces source glyph pixels instead of shrinking to a tight foreground mask. The Go `m29extract` binary is retained only as an explicit reference/fallback with `SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=go_m29extract`. M29 evidence never creates visible layers and never overrides confirmed manual slice assets.

Editable text style is measured through the current `services/psdlike-text-style` service when `SLICE_STUDIO_TEXT_STYLE_PROVIDER=psdlike`. The service is measurement-only: it receives the page PNG plus OCR text bbox and optional owner surface, then returns font size, weight, color, family, alignment, and measured glyph bounds. It does not decide raster-vs-editable, slice ownership, shape generation, knockout, or Pencil layer ordering. If the service is unavailable, slow, or returns malformed data, Slice Studio falls back to the local TypeScript estimator and still exports `project.zip`.

OCR output only adds editable text nodes above the remainder and below confirmed slice layers; it does not rebuild card shapes, images, icons, or Auto Layout. Filled non-background owner surfaces may be emitted as simple Pencil rectangles below editable text and receive matching source cleanup instructions in the page render plan. OCR text lines that are mostly covered by confirmed manual slice boxes, low confidence, or oversized/noisy are skipped so product images, icons, and manually extracted raster assets do not get accidental text overlays. Solid owner surfaces may help center and fit short labels; outlined/background surfaces are recorded as evidence but must not squeeze or shift the editable replacement text. If OCR or M29 fails, `project.zip` still exports and `manifest.json` records the skip/failure status. Tesseract is available only as an explicit diagnostic fallback with `SLICE_STUDIO_OCR_PROVIDER=tesseract`.

## Configuration

```text
NEXT_PUBLIC_SLICE_STUDIO_API_URL=
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_AUTH_COOKIE_NAME=slice_studio_session
SLICE_STUDIO_AUTH_SESSION_TTL_DAYS=30
SLICE_STUDIO_AUTH_SECURE_COOKIES=false
SLICE_STUDIO_LOCAL_OWNER_EMAIL=local@slicestudio.dev
SLICE_STUDIO_LOCAL_OWNER_NAME=Local Owner
SLICE_STUDIO_LOCAL_OWNER_PASSWORD=slice-studio-local-owner
SLICE_STUDIO_ALLOWED_ORIGIN=http://127.0.0.1:3010
SLICE_STUDIO_MAX_UPLOAD_BYTES=20971520
SLICE_STUDIO_MAX_BATCH_UPLOAD_BYTES=314572800
SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5
SLICE_STUDIO_OCR_MIN_CONFIDENCE=0.70
SLICE_STUDIO_TEXT_BBOX_SOURCE=m29_ocr_hybrid
SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=ts_m29_physical_evidence
SLICE_STUDIO_M29EXTRACT_PATH=/absolute/path/to/archive/legacy-code/services/backend-go/bin/m29extract
SLICE_STUDIO_TEXT_STYLE_PROVIDER=psdlike
SLICE_STUDIO_TEXT_STYLE_BASE_URL=http://127.0.0.1:4120
SLICE_STUDIO_TEXT_STYLE_TIMEOUT_SECONDS=8
BAIDU_PADDLE_OCR_TOKEN=
BAIDU_PADDLE_OCR_JOB_URL=https://paddleocr.aistudio-app.com/api/v2/ocr/jobs
BAIDU_PADDLE_OCR_MODEL=PP-OCRv5
BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS=5
BAIDU_PADDLE_OCR_TIMEOUT_SECONDS=120
```

The browser client normally uses same-origin `/api`, and Next.js rewrites that to `SLICE_STUDIO_API_URL`. Set `NEXT_PUBLIC_SLICE_STUDIO_API_URL` only when deliberately bypassing the same-origin proxy. `SLICE_STUDIO_API_URL` is used by Next rewrites, server-rendered account pages, and scripts such as `bun run smoke`.

`SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER` accepts `ts_m29_physical_evidence`, `go_m29extract`, or `ocr`. The default `ts_m29_physical_evidence` path has no Go binary dependency. It carries OCR text-mask lineage in the same spirit as the older Go M29 pipeline, but it does not let OCR boxes directly become physical text placement. `go_m29extract` uses `SLICE_STUDIO_M29EXTRACT_PATH`; `ocr` disables physical bbox evidence and keeps OCR bboxes.

`SLICE_STUDIO_TEXT_STYLE_PROVIDER` accepts `psdlike` or `fallback`. Normal runtime defaults to `psdlike`; test runtime defaults to `fallback` unless explicitly overridden so unit tests do not depend on a local HTTP service.

AI slice boxes use a separate `SLICE_STUDIO_AI_SLICE_*` provider configuration. The model sees compressed tiles and an optional compressed overview, returns rectangular boxes, and the Review Workbench saves accepted boxes as ordinary `SliceRecord` entries. AI does not create a separate proposal database or export path.

## Scope

v1 supports manual slicing, AI-assisted rectangular slicing, `rect | subject | card` cut modes, assets export, Pencil project export, optional OCR text overlays, optional M29 text bbox evidence, PSD-like editable-text style measurement, login/register, project ownership, basic entitlement/usage records, provider-neutral payment orders, minimal XPay webhook fulfillment, account settings, billing, and admin overview. YOLO, automatic semantic UI ownership, Figma import, team collaboration, production object storage, payment reconciliation/refund/admin repair, and cloud sync remain out of scope.
