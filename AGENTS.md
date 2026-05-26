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
-> optional M29 perception model report (opt-in)
-> raw M29 primitive graph
-> M29.2 source ownership
-> optional M29 perception source compiler (opt-in M29.2 enhancement)
-> M29.3 relation graph
-> M29.4 weak structural evidence
-> M29.5 replay plan
-> M29 ownership conservation report
-> M29.6 media internal decomposition report
-> M29 transparent asset report
-> M29 evidence contract report
-> M29 internal source promotion
-> M29.3/M29.4/M29.5 final reports from promoted M29.2
-> M29 hierarchy candidate report
-> M29 sibling group candidate report
-> M29 layout energy report
-> M29 Auto Layout permission report
-> M29 plan-driven materializer
-> optional M29 perception fate trace report (opt-in)
-> M29 design token report
-> M29 B-stage quality report
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

## M29 Bridge Fate Debugging

For any M29-visible regression, inspect the latest task's bridge fate trace first:

```text
backend/storage/upload_previews/{taskId}/m29_bridge_fate_trace/bridge_fate_trace_report.json
```

Use it only as a read-only diagnostic index. Identify `firstBlockingStage`, `firstBlockingReason`, `candidateRole`, `bbox`, `evidenceDecision`, `promotionDecision`, `finalReplayDecision`, and `materializerDecision` before choosing a fix layer.

Fix the owning layer shown by the trace. Do not add sample-specific labels, brands, filenames, task ids, fixed bboxes, fixed coordinates, theme colors, or one-off screenshot rules to bridge fate trace, materializer, Renderer, or plugin code.

Bridge fate remains diagnostic infrastructure. Failure evidence and regression guards belong in `docs/bugs/`, `docs/plans/`, tests, or validation ledgers.

## Commit & Pull Request Guidelines

Use Conventional Commit style such as `docs:`, `refactor:`, `test:`, `feat:`, and `fix:`. Phase work must become an independent commit scoped to that phase's code, tests, docs, ADRs, and plan updates. Do not include next-phase exploration, temporary debugging, storage, dist, secrets, or unrelated local changes.

PRs or handoffs should state the changed surface, linked plan/bug/ADR, validation commands, and visible UI/Figma/artifact evidence. New environment variables require updates to `.env.example` and `docs/reference/env-vars.md`.

## Agent-Specific Guardrails

Do not restore removed M29 Direct compare, legacy M30 materialization product paths, M31-M39/M39.1 runtime, routes, environment variables, or legacy ONNX proposer. When old ADRs, completed plans, or legacy drafts mention those paths, treat them as historical background only.

M29 perception model report is opt-in and report-only; it may propose bbox candidates but must not create source objects, DSL nodes, assets, replay authorization, or cleanup authorization. M29 perception source compiler is the opt-in bridge from model proposals into enhanced M29.2 source ownership; compiled objects must still flow through M29.3/M29.4/M29.5 before materialization. M29 perception fate trace is diagnostic-only and must not feed source ownership, M29.5, materializer, Renderer, or plugin decisions. This opt-in model-first path is not the removed legacy ONNX proposer runtime and must not revive that legacy route/module family.

M29.4 weak cluster, M29 ownership conservation, M29.6 media internal decomposition, M29 transparent asset report, M29 evidence contract report, M29 hierarchy candidates, M29 sibling group candidates, M29 layout energy, M29 Auto Layout permission, M29 design token, and M29 B-stage quality reports are evidence/permission/diagnostic surfaces. C-stage materialization may consume high-confidence structural evidence only to create transparent controlled structure groups around already replayed nodes. It must not create Auto Layout, Figma Component/Instance, variables, variants, vectors, or new visible owner nodes. M29.6 must not promote internal media candidates or authorize cleanup by itself. M29 transparent asset report may generate diagnostic RGBA artifacts only; it must not replace materialized assets or authorize cleanup by itself. M29 evidence contract report may combine M29.6, transparent asset, ownership, relation, and risk evidence into `allow_visible_replay` / `report_only` / `reject`, but remains report-only and cannot create source objects or cleanup authorization by itself. M29 internal source promotion is the compatibility bridge from M29.6/transparent/evidence-contract evidence back into M29.2 source ownership, and promoted objects must be reprocessed through M29.3/M29.4/M29.5 before materialization. M29.5 replay plan is still the only source for materialization order, node budget, dedupe, visible internal icon replay, and cleanup authorization. The M29 plan-driven materializer must not reclassify owners or add cleanup authorization.

Source ownership defects must be fixed in raw M29 or M29.2. Do not patch them in the materializer, Renderer, or plugin with color, copy, theme, industry, filename, or fixed-bbox special cases. Root/page background must come from source PNG sampling; do not restore a fixed light default to hide fallback-off failures.
