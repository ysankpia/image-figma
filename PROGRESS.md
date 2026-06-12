# Progress

This file is the live execution ledger for Image-to-Figma Design. It does not replace `docs/roadmap.md`, active plans, bug records, or validation docs.

## Current objective
Completed dense PC UI Pencil export text-layer coordination fix without reviving legacy services or disabling OCR globally.

## Active plan
- Current plan: `docs/plans/completed/185-slice-studio-dense-pc-text-ownership-arbiter.md`

## Current phase
Slice Studio export hardening completed

## Now
- Text ownership arbiter is implemented and validated on the dense PC sample.
- Bug 024 is resolved.
- No AI prompt, SQLite, storage contract, Pencil schema, OCR provider, frontend UI, Docker, or legacy service change was made.

## Done
- 2026-06-12: implemented Slice Studio text ownership policy `slice_studio_text_ownership.v1`.
- 2026-06-12: added M29/local foreground over-broad bbox fallback before Pencil font sizing.
- 2026-06-12: added regression tests for over-broad M29 boxes and generated marker labels.
- 2026-06-12: re-exported `project_mqar9qpo_93b911d9`; dense PC page changed from 208 visible text layers to 116 visible text layers plus 103 raster-preserved text decisions.
- 2026-06-12: inspected regenerated `design.pen` with Pencil MCP; large OCR text pollution was removed from the dense PC page.
- 2026-06-12: moved plan 185 to completed and bug 024 to resolved.
- 2026-06-12: analyzed dense PC UI failure against current Slice Studio code and historical clean-editable / visual-fidelity / visual-ocr contracts.
- 2026-06-12: created active plan 185 for a scoped text ownership arbiter.
- 2026-06-12: confirmed the current code and completed plans identify `apps/slice-studio` as the working product surface.
- 2026-06-12: confirmed existing uncommitted changes in `apps/slice-studio/server/ai-slice-boxes/provider.ts`, `apps/slice-studio/tests/ai-slice-boxes.test.ts`, and `docs/reference/slice-studio-ai-slice-prompt-strategies.md`; these are treated as pre-existing work.
- 2026-06-12: added direction contract and progress ledger.
- 2026-06-12: updated root README, AGENTS, docs index, roadmap, product docs, architecture docs, engineering docs, runbooks, env vars, bug/reference entries, code map, and legacy inventory to route default product work to Slice Studio.
- 2026-06-12: moved plan 184 to completed.

## Next
- Use the current local Slice Studio server for the next real project.
- If dense PC OCR recognition quality itself becomes the bottleneck, open a separate plan for per-M29 crop OCR padding/upscale/grayscale experiments.

## Blocked or deferred
- Per-M29 crop OCR padding/upscale/grayscale is deferred; current mainline does not OCR per M29 crop, so that is a separate experimental path.
- Source images that already contain blue detection boxes/labels still preserve those pixels as raster; this fix prevents double-emitting them as visible OCR text layers.

## Validation log
- 2026-06-12: `pnpm --dir apps/slice-studio exec vitest run tests/pencil-exporter.test.ts` passed: 18 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed: typecheck passed, Vitest 8 files / 54 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed: Next.js production build completed successfully.
- 2026-06-12: `POST /api/projects/project_mqar9qpo_93b911d9/export-project` passed with `assetCount=36`, `pageCount=2`.
- 2026-06-12: regenerated manifest page 1 reported `sourceLineCount=219`, `textLayerCount=116`, `rasterPreservedTextCount=103`, `skippedTextCount=0`.
- 2026-06-12: regenerated manifest page 2 reported `sourceLineCount=84`, `textLayerCount=84`, `rasterPreservedTextCount=0`.
- 2026-06-12: Pencil MCP screenshot of regenerated `page_0001__frame` inspected; dense OCR text pollution was removed.
- 2026-06-12: structured analysis completed; current main contradiction is missing text/raster ownership arbitration, not OCR provider availability.
- 2026-06-12: `git diff --check` passed.
- 2026-06-12: targeted stale-mainline grep passed for current docs; remaining matches are negations, historical/reference runbooks, archived plans, or old completed-plan evidence.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed: typecheck passed, Vitest 8 files / 52 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed: Next.js production build completed successfully.
- 2026-06-12: scoped documentation commit created; unrelated AI prompt code/test changes remain unstaged.

## Failure attempt ledger
- None recorded.

## User input needed
- None recorded.

## Last checkpoint
- 2026-06-12 19:34 CST: plan 185 implemented, validated, and documented.
