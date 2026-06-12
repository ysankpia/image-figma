# 158 Manual Slice Project Storage And SQLite Workspace

## Status

Completed.

## Scope

This phase turns `manual-slice.html` from an in-memory slicing page into a local project-based slicing tool. It does not add login, registration, cloud sync, automatic detection, OCR, YOLO, M29, PSD-like processing, or full-project Figma import.

## Product Flow

```text
workspace.html
-> create/open local project
-> upload 1..N UI screenshots
-> originals saved to storage/projects/{projectId}/originals/
-> SQLite stores project/page/slice metadata
-> manual-slice.html?projectId={projectId}
-> autosave manual slices
-> export assets.zip
```

## Runtime

Start the local project tool with:

```bash
npm run studio
```

Then open:

```text
http://127.0.0.1:4173/workspace.html
```

The legacy static preview remains available through:

```bash
npm run preview
```

The legacy image-generation proxy remains available through:

```bash
npm run api
```

## Storage Contract

Local project data is stored under `storage/` and is intentionally ignored by git.

```text
storage/
  app.sqlite
  projects/
    {projectId}/
      originals/page_0001.png
      originals/page_0002.png
      exports/assets.zip
```

SQLite stores metadata only. Image files are written to disk as PNG files.

## SQLite Tables

```text
projects(id, name, created_at, updated_at, page_count, slice_count)
pages(id, project_id, page_index, original_name, original_path, width, height, created_at)
slices(id, project_id, page_id, slice_index, name, kind, x, y, width, height, created_at, updated_at)
```

Slice constraints:

```text
kind = image | icon
width >= 1
height >= 1
bbox must fit inside the source page
```

## API

```text
GET    /api/health
GET    /api/projects
POST   /api/projects
GET    /api/projects/{projectId}
PATCH  /api/projects/{projectId}
DELETE /api/projects/{projectId}
POST   /api/projects/{projectId}/pages
GET    /api/projects/{projectId}/pages/{pageId}/source
PUT    /api/projects/{projectId}/slices
POST   /api/projects/{projectId}/export-assets
GET    /api/projects/{projectId}/assets.zip
```

## Export Contract

`assets.zip` contains:

```text
originals/page_0001.png
originals/page_0002.png
slices/page_0001/slice_0001.png
slices/page_0001/slice_0002.png
manifest.json
project.json
```

Slices are always cropped from the saved original PNG files.

## Validation

Required checks:

```bash
npm run check
git diff --check
git status --short --branch
```

Browser validation covers:

```text
create project
upload multiple screenshots
draw slices
autosave
refresh restore
rename/kind/delete
export assets.zip
legacy manual-slice.html without projectId still works
```
