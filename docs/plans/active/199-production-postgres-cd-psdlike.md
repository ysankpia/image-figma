# 199 Production Postgres, CD, and PSD-like Service

## Task Contract

## Objective

Finish the remaining productionization work for Slice Studio:

```text
existing RackNerd server
-> Postgres-backed empty production database with bootstrap owner
-> PSD-like text-style service under systemd
-> GitHub Actions CD
-> backup / deployment docs
-> verified production user workflow
```

## Standards Read

- `AGENTS.md`
- `docs/index.md`
- `docs/runbooks/slice-studio-production-deploy.md`
- `docs/reference/slice-studio-runtime.md`
- `docs/reference/env-vars.md`
- `docs/plans/active/198-slice-studio-manual-workflow-hardening.md`
- `docs/plans/completed/196-user-only-surface-simplification.md`
- deploy skill references for RackNerd, GitHub Actions CD, and post-deploy verification
- stage-gated dev agent references for harnessed repos, unattended execution, validation, and reports

## Mode

Harnessed repository mode, long-running unattended execution.

## Affected Layers

- source input: current SQLite schema/migrations, existing RackNerd Postgres containers, existing PSD-like service code, current manual deploy runbook
- intermediate data: DB access abstraction, schema migration SQL, production env, systemd units, GitHub Actions workflow
- decision point: provider selection between SQLite and Postgres; CD transfer strategy; PSD-like production start command
- output surface: `/`, `/login`, `/register`, `/projects`, `/projects/:projectId/review`, `/settings`, `/api/*`, `project.zip/design.pen`
- validation surface: unit tests, typecheck/build, DB migration smoke, server service health, real production project flow, workflow syntax/secret validation

## Allowed Scope

- Add a Postgres database provider for current Slice Studio tables.
- Keep local SQLite available for local tests and simple development.
- Make server auth/project handlers async where database access requires it.
- Configure production env to use an existing Postgres container, with empty Slice Studio tables and one bootstrap owner.
- Install and run `services/psdlike-text-style` on the production host.
- Add GitHub Actions CD for the current native `systemd` deployment.
- Update docs and runbooks.

## Forbidden Scope

- Do not revive admin, billing, payment, quota, usage, entitlement, order, or XPay surfaces.
- Do not delete user storage unless explicitly part of a verified backup/reset step.
- Do not create a brand-new Postgres container while a reusable existing PGSQL service is available.
- Do not put secrets in repository files, logs, commit messages, or final output.
- Do not use the old Pencil Python backend as the production app.
- Do not pretend Postgres is active before the production API is actually running against it.

## Commands

- build: `pnpm run build`
- test: `pnpm run check`
- DB smoke: `bun run smoke:db-migrations`
- local API smoke: `bun run smoke`
- production validation: inside-out `systemctl`, `/api/health`, real project smoke, export smoke
- CD validation: `gh workflow list`, `gh workflow run deploy.yml`, `gh run watch`, production health after workflow

## Dataset / Artifacts

- Production domain: `https://image.figma.245162.xyz`
- Server app path: `/opt/slice-studio/app`
- Server storage path: `/opt/slice-studio/storage`
- Server env: `/opt/slice-studio/env/slice-studio.env`
- Existing Postgres candidates observed on server:
  - `jianzhi-postgres` on `127.0.0.1:15432`
  - `adam-postgres` on `127.0.0.1:15433`
  - `baodan-db` on `127.0.0.1:43887`
  - internal-only `sub2api-postgres`

## Acceptance Criteria

- App can run locally with SQLite provider unchanged enough for tests/smoke.
- App can run with Postgres provider using the current user-only schema.
- Production database starts empty except bootstrap owner/session data created by app startup.
- Production API/Web run against Postgres and pass real smoke:
  - sign in
  - create temporary project
  - upload PNG
  - save slice
  - export assets
  - export project
  - delete temporary project
- PSD-like text-style service runs under systemd and production API uses `SLICE_STUDIO_TEXT_STYLE_PROVIDER=psdlike`.
- GitHub Actions CD exists, uses RackNerd Cloudflare tunnel or another verified SSH route, and can deploy the current app.
- Backup/runbook docs explain storage, env, Postgres, services, CD, and rollback.

## Stage Plan

