# Repository Guidelines

This repository uses an agent-first workflow. Repository files are the source of truth; do not rely on chat history. Old plans, ADRs, and legacy drafts are background only and must not override current code or current documentation.

## Project Structure & Module Organization

This repository is a pnpm workspace plus a FastAPI backend. `packages/dsl-schema/` owns DSL v0.1 types, schema, and validation. `packages/image-to-figma-renderer/` writes validated DSL into Figma through an adapter. `figma-plugin/` contains the plugin UI, main thread, manifest, and bundle checks. `backend/` contains the FastAPI app, upload mainline, M29 source truth, plan materializer, routes, storage helpers, and `backend/tests/`.

Start from [docs/index.md](docs/index.md). Current specs live in `docs/product/`, `docs/architecture/`, `docs/engineering/`, `docs/runbooks/`, `docs/reference/`, `docs/decisions/`, `docs/plans/`, and `docs/bugs/`. Historical drafts live only in `docs/reference/legacy/`. The Chinese reference snapshot for this file is [docs/reference/agent-guidelines.zh-CN.md](docs/reference/agent-guidelines.zh-CN.md); this root `AGENTS.md` is authoritative.

## Current Mainline

The only active product mainline is:

```text
Figma Plugin
-> POST /api/upload-preview
-> OCR
-> raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 ownership conservation report
-> M29 hierarchy candidate report
-> M29 sibling group candidate report
-> M29 layout energy report
-> M29 plan-driven materializer
-> GET /api/tasks/{taskId}/dsl
-> Renderer
-> Figma
```

`/api/upload-preview` is the formal upload entrypoint. `/api/tasks/{taskId}/dsl` is the only formal design-output endpoint. Current mainline details live in [docs/engineering/current-mainline-code-map.md](docs/engineering/current-mainline-code-map.md).

## Documentation Routing

Read this file first, then [docs/index.md](docs/index.md), then only the task-relevant docs.

- Product scope and acceptance: `docs/product/`.
- DSL, API, Renderer, backend, and plugin boundaries: `docs/architecture/`.
- Current code map, testing, doc maintenance, and M29 regression matrix: `docs/engineering/`.
- Local setup, release, debugging, and migrations: `docs/runbooks/`.
- Environment variables, external interfaces, glossary, and legacy drafts: `docs/reference/`.
- Plans: `docs/plans/active/`, `docs/plans/completed/`, and `docs/plans/archive/`.
- Bug postmortems and regression protection: `docs/bugs/`.

ADRs are historical decision records, not active runtime truth. For deleted paths, trust the current code map, testing strategy, and latest completed plan over older ADRs.

## Build, Test, and Development Commands

Install and run workspace checks:

```bash
pnpm install
pnpm run check
pnpm -r run test
pnpm -r run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

The backend uses Python 3.12.7 from `.tool-versions`:

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

## Coding Style & Boundary Rules

TypeScript uses ESM, two-space indentation, `camelCase` values/functions, and `PascalCase` types. Python uses four-space indentation, `snake_case` modules/functions, and type hints where they clarify boundaries.

Keep boundaries clean: Renderer must not import backend code; backend must not import plugin code; plugin UI must not call the Figma API directly; shared contracts flow through `packages/dsl-schema/`. Do not commit `dist/`, `backend/storage/`, databases, logs, caches, secrets, or temporary artifacts.

Prefer simple, current, verifiable implementations. Do not add abstractions for hypothetical future needs, and do not create `utils`, `common`, or `misc` dumping-ground modules. Large central files are design pressure; add new behavior through focused modules with clear responsibility.

## Planning & Documentation Rules

Create or update a plan in `docs/plans/active/` before work that:

- touches multiple modules or directories;
- changes DSL, API, data models, environment variables, or runtime behavior;
- adds dependencies, engineering scripts, or CI behavior;
- changes plugin, Renderer, backend, M29 evidence chain, replay plan, or materializer mainline capability;
- fixes a defect that affects the mainline.

Plan status must match its directory: unfinished work belongs in `active/`, completed work in `completed/`, and superseded or deferred work in the matching `archive/` subdirectory. Behavior, API, data model, environment, build, runtime, architecture-boundary, or acceptance changes must update the relevant docs.

## Testing & Validation Rules

Testing policy lives in [docs/engineering/testing-strategy.md](docs/engineering/testing-strategy.md). DSL changes need schema or equivalent contract validation. Renderer changes must be validated with test DSL. Backend API changes need route-level validation. Plugin or Figma-visible behavior changes must record observable evidence through this project's validation path.

Changes to M29 owner, relation, replay, materializer, cleanup authorization, or fallback behavior must map to [docs/engineering/m29-contract-regression-matrix.md](docs/engineering/m29-contract-regression-matrix.md). If coverage is missing, add tests first or document the alternate guard and remaining risk.

## Bugfix & Regression Rules

Bug work starts from `docs/bugs/index.md` and the related bug record. Reproduce before fixing. After the fix, record root cause, fix summary, regression guard, and validation evidence. If automated regression coverage is not practical, document the alternate guard and remaining risk in the bug record.

## Commit & Pull Request Guidelines

Use Conventional Commit style such as `docs:`, `refactor:`, `test:`, `feat:`, and `fix:`. Phase work must become an independent commit scoped to that phase's code, tests, docs, ADRs, and plan updates. Do not include next-phase exploration, temporary debugging, storage, dist, secrets, or unrelated local changes.

PRs or handoffs should state the changed surface, linked plan/bug/ADR, validation commands, and visible UI/Figma/artifact evidence. New environment variables require updates to `.env.example` and `docs/reference/env-vars.md`.

## Agent-Specific Guardrails

Do not restore removed M29 Direct compare, legacy M30 materialization product paths, M31-M39/M39.1 runtime, routes, environment variables, or ONNX proposer. When old ADRs, completed plans, or legacy drafts mention those paths, treat them as historical background only.

M29.4 weak cluster, M29 hierarchy candidates, M29 sibling group candidates, and M29 layout energy are evidence only; they do not grant Group, Frame, Auto Layout, Figma Component/Instance, or materialization permission. M29.5 replay plan is the only source for materialization order, node budget, dedupe, and cleanup authorization. The M29 plan-driven materializer executes the plan only; it must not reclassify owners or add cleanup authorization.

Source ownership defects must be fixed in raw M29 or M29.2. Do not patch them in the materializer, Renderer, or plugin with color, copy, theme, industry, filename, or fixed-bbox special cases. Root/page background must come from source PNG sampling; do not restore a fixed light default to hide fallback-off failures.
