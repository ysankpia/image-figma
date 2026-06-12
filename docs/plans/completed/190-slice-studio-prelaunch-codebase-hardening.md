# Plan 190: Slice Studio Prelaunch Codebase Hardening

## Status
Completed.

## Objective
Resolve the practical prelaunch issues in the current codebase before formal multi-user launch work accelerates: stabilize the AI provider boundary for OpenRouter/OpenAI-compatible providers, protect existing local project data, reduce root-level confusion from legacy code, and make Slice Studio the obvious product mainline without deleting useful research assets.

This plan complements [189-slice-studio-multi-user-production-launch.md](189-slice-studio-multi-user-production-launch.md). Plan 189 defines the formal SaaS target. Plan 190 is the codebase and local-product cleanup layer that should run before or alongside the first implementation burst.

## Concrete analysis

### Concrete object
The concrete object is the current `image-figma` repository, with `apps/slice-studio` as the active product and many legacy/reference directories still present at root or near-root level.

### Known facts
- Current active product code lives in `apps/slice-studio`.
- Current local runtime data lives under `apps/slice-studio/storage/`.
- Current git status is clean before this plan is created.
- `pnpm --dir apps/slice-studio run check` passes.
- `pnpm --dir apps/slice-studio run build` passes.
- `pnpm -r run check` passes for the current workspace.
- Current AI slice provider already has env boundaries for base URL, API key, model, timeout, retries, and model request settings.
- Current repo still contains historical/reference directories: `backend/`, `services/*`, `figma-plugin/`, `packages/*`, `Figma-design/`, historical docs, `output/`, `tmp/`, and `runs/`.
- Existing local project data must not be deleted or stranded by any directory move.

### Unverified assumptions
- The final repository shape may either keep `apps/slice-studio` as the app path with stronger root documentation, or promote Slice Studio to a root-level app layout.
- OpenRouter will be available tomorrow through a user-provided API key.
- The first OpenRouter integration can use an OpenAI-compatible chat-completions style API if the selected model does not support Responses API.
- Existing local storage contains useful development projects and should be preserved even if app paths change.

### Main contradiction
The main contradiction is that the codebase already has a clear current product, but the filesystem still looks like a research monorepo. Moving things too aggressively can break local data and historical reference value; not moving or labeling anything leaves the next implementation run vulnerable to touching the wrong layer.

The first move is therefore not a blind root rewrite. The first move is a data-safe inventory, then a minimal mainline clarity change, then provider hardening, then production feature work.

## Prelaunch issue ledger

### P0: Existing local data must survive all cleanup
Risk:
- `apps/slice-studio/storage/app.sqlite` and `apps/slice-studio/storage/projects/` contain current local projects.
- If Slice Studio is moved or storage defaults change, the app may appear empty or exports may break.

Required work:
- Create a timestamped local backup before structural changes:

  ```text
  backups/slice-studio-storage-{timestamp}/app.sqlite
  backups/slice-studio-storage-{timestamp}/projects/
  ```

- Do not commit the backup.
- Add or update a runbook documenting backup/restore.
- If any app path changes, explicitly set `SLICE_STUDIO_STORAGE_ROOT` so old project data remains discoverable.
- Run a real project smoke after any path change.

Acceptance:
- Existing projects still list in `/projects`.
- Existing project page images still load.
- Existing slices still save and export.
- `assets.zip` and `project.zip` export from an existing project.

### P0: OpenRouter/OpenAI-compatible provider hardening
Risk:
- Current provider is configured as OpenAI Responses-oriented.
- Different OpenAI-compatible providers vary in endpoint path, request shape, response shape, model capability, timeout behavior, and error format.
- Prior failures around 502/provider instability show this is a real use risk.

Required work:
- Introduce a provider mode that can support:

  ```text
  responses
  chat_completions
  ```

- Keep env names simple for user setup:

  ```text
  SLICE_STUDIO_AI_SLICE_BASE_URL
  SLICE_STUDIO_AI_SLICE_API_KEY
  SLICE_STUDIO_AI_SLICE_MODEL
  SLICE_STUDIO_AI_SLICE_WIRE_API
  ```

- Make OpenRouter usable by env only:

  ```text
  SLICE_STUDIO_AI_SLICE_BASE_URL=https://openrouter.ai/api/v1
  SLICE_STUDIO_AI_SLICE_MODEL=<model-name>
  SLICE_STUDIO_AI_SLICE_WIRE_API=chat_completions
  ```

