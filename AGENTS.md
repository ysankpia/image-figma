# Repository Guidelines

This repository uses an agent-first workflow. Repository files are the source of truth; do not rely on chat history. Old plans, ADRs, legacy drafts, and Codia Beta artifacts are background only and must not override current code or current documentation.

## Project Structure And Module Organization

This repository is a pnpm workspace plus backend services.

- `services/pencil-python-backend/` is the current usable product delivery surface on this branch. It owns the assisted slice workspace, slice project storage, candidate generation, user-confirmed `manual_slices.v1.json`, Pencil `.pen` export, `project.zip`, `selected-assets.zip`, deploy scripts, and Python tests.
- `services/backend-go/` is retained as a Go M29/Draft evidence and tooling surface. It still provides `m29extract` for Pencil boundary/evidence work, but Go Draft is not the current product delivery mainline on this branch.
- `figma-plugin/` contains the plugin UI, main thread, manifest, and bundle checks.
- `packages/image-to-figma-renderer/` renders validated runtime DSL into Figma through an adapter.
- `packages/dsl-schema/` owns shared DSL contracts that are intentionally shared with TypeScript code.
- `backend/` is retained Python/FastAPI historical preview/reference code. Do not use it as the starting point for Editable Draft runtime work unless a task explicitly targets the Python `/api/upload-preview` path.

Start from [docs/index.md](docs/index.md). Current specs live in `docs/product/`, `docs/architecture/`, `docs/engineering/`, `docs/runbooks/`, `docs/reference/`, `docs/plans/`, and `docs/bugs/`. Historical drafts live only in `docs/reference/legacy/` or `docs/plans/archive/`.

## Current Mainline

The active product mainline on this branch is:

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

Core product target:

```text
PNG/screenshots -> user-confirmed Pencil/Figma handoff package
```

Non-targets for the mainline:

```text
PNG -> Codia-like tree
PNG -> official Codia JSON byte-for-byte clone
PNG -> fully automatic semantic UI control tree
PNG -> Auto Layout/component reconstruction
YOLO/model output as final visible ownership judge
Go Draft as the default delivery route
services/pencil-go revival
```

Codia artifacts, official Codia JSON samples, old Go Draft plans, and automatic ownership experiments are eval/reference inputs only. Generation code must not read Codia golden data.

## Runtime Surfaces

The current assisted slice runtime surface is:

```text
GET  /api/pencil/slice-projects/workspace
GET  /api/pencil/slice-projects/new
POST /api/pencil/slice-projects
GET  /api/pencil/slice-projects/{projectId}
GET  /api/pencil/slice-projects/{projectId}/review
GET  /api/pencil/slice-projects/{projectId}/candidates
GET  /api/pencil/slice-projects/{projectId}/review-state
PUT  /api/pencil/slice-projects/{projectId}/review-state
GET  /api/pencil/slice-projects/{projectId}/manual-slices
PUT  /api/pencil/slice-projects/{projectId}/manual-slices
POST /api/pencil/slice-projects/{projectId}/export-preview
POST /api/pencil/slice-projects/{projectId}/export
GET  /api/pencil/slice-projects/{projectId}/download.zip
GET  /api/pencil/slice-projects/{projectId}/selected-assets.zip
```

The older automatic Pencil project export surface remains available for explicit batch/diagnostic use, but it is no longer the product judge:

```text
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip
```

The Draft runtime surface is retained as historical/deferred Draft work, not the current default delivery route on this branch:

```text
POST /api/draft-preview
GET /api/draft-preview/{taskId}
GET /api/draft-preview/{taskId}/dsl
GET /api/draft-preview/{taskId}/assets/{assetId}.png
```

The former Go Codia Beta product entrypoint has been removed on this branch. The names below are legacy/eval material only:

```text
/api/codia-preview
codia assembly/control/tree/emitter
codia_runtime.dsl.v0_2.json
Generate Beta
```

Do not restore the Codia HTTP route or add new generation behavior to Codia packages. If a Codia or Draft concept is useful for the assisted slice route, translate the underlying need into candidate evidence, source-image crop, user confirmation, export manifest, or acceptance metric.

