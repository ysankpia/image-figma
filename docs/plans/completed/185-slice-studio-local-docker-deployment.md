# 185 Slice Studio Local Docker Deployment

Status: completed

## Summary

Package Slice Studio into a local Docker deployment so the system can be used tomorrow morning from one stable local URL without exposing it to a public server.

This is a self-use deployment, not production SaaS. The priority is that `apps/slice-studio` is available at a local browser URL with persistent storage and the current AI/OCR configuration loaded from local environment variables.

## Input normalization

- User-provided input: deploy locally with Docker first, do not publish to a server yet, keep the project usable tomorrow morning.
- Truth sources: `apps/slice-studio`, `docs/product/direction-contract.md`, `docs/engineering/validation.md`, current `.env.local` runtime configuration.
- Evidence/reference sources: Docker local runtime, previous Slice Studio checks/builds, current storage layout.
- Missing inputs: no blocker; local `.env.local` exists and must not be committed.
- Final output: local Docker/Compose deployment and a browser link.

## Scope

- Add Slice Studio Dockerfile, local compose file, and production start script.
- Make production web use same-origin `/api` with Next rewrite to the internal API.
- Persist storage through `apps/slice-studio/storage`.
- Add local Docker deployment runbook.
- Update `PROGRESS.md`.
- Validate with check/build, Docker build, container health check, and browser-accessible page.

## Non-goals

- No public server deployment.
- No auth system.
- No PostgreSQL migration.
- No physical movement/deletion of legacy code.
- No cloud storage.
- No domain/HTTPS setup.

## Affected layers

- Source input: Slice Studio Docker packaging and runtime env.
- Intermediate data: `.env.local` and persistent storage mount.
- Decision point: local Docker runtime as tomorrow's usable surface.
- Output surface: `http://127.0.0.1:51230/projects`.
- Validation surface: Docker container, health endpoint, web page, check/build.

## Validation

- `pnpm --dir apps/slice-studio run check`
- `pnpm --dir apps/slice-studio run build`
- `docker compose -f apps/slice-studio/docker-compose.local.yml up -d --build`
- `curl http://127.0.0.1:51230/api/health`
- `curl -I http://127.0.0.1:51230/projects`
- `git diff --check`
- `git status --short --branch`

## Validation results

- `pnpm --dir apps/slice-studio run check`: passed; TypeScript passed and Vitest reported 8 files / 52 tests passed.
- `pnpm --dir apps/slice-studio run build`: passed; Next standalone build produced `/projects` and `/projects/[projectId]/review`.
- `docker compose -f apps/slice-studio/docker-compose.local.yml up -d --build`: passed; `slice-studio-local` is running.
- `curl http://127.0.0.1:51230/api/health`: returned `{"ok":true}`.
- `curl -I http://127.0.0.1:51230/projects`: returned `HTTP/1.1 200 OK`.
- Browser validation opened `http://127.0.0.1:51230/projects` and showed 11 existing projects from the mounted local storage.
- Storage validation confirmed `/data/slice-studio/app.sqlite` is visible inside the container through the `apps/slice-studio/storage` bind mount.

## Legacy code handling

This plan does not move old code. Physical archive/prune is deferred until after the local Docker deployment is usable. Current docs already classify old code; the next safe step is a separate legacy cleanup plan after deployment validation.
