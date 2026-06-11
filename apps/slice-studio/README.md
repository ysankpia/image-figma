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

`/projects` is the local project browser:

```text
topbar: current view title, new project button
new project: modal form
content toolbar: recent/all/with-assets filters, search, sort, grid/list view
content grid: Figma-like project cards with first-page previews
card actions: inline rename, delete confirmation
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

`design.pen` contains one frame per page. Each frame has a visible `remainder.png` layer plus the confirmed slice PNG layers placed at their original source-image coordinates. Slice PNGs use the same `rect | subject | card` crop logic as `assets.zip`; there is no second asset pipeline. OCR, TextLayer generation, font recognition, and Figma import are intentionally not part of this Pencil export stage.

## Configuration

```text
NEXT_PUBLIC_SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_API_URL=http://127.0.0.1:4110
SLICE_STUDIO_API_PORT=4110
SLICE_STUDIO_ALLOWED_ORIGIN=http://127.0.0.1:3010
SLICE_STUDIO_MAX_UPLOAD_BYTES=20971520
SLICE_STUDIO_MAX_BATCH_UPLOAD_BYTES=314572800
```

`NEXT_PUBLIC_SLICE_STUDIO_API_URL` is used by the Next.js browser client. `SLICE_STUDIO_API_URL` is used by scripts such as `bun run smoke`.

## Scope

v1 supports manual `image` slicing plus Pencil project export. AI, OCR, YOLO, M29, PSD-like, TextLayer generation, Figma import, auth, and cloud sync are intentionally out of scope.
