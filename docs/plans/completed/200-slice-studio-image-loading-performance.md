# 200 Slice Studio Image Loading Performance

## Objective

Reduce review workbench and project-list latency for projects with many large screenshots without changing export correctness.

The source PNG remains the truth for cropping, AI source reads, `assets.zip`, and `project.zip/design.pen`. UI navigation surfaces should use derived thumbnails and load original page images only when the user actually opens that page.

## Current Bottleneck

`ReviewWorkbenchClient` used to hydrate every page by loading every `sourceUrl` into an `HTMLImageElement` during project load. A 10-20 page project therefore downloaded and decoded all full original screenshots before the user could comfortably work. The project list also used first-page source images for card previews.

## Scope

- Add a page thumbnail URL to `PageRecord`.
- Generate a small server-side thumbnail when pages are uploaded or replaced.
- Lazily backfill thumbnails for existing projects when `/thumbnail` is requested.
- Use thumbnails in project cards and the review page rail.
- Load full original images only for the active canvas page.
- Keep all exports and slice previews reading original images.
- Add tests that lock the thumbnail contract.

## Non-Goals

- Do not store only compressed uploads.
- Do not change export crop coordinates.
- Do not change the database schema.
- Do not add service workers or browser cache layers in this pass.
- Do not change AI detection or Pencil export behavior.

## Acceptance

- `/api/projects/:projectId/pages/:pageId/thumbnail` serves a small derived PNG.
- `PageRecord.sourceUrl` still points to the original source image route.
- `PageRecord.thumbnailUrl` points to the thumbnail route.
- Left page rail and project card previews use `thumbnailUrl`.
- Active canvas uses `sourceUrl` and loads it on demand.
- Page replace/delete keeps thumbnail cache consistent with the source.
- Tests, typecheck, build, and diff whitespace checks pass.

## Stage Report: 2026-06-19

Implemented the minimal image-loading split:

- `PageRecord` now carries `thumbnailUrl` next to `sourceUrl`.
- Upload and page replacement write a 360px-wide derived PNG under project `thumbnails/`.
- Existing projects lazily backfill thumbnails through the new thumbnail route.
- Project cards and the review page rail use thumbnails.
- The canvas no longer preloads every page source image; it loads the active page source on demand and keeps already loaded page images unless the page source is replaced.
- Delete/replace removes or rolls back derived thumbnails so they cannot become a second truth source.

Validation:

| check | result |
|---|---|
| targeted tests | `pnpm exec vitest run tests/storage.test.ts tests/manifest.test.ts tests/ai-slice-boxes.test.ts` passed, 27 tests |
| typecheck | `pnpm exec tsc -p tsconfig.json --noEmit` passed |
| full check | `pnpm run check` passed, 12 files / 108 tests |
| build | `pnpm run build` passed |
| whitespace | `git diff --check` passed |
| real API smoke | temporary project uploaded a 1400x900 PNG; `/source` stayed 1400x900 / 26997 bytes, `/thumbnail` returned 360x231 / 197 bytes, and `export-assets` returned a signed ZIP URL |
