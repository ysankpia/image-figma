# Plan 192: Promote Slice Studio To Repository Root

## Status
Completed.

## Objective
Move the current Slice Studio Next/Elysia app from `apps/slice-studio/` to the repository root so the root directory is the product application, while preserving existing local project data.

## Concrete analysis

### Concrete object
The active app currently lives in:

```text
apps/slice-studio/
```

It owns:

```text
app/
components/
server/
shared/
scripts/
tests/
storage/
package.json
next.config.ts
tsconfig.json
```

### Known facts
- `server/config.ts` defaults `storageRoot` to `process.cwd()/storage`.
- If the app runs from the repository root, the natural storage path becomes `storage/`.
- Existing local project data currently lives in `apps/slice-studio/storage/`.
- Plan 190 created a backup before structural work.

### Main contradiction
Keeping Slice Studio in `apps/slice-studio` preserves stability but keeps the main product hidden in a subdirectory. Moving it to root clarifies ownership, but only if storage, env, docs, scripts, and validation move with it.

## Target structure

```text
app/
components/
server/
shared/
scripts/
tests/
storage/
package.json
next.config.ts
tsconfig.json
next-env.d.ts
```

`apps/` should be removed if empty after the move.

## Result

- Promoted Slice Studio source/config/test files to the repository root:
  `app/`, `components/`, `server/`, `shared/`, `scripts/`, `tests/`, `package.json`, `next.config.ts`, `tsconfig.json`, `next-env.d.ts`.
- Moved local runtime data from `apps/slice-studio/storage/` to root `storage/`; observed existing local project count remained `17`.
- Copied Slice Studio local env keys to root `.env.local` and backed up the previous root env as ignored `.env.local.legacy-backup-*`.
- Replaced root package scripts so `pnpm run dev`, `pnpm run check`, `pnpm run build`, and `pnpm run smoke` run Slice Studio directly.
- Scoped `tsconfig.json` and `vitest.config.ts` to the current root app so archived code is not compiled or tested as current product code.
- Removed the empty `apps/` directory after preserving data and env.

## Required work

- Move Slice Studio tracked source/config files to root.
- Move local `apps/slice-studio/storage/` to root `storage/` without committing runtime data.
- Merge/replace root package metadata so root scripts run Slice Studio directly.
- Update `.gitignore` for root `.next/`, `storage/`, `*.tsbuildinfo`, and runtime artifacts.
- Update current docs from `apps/slice-studio` to root paths.
- Update Go M29 fallback path to the archived location.
- Keep existing local `.env.local` data available for root runtime without committing secrets.

## Validation

```bash
pnpm install
pnpm run check
pnpm run build
pnpm run smoke
git diff --check
git status --short --branch
```

Browser smoke:

```text
http://127.0.0.1:3010/projects shows existing projects.
An existing review page loads source image, assets, and canvas.
```

## Completion criteria

- `pnpm run dev` starts Slice Studio from the repository root.
- Existing local projects still list.
- Existing source images and asset previews still load.
- `pnpm run check`, `pnpm run build`, and `pnpm run smoke` pass.
- Current documentation no longer identifies `apps/slice-studio` as the active code path.
