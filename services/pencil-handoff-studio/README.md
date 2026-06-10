# Pencil Handoff Studio

干净的新服务，用于把 UI 设计稿图片批量转成 Pencil handoff 项目和前端切图资源包。

```text
1..N UI images
-> originals
-> image/icon/basic candidates
-> Konva Review
-> manual_slices.v1.json
-> assets.zip
-> project.zip
```

## Run

```bash
cd services/pencil-handoff-studio
uv sync
cd web && pnpm install && pnpm run build
cd ..
uv run uvicorn app.main:app --host 127.0.0.1 --port 8120
```

Open:

```text
http://127.0.0.1:8120/api/handoff-projects/workspace
```

## Environment

```text
PENCIL_HANDOFF_STORAGE_ROOT=services/pencil-handoff-studio/storage
PENCIL_HANDOFF_MAX_FILES=0
PENCIL_HANDOFF_MAX_UPLOAD_BYTES=10485760
PENCIL_HANDOFF_YOLO_MODEL=/path/to/best.pt
PENCIL_HANDOFF_M29EXTRACT=/path/to/m29extract
PENCIL_HANDOFF_PSDLIKE_ROOT=/path/to/services/psdlike-python
OCR_PROVIDER=none
```

`PENCIL_HANDOFF_MAX_FILES=0` 表示不限制单项目图片数量。YOLO、M29、PSD-like、OCR 都是候选证据源；失败只写 warning，不阻断人工画框和导出。

## API

```text
GET  /api/health
GET  /api/ready
POST /api/handoff-projects
GET  /api/handoff-projects
GET  /api/handoff-projects/{projectId}
DELETE /api/handoff-projects/{projectId}
GET  /api/handoff-projects/{projectId}/review
GET  /api/handoff-projects/{projectId}/source/{pageId}
GET  /api/handoff-projects/{projectId}/candidates
GET  /api/handoff-projects/{projectId}/review-state
PUT  /api/handoff-projects/{projectId}/review-state
GET  /api/handoff-projects/{projectId}/manual-slices
PUT  /api/handoff-projects/{projectId}/manual-slices
POST /api/handoff-projects/{projectId}/export-preview
GET  /api/handoff-projects/{projectId}/export-preview/{filename}
POST /api/handoff-projects/{projectId}/export
GET  /api/handoff-projects/{projectId}/project.zip
GET  /api/handoff-projects/{projectId}/assets.zip
```

## Output

`assets.zip`:

```text
originals/page_0001.png
originals/page_0002.png
slices/page_0001/slice_0001.png
slices/page_0001/slice_0002.png
manifest.json
```

`project.zip`:

```text
design.pen
assets/originals/page_0001.png
assets/slices/page_0001/slice_0001.png
manifest.json
manual_slices.v1.json
review_state.v1.json
export-preview/contact-sheet.png
debug/
```

`design.pen` 每页一个 frame：底层是可见锁定 source reference，opacity 0.45；上层是用户确认的 selected slices，按原图坐标放回。

## Validation

```bash
make check
make handoff-acceptance IMAGE=/absolute/path/or/dir OUT=/Volumes/WorkDrive/pencil-exports/handoff-acceptance
```