1. Stage 0: Freeze facts and create plan.
2. Stage 1: Add async DB abstraction with SQLite and Postgres providers; update auth/projects/API handlers.
3. Stage 2: Add Postgres schema migration/smoke; validate locally.
4. Stage 3: Configure production Postgres using existing server PGSQL; deploy and validate empty DB plus owner.
5. Stage 4: Install PSD-like service under systemd; switch production style provider to `psdlike`; validate export path.
6. Stage 5: Add GitHub Actions CD workflow and required secrets; run workflow; validate production.
7. Stage 6: Add backup/rollback docs and final validation report; commit/push staged changes.

## Git Policy

Commit stage-scoped changes only after validation. Do not stage runtime storage, databases, zips, `.pen`, `.env`, build output, or server-only secrets.

## Stop Conditions

- Existing Postgres credentials cannot be safely retrieved or used without leaking secrets.
- Postgres migration requires a broader schema/product contract change than current user-only Slice Studio.
- Async DB conversion breaks export/auth/project flows in a way that cannot be repaired within three focused attempts.
- PSD-like service dependency install fails on the server and no pinned Python/uv path can be made reliable.
- GitHub Actions cannot access RackNerd without adding an unsafe personal key or exposing secrets.

## Stage Report: 2026-06-19 Postgres / PSD-like / CD Setup

## Scope

Implemented the current production data/service deployment path without reviving admin, billing, payment, entitlement, usage, quota, or XPay.

## Changed Files

- `server/db.ts`
- `server/db-migrations.ts`
- `server/auth.ts`
- `server/projects.ts`
- `server/index.ts`
- `server/exporter.ts`
- `server/pencil-exporter.ts`
- `server/ai-slice-boxes/index.ts`
- `server/config.ts`
- `scripts/db-migration-smoke.ts`
- `scripts/postgres-smoke.ts`
- `.github/workflows/deploy.yml`
- `package.json`
- `pnpm-lock.yaml`
- `README.md`
- `PROGRESS.md`
- `docs/reference/env-vars.md`
- `docs/reference/slice-studio-runtime.md`
- `docs/runbooks/slice-studio-production-deploy.md`

## Validation

| item | value |
|---|---|
| local typecheck/tests | `pnpm run check` passed, 12 files / 108 tests |
| local build | `pnpm run build` passed |
| local SQLite migration smoke | `bun run smoke:db-migrations` passed |
| local API smoke | `bun run smoke` passed against SQLite |
| server Postgres smoke | `bun scripts/postgres-smoke.ts` passed against `slice_studio` DB |
| server build | `pnpm exec tsc -p tsconfig.json --noEmit` and `pnpm run build` passed on RackNerd |
| server services | `slice-studio-text-style`, `slice-studio-api`, `slice-studio-web` active |
| server health | `127.0.0.1:4120/health`, `127.0.0.1:4110/api/health`, `127.0.0.1:3010` passed |
| server real smoke | `SLICE_STUDIO_API_URL=http://127.0.0.1:4110 bun run smoke` passed against Postgres |
| source-origin HTTPS | `curl --resolve image.figma.245162.xyz:443:192.236.242.152 https://image.figma.245162.xyz/api/health` passed |
| Cloudflare public HTTPS | recovered and passed after edge certificate propagation |

## Acceptance Result

| criterion | result | evidence |
|---|---|---|
| Local SQLite still works | passed | local migration smoke and API smoke |
| Postgres provider works | passed | server Postgres smoke and real app smoke |
| Production DB empty plus bootstrap owner | passed | `slice_studio` DB reset by smoke, app startup bootstrapped owner |
| PSD-like service runs | passed | `slice-studio-text-style` active, `/health` returned `{"ok":true}` |
| GitHub Actions CD exists and deploys | passed | push-triggered run `27780640649` succeeded |
| Public HTTPS URL works through Cloudflare | passed | `https://image.figma.245162.xyz/api/health` and public real smoke passed |

## Failed / Degraded Cases

| case | symptom | suspected root cause | status |
|---|---|---|---|
| `https://image.figma.245162.xyz` through normal DNS | temporary TLS handshake failure after Caddy/Cloudflare certificate propagation | Cloudflare edge certificate propagation lag | recovered; public health and smoke passed |

## Architecture Contract Check

The database provider change is limited to the current user-only Slice Studio tables: users, sessions, projects, pages, slices, and schema migrations. It does not reintroduce removed admin/billing/payment tables or API routes.

## Anti-Overfitting Check

No page, project, image, user, coordinate, or sample-specific production logic was added. The Postgres smoke uses a disposable project and current table contract, not a fixture-specific branch.

## Next Stage

Finish final documentation cleanup and move plan 199 to completed after final validation remains green.