The retained Python/FastAPI preview path is historical/reference unless explicitly targeted:

```text
/api/upload-preview
/api/tasks/{taskId}/dsl
```

## Documentation Routing

Read this file first, then [docs/index.md](docs/index.md), then only the task-relevant docs.

- Product scope and acceptance: `docs/product/`.
- Draft architecture, API, renderer, backend, and plugin boundaries: `docs/architecture/`.
- Current code map, validation, doc maintenance, and anti-specialization rules: `docs/engineering/`.
- Local setup, release, debugging, and migrations: `docs/runbooks/`.
- Environment variables, external interfaces, glossary, Codia samples, and legacy drafts: `docs/reference/`.
- Plans: `docs/plans/active/`, `docs/plans/completed/`, and `docs/plans/archive/`.
- Bugs and regression records: `docs/bugs/`.

ADRs are historical decision records. They do not override current architecture docs, current plans, or current code.

## Build, Test, And Development Commands

Install and run workspace checks:

```bash
pnpm install
pnpm run check
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

Go backend checks:

```bash
cd services/backend-go
go test ./...
```

Draft server local run target:

```bash
cd services/backend-go
DRAFT_SERVER_ADDR=127.0.0.1:8000 go run ./cmd/draftserver
```

Use the Python/FastAPI path only for explicit historical preview work:

```bash
cd backend
uv sync
UPLOAD_PREVIEW_PROFILE=production uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
uv run pytest -q
```

Current Pencil assisted slice backend checks:

```bash
cd services/pencil-python-backend
make check
make slice-acceptance IMAGE=/absolute/path/to/image-or-dir OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

Before handoff, run at least:

```bash
git diff --check
git status --short --branch
```

## Coding Style And Boundary Rules

TypeScript uses ESM, two-space indentation, `camelCase` values/functions, and `PascalCase` types. Go code uses `gofmt`, table-driven tests where useful, focused packages, and standard-library-first implementations. Python uses four-space indentation, `snake_case` modules/functions, and type hints where they clarify boundaries.

Keep boundaries clean:

- Renderer must not import backend code.
- Backends must not import plugin code.
- Plugin UI must not call the Figma API directly.
- Draft generation packages must not import Codia eval packages.
- Shared contracts flow through explicit package contracts, not ad hoc JSON mutation.

Do not commit `dist/`, `backend/storage/`, `services/backend-go/storage/`, databases, logs, caches, secrets, temporary artifacts, or generated experiment output.

Prefer simple, current, verifiable implementations. Do not create `utils`, `common`, or `misc` dumping-ground modules. Large central files are design pressure; add new behavior through focused modules with clear responsibility.

## Assisted Slice Guardrails

The assisted slice pipeline centers on these contracts:

```text
candidates.v1.json
review_state.v1.json
manual_slices.v1.json
project.zip
selected-assets.zip
```

Hard invariants:

- `manual_slices.v1.json` is the final delivery truth source.
- `review_state.v1.json` is workbench state only.
- PSD-like, M29, OCR, foreground audit, and model detections only produce candidates or debug evidence.
- Export crops selected slices from the original `source.png`, not from raw fragment crops.
- Pencil `.pen` visible image refs must point to package-local `./assets/visible/...` files.
- Do not emit absolute paths, `source.png`, raw crops, masks, debug assets, or `../` as visible refs.
- Default export is rectangular crop; transparent background remains optional future work.

## Draft Architecture Guardrails

The Draft pipeline is historical/deferred on this branch. If explicitly resumed, it centers on `editable_layer_graph.v1.json`. First-version visible layer kinds are intentionally small:

```text
Page
ReferenceImage
TextLayer
RasterLayer
ShapeLayer
GroupLayer
```

Semantic concepts such as Button, ListView, BottomNavigation, ActionBar, EditText, Component, Instance, and Auto Layout must not become first-version structural authorities. Represent them as `semanticTags` or eval labels unless an approved plan changes the contract.

Hard invariants:

- One visible foreground pixel should have one visible owner.
- The original PNG must not be emitted as visible full-page backing.
- `ReferenceImage` is hidden/locked diagnostic context only.
- Text layers render above same-region raster/shape layers.
- Raster assets must have resolvable asset references.
- Shape layers must not carry foreground text pixels.
- Every emit/consume/suppress/refine decision must carry source refs and a reason.

