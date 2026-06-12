# Progress

This file is the live execution ledger for Image-to-Figma Design. It does not replace `docs/roadmap.md`, active plans, bug records, or validation docs.

## Current objective
Completed dense PC UI text ownership simplification so recognized tiny text can become editable Pencil text.

## Active plan
- Current plan: `docs/plans/completed/186-slice-studio-dense-text-editable-policy.md`

## Current phase
Slice Studio export text ownership simplification completed

## Now
- Dense PC UI tiny text now becomes editable when OCR/M29 already recognizes it.
- The `tiny_dense_ui_text` raster-preserve rule has been removed.
- Marker, slice-overlap, low-confidence, and geometry protections remain in place.
- UpscalerJS / crop super-resolution was not added to the mainline.

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
- Use the updated Slice Studio export path for the next dense PC UI sample.
- If a future sample still fails, inspect the concrete cause first: OCR content, M29 bbox, font sizing, remainder knockout, or Pencil rendering.

## Blocked or deferred
- Crop super-resolution / UpscalerJS is deferred; current evidence does not justify adding it to the mainline dependency path.
- Source images that already contain blue detection boxes/labels still preserve those pixels as raster; this fix prevents double-emitting them as visible OCR text layers.

## Validation log
- 2026-06-12: implemented direct policy change by removing `tiny_dense_ui_text`; high-confidence tiny text is no longer forced to raster solely because the page is dense.
- 2026-06-12: `pnpm --dir apps/slice-studio exec vitest run tests/pencil-exporter.test.ts` passed: 19 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed: typecheck passed, Vitest 8 files / 55 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed: Next.js production build completed successfully.
- 2026-06-12: `git diff --check` passed.
- 2026-06-12: `project_mqavhwm7_875518fe` re-export passed; dense 09 v2 page changed to `sourceLineCount=205`, `textLayerCount=194`, `rasterPreservedTextCount=11`.
- 2026-06-12: Pencil MCP layout check for `project_mqavhwm7_875518fe` regenerated `design.pen` reported no layout problems.
- 2026-06-12: `project_mqar9qpo_93b911d9` re-export passed; page 1 changed to `sourceLineCount=219`, `textLayerCount=183`, `rasterPreservedTextCount=36`; page 2 remained `textLayerCount=84`, `rasterPreservedTextCount=0`.
- 2026-06-12: Pencil MCP layout check for `project_mqar9qpo_93b911d9` regenerated `design.pen` reported no layout problems.
- 2026-06-12: inspected `apps/slice-studio/server/text-reconstruction.ts`; `denseTextPage && located.bbox.height <= 10` returns `raster_preserve` with reason `tiny_dense_ui_text`.
- 2026-06-12: inspected `tmp/m29-debug/summary.json`; regenerated v2 dense PC image has 205 OCR lines, 189 M29 foreground matches, 72 editable text decisions, and 129 `tiny_dense_ui_text` decisions.
- 2026-06-12: temporary `tmp/upscalerjs-probe` install confirmed UpscalerJS can initialize with `@tensorflow/tfjs-node` on this machine; no mainline dependency changed.
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
- 2026-06-12 21:53 CST: plan 186 implemented, validated, documented, and local dev server restarted for user testing.