- Add provider request/response diagnostics that redact:
  - API key;
  - base64 image payloads;
  - full source images;
  - user project data not needed for debugging.
- Preserve the existing AI box output contract:

  ```text
  provider response
  -> parsed boxes
  -> server tile/overview merge
  -> frontend normal SliceRecord save
  ```

- Add tests for:
  - chat-completions response extraction;
  - provider 4xx/5xx error normalization;
  - invalid JSON recovery;
  - no secret leakage in debug output.

Acceptance:
- Current OpenAI Responses path still works.
- OpenRouter-style chat completions path works with a fake provider test.
- User only needs base URL, API key, and model name, plus wire API when required.
- AI provider errors are actionable and do not expose secrets.

### P0: Root-level direction must be hard to misread
Risk:
- The repository root still contains many old product/research surfaces.
- An agent or developer can enter `backend/`, `services/pencil-python-backend/`, `figma-plugin/`, or `packages/image-to-figma-renderer/` and mistake it for the current delivery path.

Required work:
- Keep `AGENTS.md`, `PROGRESS.md`, `docs/index.md`, and `docs/engineering/current-code-map.md` as the authority chain.
- Add a root-level concise mainline section to `README.md` if it is not already clear enough.
- Add short marker README files to major legacy directories only if current docs are not enough:

  ```text
  backend/README.md
  services/README.md
  figma-plugin/README.md
  packages/README.md
  ```

- These marker files must not delete or devalue the code. They must state:

  ```text
  current product is apps/slice-studio
  this directory is reference/deferred unless explicitly targeted
  read docs/engineering/legacy-code-inventory.md before modifying
  ```

Acceptance:
- A new agent starting from root sees `apps/slice-studio` as the current product within one minute.
- Legacy code remains available as reference.
- No functional code is moved or deleted in this step.

### P1: Decide whether to promote Slice Studio to root
Risk:
- Moving `apps/slice-studio` to root may make the repo feel cleaner, but it touches imports, workspace config, build scripts, env paths, storage defaults, docs, and existing data.
- Keeping `apps/slice-studio` may be less pretty, but it is currently stable and documented.

Decision rule:
- Do not physically move the app until after P0 provider/data checks unless there is a strong operational reason.
- Prefer a non-destructive first cut:

  ```text
  root README and scripts point to apps/slice-studio
  root scripts wrap Slice Studio commands
  storage root is explicit
  legacy markers reduce confusion
  ```

- Only promote to root if the following are accepted:
  - storage migration plan exists;
  - all imports/build scripts update cleanly;
  - `pnpm -r run check` passes;
  - existing local projects still load;
  - docs and runbooks update in the same commit.

Acceptance if not moving:
- Root commands make Slice Studio feel primary.
- No current behavior changes.

Acceptance if moving:
- Existing storage is preserved through explicit env or migration.
- Old path is not left as a broken duplicate.
- All docs point to the new path.

### P1: Runtime artifact and ignored-file discipline
Risk:
- The working directory has many ignored artifacts: `.env.local`, `.next/`, `storage/`, `node_modules/`, `output/`, `tmp/`, `runs/`, Python venvs, caches, and service storages.
- These are normal locally but unsafe for deployment packaging.

Required work:
- Keep current ignore rules.
- Add a release packaging rule: deploy from clean checkout or explicit package, never by copying the live working directory.
- Add a pre-deploy artifact check:

  ```bash
  git status --short --branch
  git ls-files | rg "\\.zip$|\\.pen$|\\.sqlite$|\\.db$|\\.env\\.local$|(^|/)\\.next/|(^|/)dist/|(^|/)storage/"
  ```

- Document which ignored paths may contain useful local data and must not be deleted casually.

Acceptance:
- No runtime data is tracked by Git except `apps/slice-studio/storage/.gitkeep`.
- Release/deploy docs warn against copying ignored local artifacts.

### P1: Live smoke must be repeatable
Risk:
- Static tests pass, but browser/API smoke is the only proof that upload, save, AI, and export work together.

Required work:
- Keep `apps/slice-studio/scripts/smoke.ts` as the local API smoke.
- Add a documented smoke checklist for:
  - existing project load;
  - new project create;
  - upload;
  - manual slice;
  - AI current page;
  - AI all pages;
  - export assets;
  - export project;
  - Pencil open/inspect when needed.
- For OpenRouter integration, add a fake-provider automated test and one real-provider manual smoke when the user provides a key.

