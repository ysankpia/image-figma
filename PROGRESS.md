# Progress

This file is the live execution ledger for Image-to-Figma Design. It does not replace `docs/roadmap.md`, active plans, bug records, or validation docs.

## Current objective

Keep Slice Studio local Docker deployment usable for self-use and defer public server deployment until access control and storage migration are planned.

## Active plan

- Current plan: none. Latest completed plan: `docs/plans/completed/185-slice-studio-local-docker-deployment.md`

## Current phase

Local Docker self-use

## Now

- Slice Studio is running locally in Docker at `http://127.0.0.1:51230/projects`.
- Keep the container and `apps/slice-studio/storage` available for immediate self-use.
- Keep legacy code in place; physical archive/prune remains deferred until a separate cleanup plan.

## Done

- 2026-06-12: confirmed the current code and completed plans identify `apps/slice-studio` as the working product surface.
- 2026-06-12: added direction contract and progress ledger.
- 2026-06-12: updated root README, AGENTS, docs index, roadmap, product docs, architecture docs, engineering docs, runbooks, env vars, bug/reference entries, code map, and legacy inventory to route default product work to Slice Studio.
- 2026-06-12: moved plan 184 to completed.
- 2026-06-12: documentation sync commit was created and pushed.
- 2026-06-12: AI inclusive-icons prompt commit was created and pushed.
- 2026-06-12: added local Docker packaging for `apps/slice-studio`.
- 2026-06-12: started `slice-studio-local` with `apps/slice-studio/storage` mounted at `/data/slice-studio`.
- 2026-06-12: validated Docker URL `http://127.0.0.1:51230/projects`; browser showed 11 existing projects from local storage.
- 2026-06-12: validated a mounted project source image through the Docker URL; `/api/.../source` returned `image/png`.
- 2026-06-12: moved plan 185 to completed.

## Next

- Use the local Docker URL for the next real batch of screenshots.
- Before public server deployment, add access control and decide SQLite storage migration/backup strategy.
- Create a separate legacy cleanup/archive plan only after current Docker use is stable.

## Blocked or deferred

- Legacy code physical movement/deletion is deferred. The safe current state is docs-level classification plus a future explicit cleanup plan.
- Public server deployment, auth, PostgreSQL, domain, and HTTPS are deferred until local Docker use is validated.

## Validation log

- 2026-06-12: previous documentation sync validation passed: `git diff --check`, Slice Studio check/build.
- 2026-06-12: previous AI prompt validation passed: `pnpm --dir apps/slice-studio run check`, `pnpm --dir apps/slice-studio run build`, `git diff --check`.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed; TypeScript passed and Vitest reported 8 files / 52 tests.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed.
- 2026-06-12: `docker compose -f apps/slice-studio/docker-compose.local.yml up -d --build` passed.
- 2026-06-12: `curl http://127.0.0.1:51230/api/health` returned `{"ok":true}`.
- 2026-06-12: `curl -I http://127.0.0.1:51230/projects` returned `HTTP/1.1 200 OK`.
- 2026-06-12: browser validation opened `http://127.0.0.1:51230/projects` and showed 11 existing projects.
- 2026-06-12: container storage validation confirmed `/data/slice-studio/app.sqlite` is mounted from `apps/slice-studio/storage/app.sqlite`.
- 2026-06-12: Docker source-image validation returned `HTTP/1.1 200 OK` and `Content-Type: image/png` for an existing project's first page source URL.

## Failure attempt ledger

- None recorded.

## User input needed

- None recorded.

## Last checkpoint

- 2026-06-12: local Docker deployment is running at `http://127.0.0.1:51230/projects`; code changes pending commit.
