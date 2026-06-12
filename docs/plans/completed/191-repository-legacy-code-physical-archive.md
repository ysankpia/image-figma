# Plan 191: Repository Legacy Code Physical Archive

## Status
Completed.

## Objective
Move non-mainline source code out of the repository root so the current product path is no longer mixed with historical services, plugin runtimes, renderer packages, and experiments. This is a physical relocation, not deletion.

## Concrete analysis

### Concrete object
The current `image-figma` repository contains the active Slice Studio app plus older product and research surfaces at root-level paths:

```text
backend/
services/
figma-plugin/
packages/
Figma-design/
tests/
tools/
go.work
tsconfig.base.json
```

### Known facts
- Before this cleanup, current product code lived in `apps/slice-studio`.
- Plan 192 promotes Slice Studio to the repository root after this archive step.
- Plan 190 already marked the older directories as reference/deferred/fallback, but did not physically move them.
- Current Slice Studio no longer imports runtime code from these old paths by default.
- The old paths remain valuable as implementation and research reference.

### Main contradiction
The old code is useful as reference, but root-level placement makes it look like current product code. The correct move is to archive it in-place under an explicit archive namespace, not delete it and not keep it beside the main product.

## Target structure

```text
archive/legacy-code/
  backend/
  services/
  figma-plugin/
  packages/
  Figma-design/
  tests/
  tools/
  go.work
  tsconfig.base.json
```

The archive directory is kept in Git. Runtime artifacts inside those directories remain ignored by existing ignore rules.

## Result

- Moved root-level legacy/reference source directories into `archive/legacy-code/`.
- Added `archive/legacy-code/README.md` to explain archive status and recovery rules.
- Updated root `.gitignore` so archived runtime artifacts such as storage, tmp, bins, build output, SQLite, and DB files remain ignored.
- Updated current code maps, inventory, runbooks, env docs, validation docs, and repository rules so archived code is reference only unless a new active plan revives it.
- Removed the empty root `tools/` directory.

## Required work

- Move old source/reference directories into `archive/legacy-code/`.
- Add `archive/legacy-code/README.md` explaining status and recovery rule.
- Update current documentation and workspace config so new work points to current Slice Studio code only.
- Do not move `docs/`, `output/`, `tmp/`, `runs/`, `backups/`, or local storage in this plan.
- Do not delete local user data.

## Validation

```bash
pnpm run check
pnpm run build
pnpm run smoke
git diff --check
```

Plan 192 ran the stronger Slice Studio build/smoke after promoting the app to root.

## Completion criteria

- Root no longer contains old product source directories.
- Archived code is discoverable under `archive/legacy-code/`.
- Workspace checks no longer treat archived packages as active workspace packages.
- Current docs explain that archived code is reference only unless a new plan revives it.
