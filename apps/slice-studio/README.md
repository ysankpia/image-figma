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
