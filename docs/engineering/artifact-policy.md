# Artifact Policy

Current product artifacts belong to Slice Studio.

```text
storage/
  app.sqlite
  users/{userId}/projects/{projectId}/originals/
  users/{userId}/projects/{projectId}/exports/assets.zip
  users/{userId}/projects/{projectId}/exports/project.zip
```

Runtime artifacts are useful for local work and validation, but they are not source code and must not be committed unless explicitly curated as fixtures.

## Slice Studio Runtime Artifacts

`assets.zip` should contain:

```text
originals/*
slices/*
manifest.json
project.json
```

`project.zip` should contain:

```text
design.pen
manifest.json
project.json
assets/originals/*
assets/visible/remainders/*
assets/visible/slices/*
```

Exported visible image refs must be package-local. They must not contain absolute paths, `../`, raw source paths, debug paths, provider request data, or local storage paths.

## Git Policy

Do not commit runtime artifacts:

```text
storage/
.next/
archive/legacy-code/backend/storage/
archive/legacy-code/services/backend-go/storage/
archive/legacy-code/services/backend-go/tmp/
services/*/storage/
logs/
*.log
*.db
*.sqlite
*.sqlite3
dist/
build/
*.zip
*.pen
```

Reference fixtures are allowed only when intentionally curated under `docs/reference/` or test fixture directories and contain no secrets, local absolute paths, user data, or provider raw responses.

## Report Policy

Reports should help locate ownership decisions and validation evidence. They must not contain API keys, bearer tokens, full provider request headers, or full local env dumps.

Useful current reports include:

```text
Slice Studio export manifest
AI slice diagnostics
OCR/M29 text diagnostics
validation notes in docs/plans/*
```

Historical Draft reports such as `draft_validation_report.md`, `vision_detector_report.md`, and `asset_manifest.json` remain useful only when explicitly working on the deferred Go Draft route.

## Asset Policy

Confirmed Slice Studio slices are the visible asset truth source. `assets.zip` and `project.zip` must crop from original source images and saved SliceRecord boxes.

AI boxes, OCR, M29 physical evidence, old PSD-like candidates, YOLO detections, and historical Draft layers are evidence or reference only. They do not become visible product assets until saved as normal Slice Studio slices or explicitly routed through a new approved contract.

The source image may be packaged as original/reference context, but it must not become a hidden workaround for missing confirmed slice assets.
