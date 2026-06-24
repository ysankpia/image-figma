# Plan: Slice Studio → Figma via DraftRuntimeDSL

## Status: In Progress

## Context
Current `.pen` export uses a remainder PNG + flat node overlay, creating permanent seams.
This plan adds a new export path: containment tree → `DraftRuntimeDSL v1.0` → Figma Plugin.

## New Route
`GET /api/projects/:projectId/pages/:pageId/figma-dsl` → returns `DraftRuntimeDSL` JSON.

## New Files
- `shared/bbox.ts` — added `containsBbox()`
- `server/style-sampler.ts` — `sampleBgColor`, `estimateCornerRadius` (sharp)
- `server/slice-compiler.ts` — `compileSlicesToDraft()` containment tree + OCR text
- `server/export-figma-dsl.ts` — Elysia route handler
- `server/index.ts` — registered new route

## Plugin Changes
- `archive/legacy-code/figma-plugin/src/messages.ts` — added `render-slice-studio-dsl` message
- `archive/legacy-code/figma-plugin/src/main.ts` — added `renderSliceStudioDsl()` handler
- `archive/legacy-code/figma-plugin/manifest.json` — added `http://127.0.0.1:4110` to devAllowedDomains
- `archive/legacy-code/figma-plugin/src/ui.html` — added Slice Studio import section

## Validation
```bash
pnpm run check
pnpm run build
curl http://127.0.0.1:4110/api/projects/{id}/pages/{pageId}/figma-dsl
```