Acceptance:
- `pnpm --dir apps/slice-studio run check` passes.
- `pnpm --dir apps/slice-studio run build` passes.
- `pnpm -r run check` passes when broader repo changes are made.
- `bun run smoke` passes against a running API for non-AI paths.
- A real AI smoke is recorded when provider credentials exist.

### P2: Legacy physical relocation
Risk:
- Physically moving old code into an archive directory is expensive and can break imports, docs, tests, and historical paths.
- The current docs already classify legacy code.

Required work:
- Do not move legacy source directories in the first cleanup burst.
- If physical relocation is still desired later, create a separate plan with:
  - source path inventory;
  - import/reference grep;
  - docs link rewrite;
  - validation per moved surface;
  - rollback plan.

Acceptance:
- Legacy code is either clearly marked in place or moved with complete path rewrites and validation.

## Recommended execution order

1. Backup and verify current local storage.
2. Add root/mainline clarity docs and marker READMEs if needed.
3. Add root scripts or README commands that make Slice Studio the default product without moving the app.
4. Harden AI provider adapter for OpenRouter/OpenAI-compatible chat completions.
5. Run automated checks and local smoke.
6. With a real OpenRouter key, run AI current page and AI all pages on a known project.
7. Only then decide whether physical app promotion to root is worth it.
8. Continue plan 189: auth/session, ownership, production storage/database, entitlement, payment.

## Non-goals

- Do not delete local project storage.
- Do not commit `.env.local`, SQLite, project storage, ZIP, `.pen`, `.next`, `output`, `tmp`, or `runs`.
- Do not physically move legacy directories without a separate relocation plan.
- Do not rewrite Review Workbench UI.
- Do not change AI prompt semantics unless provider request format requires it.
- Do not choose a payment provider in this plan.
- Do not implement multi-user auth in this plan; that belongs to plan 189.

## Validation plan

Baseline:

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
pnpm -r run check
git diff --check
git status --short --branch
```

Storage/data:

```text
record current project count
backup storage
start app
load existing project
export assets.zip
export project.zip
confirm storage still points to the expected root
```

AI provider:

```text
fake OpenRouter-compatible response test passes
provider error normalization tests pass
real OpenRouter key smoke passes when key is available
AI boxes merge into normal saved slices
```

Repository clarity:

```text
new root reader can identify apps/slice-studio as current product
legacy directories explicitly point to legacy inventory
no tracked runtime artifacts or secrets
```

## Completion criteria

Plan 190 is complete when:

- current local data is backed up and verified;
- root-level docs make Slice Studio unambiguously primary;
- legacy/reference areas are clearly marked without deleting useful code;
- OpenRouter/OpenAI-compatible AI provider use is implemented and tested through the existing provider boundary;
- checks and smoke evidence are recorded;
- plan 189 can continue without first untangling repository layout or AI provider instability.

## Completion evidence

Completed on 2026-06-13.

- Storage backup exists at `backups/slice-studio-storage-20260613-023319` with `projects=17`, `pages=47`, `slices=643`, size `223M`.
- Root scripts now route default dev/check/build/smoke commands to `apps/slice-studio`.
- Marker READMEs identify `apps/slice-studio` as the current product and keep `backend/`, `services/`, `figma-plugin/`, and `packages/` as reference/deferred unless explicitly targeted.
- AI slice provider now supports `responses` and `chat_completions` wire formats through `SLICE_STUDIO_AI_SLICE_WIRE_API`.
- OpenRouter-style configuration is documented with `SLICE_STUDIO_AI_SLICE_BASE_URL=https://openrouter.ai/api/v1` and `SLICE_STUDIO_AI_SLICE_WIRE_API=chat_completions`.
- Provider request/response tests cover Responses payloads, chat-completions payloads, text extraction, URL normalization, bare JSON recovery, and redacted provider diagnostics.
- Validation passed:
  - `pnpm --dir apps/slice-studio run check`
  - `pnpm --dir apps/slice-studio run build`
  - `pnpm -r run check`
  - `pnpm --dir apps/slice-studio run smoke`
  - `git diff --check`
- Browser smoke passed on `http://127.0.0.1:3010/projects`: existing local projects rendered, `17` projects were visible, and browser console had no errors.
- Browser smoke passed on `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`: source image and 7 asset previews loaded, Konva canvas rendered, no horizontal document overflow, and browser console had no errors.
- Real OpenRouter provider smoke remains pending until a real API key and model are provided. The fake OpenAI-compatible provider boundary is implemented and covered by tests.
