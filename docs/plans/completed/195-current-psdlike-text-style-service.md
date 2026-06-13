# Plan 195: Current PSD-like text-style service

Status: completed
Created: 2026-06-14
Completed: 2026-06-14

## Objective

Promote the verified PSD-like font/style measurement behavior from plan 194
into the current Slice Studio runtime as a small, focused Python service, then
wire Slice Studio export to use it for editable Pencil text style.

The goal is not to revive the old PSD-like pipeline. The goal is to replace
the weak TypeScript coefficient font estimator with real font measurement while
keeping Slice Studio's current OCR, M29, slice ownership, knockout, and Pencil
export contracts.

## Starting Evidence

Plan 194 verified the real P10 `搜索` failure:

```text
Current TS export: fontSize=40, fontWeight=600
PSD-like measurement: fontSize=31, fontWeight=500
```

This directly targets the current visible defect: editable text in control
surfaces is too large/too bold even after geometry and owner-surface fixes.

## Architecture Decision

Create a current service:

```text
services/psdlike-text-style/
```

Do not run production code from:

```text
archive/legacy-code/services/psdlike-python/
```

Copy only the minimum needed measurement code and dependencies. The archive
stays a source reference, not a runtime dependency.

The service is measurement-only:

```text
Input: full page PNG + text items + optional ownerSurface
Output: fontSize, fontWeight, fontFamily, color, lineHeight, textAlign, measured
```

It must not decide:

```text
editable vs raster
slice ownership
shape generation
knockout
Pencil layer ordering
```

Those remain in TypeScript Slice Studio.

## Runtime Policy

Use a provider setting, not a one-off boolean:

```text
SLICE_STUDIO_TEXT_STYLE_PROVIDER=psdlike
SLICE_STUDIO_TEXT_STYLE_BASE_URL=http://127.0.0.1:4120
SLICE_STUDIO_TEXT_STYLE_TIMEOUT_SECONDS=8
```

Default provider should be `psdlike` once the service is part of the current
dev/runtime scripts.

Failure policy is fail-open:

```text
service down / timeout / non-200 / malformed item -> fall back to current TS estimator
```

Export must never fail only because text-style measurement is unavailable.

Manifest should record the audit source:

```text
textStyleSource: "psdlike" | "fallback"
```

## Scope

In scope:

- Create `services/psdlike-text-style/` with a focused FastAPI app.
- Add `/health`.
- Add `POST /api/text-style-batch`.
- Add service tests for synthetic and real-style button text measurement.
- Add TypeScript client `server/psdlike-text-style.ts`.
- Add config in `server/config.ts`.
- Refactor `server/text-reconstruction.ts` so editable text candidates are
  collected, owner surfaces are detected, one batch style call is made per
  page, and `makeTextLayer` receives optional measured style overrides.
- Keep fallback behavior deterministic and tested.
- Add dev script for the Python service and include it in the normal local dev
  workflow after validation.
- Validate on `project_mqc1wpkd_123c88b0/page_0010` and full export.

Out of scope:

- OCR provider changes.
- M29 physical bbox changes.
- Slice ownership policy changes.
- Pencil schema version changes.
- Payment/auth/production launch work.
- Any runtime dependency on `archive/legacy-code`.

## Implementation Stages

1. Extract minimal Python service.
2. Add service tests and prove `/api/text-style-batch` matches plan 194 values.
3. Add TypeScript client and fallback tests.
4. Wire text reconstruction to use one measured-style batch per page.
5. Add scripts/docs/env references.
6. Restart services and validate real page-scoped export.
7. Validate full export and Pencil artifact.

## Acceptance

- `services/psdlike-text-style` is the only production Python text-style
  service path.
- `archive/legacy-code/services/psdlike-python` is not imported or started by
  Slice Studio scripts.
- P10 `搜索` exports with `fontSize` in the `30-34` range and
  `fontWeight=500` when the service is available.
- With the service stopped, the same export still succeeds and records
  `textStyleSource="fallback"`.
- No fake raster-preserve workaround is introduced for `搜索`; the text remains
  editable.

## Validation

```bash
cd services/psdlike-text-style && uv run pytest -q
pnpm exec vitest run tests/text-reconstruction.test.ts tests/pencil-exporter.test.ts
pnpm run check
pnpm run build
git diff --check
```

Real flow:

```text
1. Start text-style service on 127.0.0.1:4120.
2. Restart Slice Studio API.
3. Export project_mqc1wpkd_123c88b0/page_0010.
4. Inspect manifest for page_0010__text_0005:
   fontSize ~= 31, fontWeight = 500, textStyleSource = psdlike.
5. Stop the service.
6. Re-export the same page and confirm export succeeds with fallback source.
7. Run full project export and inspect Pencil output.
```

## Completed Implementation

- Added the focused current service at `services/psdlike-text-style/`.
- Added `/health` and `POST /api/text-style-batch`.
- Added service tests for button/control text style measurement.
- Added TypeScript client `server/psdlike-text-style.ts`.
- Added text-style provider config:
  - `SLICE_STUDIO_TEXT_STYLE_PROVIDER`
  - `SLICE_STUDIO_TEXT_STYLE_BASE_URL`
  - `SLICE_STUDIO_TEXT_STYLE_TIMEOUT_SECONDS`
- Wired `server/text-reconstruction.ts` to collect editable text candidates,
  call one measured-style batch per page, and feed optional style overrides
  into `makeTextLayer`.
- Kept fail-open fallback: non-200, timeout, malformed response, or stopped
  service returns to the existing TS estimator.
- Added manifest audit fields:
  - `textStyleSource`
  - `textStyleMeasured`
- Updated scripts/docs/env references so `bun run dev` starts web, API, and
  text-style service.

## Validation Results

Static:

```text
cd services/psdlike-text-style && uv run pytest -q
3 passed

pnpm run check
9 test files / 82 tests passed

pnpm run build
Next.js production build passed

git diff --check
passed
```

Real page export with the service running:

```text
POST /api/projects/project_mqc1wpkd_123c88b0/pages/page_0010/export-project
-> ok=true, assetCount=30, pageCount=1

page_0010__text_0005 搜索:
fontSize=31
fontWeight=500
textStyleSource=psdlike
textStyleMeasured={width:62,height:34}
textRenderBBox={x:796,y:174,width:70,height:33}
```

Fail-open export with the service stopped:

```text
POST /api/projects/project_mqc1wpkd_123c88b0/pages/page_0010/export-project
-> ok=true, assetCount=30, pageCount=1

page_0010__text_0005 搜索:
fontSize=40
fontWeight=600
textStyleSource=fallback
```

Full project export with the service running:

```text
POST /api/projects/project_mqc1wpkd_123c88b0/export-project
-> ok=true, assetCount=532, pageCount=28

manifest textStyleSource counts:
psdlike=1330
```

Pencil validation:

```text
/private/tmp/slice-full-psdlike/package/design.pen
snapshot_layout(problemsOnly=true,maxDepth=3): No layout problems.
```

Pencil screenshot of `page_0010__frame` showed the search button label at the
reduced measured size instead of the previous oversized/bold output.
