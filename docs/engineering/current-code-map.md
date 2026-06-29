# Current Code Map

This document maps the current `main` branch. It describes where new product work should land.

## Product Mainline

```text
1..N UI screenshots/design images
-> repository root
-> project workspace
-> original source images
-> saved SliceRecord boxes in SQLite
-> assets.zip
-> project.zip / design.pen
```

New product work defaults to:

```text
repository root
```

Saved Slice Studio pages and slices are the current product truth source. AI boxes, OCR, TypeScript M29 physical evidence, Go M29 fallback, and old automatic candidates are evidence only.

## Slice Studio Surface

Primary files:

```text
app/
components/
server/
shared/
tests/
README.md
.env.example
```

Runtime:

```text
Next web:  http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
SQLite:    storage/app.sqlite
Originals: storage/users/{userId}/projects/{projectId}/originals/
Exports:   storage/users/{userId}/projects/{projectId}/exports/
```

Backward compatibility note:

```text
legacy local projects may still physically live under storage/projects/{projectId}/...
runtime keeps reading those paths until a later explicit migration/repack step
```

Current API:

```text
GET    /api/health
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

## Slice Studio Module Responsibilities

```text
server/index.ts             Elysia route surface
server/projects.ts          project/page/slice persistence
server/db.ts                SQLite setup and queries
server/exporter.ts          assets.zip export
server/pencil-exporter.ts   project.zip/design.pen export
server/pencil-package.ts    Pencil package assembly helpers
server/shape-cutout.ts      rect/subject/card crop output
server/text-ocr.ts          OCR provider integration
server/text-reconstruction.ts editable Pencil text nodes
server/render-plan.ts       Pencil export layer ownership contract
server/render-plan-builder.ts derives page render/ownership plan from saved slices and reconstructed text
server/m29-text-locator.ts  OCR line to physical bbox matching
server/m29-physical-evidence/ TypeScript M29 physical evidence kernel
server/ai-slice-boxes/      AI tile/overview bbox proposal
shared/types.ts             public TypeScript data contracts
shared/manifest.ts          export manifest builder
shared/ai-slices.ts         merge AI boxes into normal slices
components/workspace/       project home
components/review/          Review Workbench
```

## Hard Product Rules

```text
saved SliceRecord boxes are the export truth
AI boxes are transient suggestions
OCR text does not rebuild UI backgrounds
M29 evidence does not create visible layers
exports crop from original source images
visible .pen refs must be package-local
```

`assets.zip` and `project.zip` use the same confirmed slice assets and cut-mode logic. There is no second visible asset ownership pipeline.

## Reference And Superseded Surfaces

## Standalone Experiments

`tools/html-first-ui-rebuilder/` is an independent Python-first skill/CLI for the new HTML-first route:

```text
UI screenshot
-> asset_plan.json
-> full-page Qwen layers / connected components
-> clean ROI crops
-> asset sheets
-> optional ROI Qwen-Image-Layered retry layers
-> extracted assets
-> preview.html / report.md
```

It is deliberately not wired into Slice Studio, the SQLite project state, `manual_ui_slices.v1`, Go Draft, Renderer, or the historical Figma plugin.

`tools/go-m29-physical-evidence/` is an independent minimal Go M29.0 locator:

```text
input PNG
-> foreground mask
-> connected components
-> original-image pixel bboxes
-> m29_locations.v1.json
-> crops/loc_*.png
```

It is deliberately not wired into Slice Studio. The current default Slice Studio path remains `server/m29-physical-evidence/`; this standalone module exists for isolated coordinate extraction and matching crop output without editing `archive/legacy-code/services/backend-go/`. It does not include OCR, evidence tokens, Draft, vision, overlays, preview sheets, or relation graph output.

`tools/py-m29-locator/` is an independent Python port of that standalone Go locator:

```text
input PNG
-> foreground mask
-> connected components
-> original-image pixel bboxes
-> m29_locations.v1.json
-> crops/loc_*.png
```

It is also not wired into Slice Studio. Its acceptance target is matching coordinate JSON and crop output. Small measurement-only floating-point differences from Go around edge-density thresholds are accepted and should not be fixed with image-specific logic.

These directories are retained but are not the default product entrypoint:

| Path | Current status | Rule |
| --- | --- | --- |
| `archive/legacy-code/services/pencil-python-backend/` | superseded product/reference | Do not send new default product work here. Keep for historical Pencil assisted slice reference and deployment notes. |
| `archive/legacy-code/services/pencil-asset-backend/` | superseded slim handoff/reference | Keep as image/icon handoff reference. Do not merge its YOLO/M29/PSD-like candidate logic into Slice Studio by default. |
| `archive/legacy-code/services/pencil-handoff-studio/` | superseded handoff prototype/reference | Keep as prior batch handoff reference. |
| `archive/legacy-code/services/backend-go/cmd/m29extract/` and `archive/legacy-code/services/backend-go/internal/m29/` | reference/fallback tooling | Slice Studio default uses TypeScript M29 physical evidence. Go is explicit fallback/reference only. |
| `archive/legacy-code/services/backend-go/internal/draft/`, `cmd/draft*`, `internal/vision/`, `internal/app/` | legacy research/deferred runtime | Do not revive without a new active plan and validation gate. |
| `archive/legacy-code/backend/` | legacy Python upload-preview research | Not a current runtime. |
| `archive/legacy-code/services/backend-python/` | legacy model/PSD-like experiment | Reference only. |
| `archive/legacy-code/services/psdlike-python/` | legacy/reference dependency for old Python routes | Not used by default Slice Studio runtime. |
| `archive/legacy-code/services/pencil-go/` | legacy experiment | Do not revive by default. |
| `archive/legacy-code/figma-plugin/`, `archive/legacy-code/packages/dsl-schema/`, `archive/legacy-code/packages/image-to-figma-renderer/` | deferred Draft/plugin assets | Maintain only when explicitly working on old Draft/plugin runtime. |

For full classification, read [legacy-code-inventory.md](legacy-code-inventory.md).

## Package Responsibilities

Current active implementation responsibility lives at the repository root.

Historical Go package responsibilities remain useful only when explicitly working on Go Draft/M29:

```text
internal/image  -> generic image math
internal/m29    -> physical evidence
internal/vision -> model providers and candidate/review logic
internal/draft  -> deferred editable layer graph / runtime DSL
internal/eval   -> Codia/golden comparison only
```

Generation code must not import Codia eval packages or read official Codia golden data.