## Vision And Provider Guardrails

Vision models provide candidates and review decisions; they do not generate final Figma trees or final DSL.

Default authority order:

```text
M29/OCR bbox evidence > VLM semantic label
```

Provider configuration must remain replaceable through environment variables. Do not hardcode base URL, model ID, API key, provider name, sample name, brand, visible text, fixed bbox, fixed coordinates, or fixed screen size.

## Planning And Documentation Rules

Create or update a plan in `docs/plans/active/` before work that:

- touches multiple modules or directories;
- changes DSL, API, data models, environment variables, runtime behavior, or artifact contracts;
- adds dependencies, engineering scripts, or CI behavior;
- changes plugin, Renderer, backend, M29 evidence, vision provider, Draft graph, export, or server capability;
- fixes a defect that affects the mainline.

Plan status must match its directory. Unfinished work belongs in `active/`, completed work in `completed/`, and superseded/deferred work in the matching `archive/` subdirectory.

Behavior, API, data model, environment, build, runtime, architecture-boundary, or acceptance changes must update the relevant docs.

## Testing And Validation Rules

Testing policy lives in [docs/engineering/validation.md](docs/engineering/validation.md). Static tests alone are not enough for visible pipeline work. Substantial Draft changes need a real sample/artifact validation pass.

At minimum, validate the affected surface:

- Draft contract/package changes: `cd services/backend-go && go test ./internal/draft/...`.
- Vision provider changes: `cd services/backend-go && go test ./internal/vision/...`.
- Server route changes: `cd services/backend-go && go test ./internal/app/... ./cmd/draftserver`.
- Renderer changes: `pnpm --filter @image-figma/image-to-figma-renderer run typecheck && pnpm --filter @image-figma/image-to-figma-renderer run test`.
- Plugin changes: `pnpm --filter @image-figma/figma-plugin run typecheck && pnpm --filter @image-figma/figma-plugin run build`.

Real sample validation should inspect generated artifacts, not only command exit codes:

```text
editable_layer_graph.v1.json
draft_runtime.dsl.v1.json
draft_validation_report.md
asset_manifest.json
renderer/plugin warnings
```

## Bugfix And Regression Rules

Bug work starts from `docs/bugs/index.md` and the related bug record. Reproduce before fixing when practical. After the fix, record root cause, fix summary, regression guard, and validation evidence.

Fix the owning layer:

```text
source image/OCR
M29 physical evidence
vision candidate/review
Draft assembly ownership
Draft asset/export
Renderer
Plugin route/render wiring
```

Do not patch visible output until the ownership or information-loss layer is known.

## Commit And Pull Request Guidelines

Use Conventional Commit style such as `docs:`, `refactor:`, `test:`, `feat:`, and `fix:`. Phase work must become an independent commit scoped to that phase's code, tests, docs, and plan updates.

Do not include next-phase exploration, temporary debugging, storage, dist, secrets, or unrelated local changes.

PRs or handoffs should state changed surface, linked plan/bug/architecture doc, validation commands, and visible artifact evidence. New environment variables require updates to `.env.example` and `docs/reference/env-vars.md`.

## Agent-Specific Guardrails

Do not restore or extend these as product-generation paths:

```text
Codia assembly/control/tree/emitter
Generate Beta as the main product route
visible full-image backing
Python /api/upload-preview as Draft runtime
M29 Direct compare
legacy M30 materialization product paths
M31-M39/M39.1 runtime
ONNX proposer
```

Codia golden JSON and Codia-like canvas samples are eval/reference only. They must not be imported by generation packages or used as runtime hints.

Do not patch Draft output with rules tied to sample names, file paths, task ids, image names, page names, fixed coordinates, fixed bboxes, fixed screen sizes, visible text, brand, theme color, industry, account, or one screenshot structure.

Source ownership defects belong upstream in M29, OCR, vision review, or Draft assembly. Renderer and plugin code should render the contract and report warnings; they should not hide backend ownership bugs.
