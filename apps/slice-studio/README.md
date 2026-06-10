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
-> manual image/icon slices
-> SQLite metadata
-> assets.zip
```

## Review Workbench

Review uses a canvas-first layout:

```text
topbar: project, upload, zoom, save state, export
left rail: page thumbnails
center: black Konva canvas with floating tools
right inspector: selected asset editing, collapsible
```

Shortcuts:

```text
V: select and adjust slices
B: continuously draw slices
H: pan canvas
Delete/Backspace: delete active slice
Cmd/Ctrl+S: save immediately
Cmd/Ctrl + wheel: zoom around cursor
```

## Storage

```text
storage/
  app.sqlite
  projects/{projectId}/originals/page_0001.png
  projects/{projectId}/exports/assets.zip
```

`storage/` is local runtime data and must not be committed.

## Scope

v1 only supports manual `image` and `icon` slicing. AI, OCR, YOLO, M29, PSD-like, Pencil export, Figma import, auth, and cloud sync are intentionally out of scope.
