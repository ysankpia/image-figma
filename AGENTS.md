# Repository Guidelines

This repository uses an agent-first workflow. Repository files are the source of truth; do not rely on chat history. Old plans, ADRs, legacy drafts, and Codia Beta artifacts are background only and must not override current code or current documentation.

## Project Structure And Module Organization

This repository is a pnpm workspace plus backend services.

- `services/backend-go/` is the current backend implementation surface for the new Editable Draft pipeline. It owns Go M29 physical evidence, provider-neutral vision detection/review, editable layer graph assembly, local crop assets, Draft runtime DSL export, task storage, and Go tests.
- `figma-plugin/` contains the plugin UI, main thread, manifest, and bundle checks.
- `packages/image-to-figma-renderer/` renders validated runtime DSL into Figma through an adapter.
- `packages/dsl-schema/` owns shared DSL contracts that are intentionally shared with TypeScript code.
- `backend/` is retained Python/FastAPI historical preview/reference code. Do not use it as the starting point for Editable Draft runtime work unless a task explicitly targets the Python `/api/upload-preview` path.

Start from [docs/index.md](docs/index.md). Current specs live in `docs/product/`, `docs/architecture/`, `docs/engineering/`, `docs/runbooks/`, `docs/reference/`, `docs/plans/`, and `docs/bugs/`. Historical drafts live only in `docs/reference/legacy/` or `docs/plans/archive/`.

## Current Mainline

The active product mainline on this branch is:

```text
Figma Plugin
-> POST /api/draft-preview
-> Go backend services/backend-go
-> OCR
-> M29 physical evidence
-> optional OpenAI-compatible vision detector
-> optional vision review/reconciliation
-> Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma editable draft
```

Core product target:

```text
PNG -> editable Figma draft
```

Non-targets for the mainline:

```text
PNG -> Codia-like tree
PNG -> official Codia JSON byte-for-byte clone
PNG -> semantic UI control tree
PNG -> Auto Layout/component reconstruction
```

Codia artifacts and official Codia JSON samples are eval/reference inputs only. Generation code must not read Codia golden data.

## Runtime Surfaces

The new Draft runtime surface is:

```text
POST /api/draft-preview
GET /api/draft-preview/{taskId}
GET /api/draft-preview/{taskId}/dsl
GET /api/draft-preview/{taskId}/assets/{assetId}.png
```

The former Go Codia Beta path is legacy/eval material on this branch:

```text
/api/codia-preview
codia assembly/control/tree/emitter
codia_runtime.dsl.v0_2.json
Generate Beta
```

Do not add new generation behavior to the Codia path. If a Codia concept is useful, translate the underlying need into Draft terms: layer ownership, asset crop, z-order, grouping, or eval metric.

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

## Draft Architecture Guardrails

The Draft pipeline centers on `editable_layer_graph.v1.json`. First-version visible layer kinds are intentionally small:

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
