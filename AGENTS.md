# Repository Guidelines

This repository uses an agent-first workflow. Repository files are the source of truth; do not rely on chat history. Old plans, ADRs, legacy drafts, Codia Beta artifacts, and historical service folders are background only and must not override current code or current documentation.

## Start Here

Read these first:

1. `PROGRESS.md` for current objective, active plan, validation log, blockers, and checkpoint.
2. `docs/index.md` for the documentation map.
3. `docs/product/direction-contract.md` for final artifact, truth source, repair path, non-goals, and validation artifact.
4. `docs/roadmap.md` for current phase and next work.
5. `apps/slice-studio/README.md` for the current runtime and product behavior.
6. `docs/engineering/current-code-map.md` and `docs/engineering/legacy-code-inventory.md` before touching old directories.

## Current Mainline

The active product mainline is **Slice Studio**:

```text
1..N UI screenshots/design images
-> apps/slice-studio
-> project workspace
-> original PNGs in local storage
-> saved SliceRecord boxes in SQLite
-> assets.zip
-> project.zip / design.pen
```

Current default surface:

```text
apps/slice-studio/
```

Primary commands:

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
```

Local dev:

```bash
cd apps/slice-studio
bun run dev
```

Default URLs:

```text
Next web:  http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
```

## Runtime Surfaces

Slice Studio API:

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
```

The older assisted-slice Python endpoints under `/api/pencil/slice-projects/*` are historical/reference unless a task explicitly targets that service. Go Draft `/api/draft-preview`, Python `/api/upload-preview`, Codia-like generation, and Figma plugin/Renderer paths are not the current default delivery route.

## Truth Sources

- Saved Slice Studio pages and slices are the live edit/export truth.
- Export manifest schema `manual_ui_slices.v1` is the artifact truth.
- AI boxes are transient suggestions that become normal slices only through the existing save path.
- OCR provides text content only.
- TypeScript `m29-physical-evidence` provides physical text bbox evidence only.
- Go `m29extract` is explicit reference/fallback only and is not required for the default Slice Studio text path.
- Old Pencil Python, Pencil Asset, Pencil Handoff Studio, Go Draft, Renderer, plugin, PSD-like, and Codia material is reference or legacy unless a new active plan changes its authority.

## Project Structure

- `apps/slice-studio/` is the current product.
- `apps/slice-studio/server/` owns Elysia routes, SQLite storage, export, OCR, M29 physical evidence, AI slice boxes, and Pencil package generation.
- `apps/slice-studio/components/` owns the Next/React/Konva project workspace and review workbench.
- `apps/slice-studio/shared/` owns shared data contracts.
- `apps/slice-studio/tests/` owns Slice Studio unit/contract tests.
- `services/pencil-python-backend/`, `services/pencil-asset-backend/`, and `services/pencil-handoff-studio/` are superseded product/reference surfaces.
- `services/backend-go/` retains Go M29/Draft research and explicit fallback tooling.
- `services/psdlike-python/`, `backend/`, `services/backend-python/`, `figma-plugin/`, `packages/dsl-schema/`, and `packages/image-to-figma-renderer/` are historical/deferred/research assets unless explicitly targeted.

Before deleting, moving, or reviving non-mainline directories, read `docs/engineering/legacy-code-inventory.md`.

## Coding Style And Boundary Rules

TypeScript uses ESM, two-space indentation, `camelCase` values/functions, and `PascalCase` types. Go code uses `gofmt`. Python uses four-space indentation, `snake_case`, and type hints where they clarify boundaries.

Keep boundaries clean:

- Slice Studio export reads saved slices and original source images; it must not crop from canvas thumbnails or debug artifacts.
- AI slice boxes must not bypass saved slices or create a separate persistent proposal system.
- OCR, M29, YOLO, PSD-like, and VLM outputs are evidence/candidates only; they are not final visible ownership.
- Pencil `.pen` visible refs must point to package-local assets and must not contain absolute paths, `source.png`, raw crops, masks, debug assets, or `../`.
- Renderer/plugin code should render explicit contracts and report warnings; it should not hide backend ownership bugs.

Do not create `utils`, `common`, or `misc` dumping-ground modules. Large central files are design pressure; add behavior through focused modules with clear responsibility.

## Planning And Documentation Rules

Create or update a plan in `docs/plans/active/` before work that:

- touches multiple modules or directories;
- changes API, data models, environment variables, runtime behavior, or artifact contracts;
- changes Slice Studio export, OCR, M29 physical evidence, AI slice boxes, Pencil package generation, or server capability;
- fixes a defect that affects the current mainline;
- revives or physically moves legacy code.

Plan status must match its directory. Unfinished work belongs in `active/`, completed work in `completed/`, and superseded/deferred work in the matching archive directory.

Behavior, API, data model, env var, build, runtime, architecture-boundary, or acceptance changes must update the relevant docs.

Use `PROGRESS.md` for multi-step execution state. Update it before long-running work, after meaningful modules, after validation, when blocking or deferring an issue, and before final handoff.

## Testing And Validation Rules

Testing policy lives in `docs/engineering/validation.md`. Static tests alone are not enough for visible pipeline work.

At minimum for Slice Studio changes:

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
git status --short --branch
```

For export, OCR, M29 text bbox, AI slicing, or package changes, also run a real project smoke and inspect generated artifacts when credentials and samples are available.

## Git And Artifact Discipline

You may be in a dirty working tree. Never revert or overwrite user changes unless explicitly requested. Stage and commit only files scoped to the current task.

Do not commit:

```text
apps/slice-studio/.env.local
apps/slice-studio/storage/
apps/slice-studio/.next/
*.sqlite
*.db
*.zip
*.pen
dist/
build/
logs/
secrets
```

Do not run destructive operations such as deleting project data, resetting history, force-pushing, dropping databases, rotating secrets, or changing deployment state unless the user explicitly requested it or repository policy documents the operation.

## Final Handoff

For non-trivial work, final handoff must include:

- current `PROGRESS.md` state;
- completed modules/docs;
- validation commands and results;
- real-flow or artifact validation when applicable;
- blockers or deferred issues;
- whether the final artifact is deliverable;
- commit hash if committed, or reason if not committed.
