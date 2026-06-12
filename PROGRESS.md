# Progress

This file is the live execution ledger for Image-to-Figma Design. It does not replace `docs/roadmap.md`, active plans, bug records, or validation docs.

## Current objective
Plan the formal multi-user production launch for Slice Studio, including landing page, login/register, user ownership, production database/storage, AI provider replaceability, entitlement gates, provider-neutral payment/subscription, deployment, backup, and validation.

## Active plan
- Current plan: `docs/plans/active/189-slice-studio-multi-user-production-launch.md`
- Most recently completed: `docs/plans/completed/188-review-workbench-i18n.md`

## Current phase
Slice Studio multi-user production launch planning

## Now
- Current local product is usable as a private Slice Studio workflow, but formal public launch requires a new production product contract.
- Active plan 189 defines the multi-user production path: landing page, auth/session, project ownership, production database, object storage, entitlement/usage gates, provider-neutral payment, replaceable AI provider, deployment, backup/restore, and full user-view validation.
- Payment provider is intentionally not fixed yet because account/legal constraints are unresolved; the plan defines the internal entitlement and webhook safety contract first.
- AI provider selection is treated as a replaceable OpenAI-compatible provider concern; OpenRouter can be evaluated without binding core product logic to it.
- No business code has been changed for production launch yet.

## Done
- 2026-06-12: completed Review Workbench i18n plan 188 and moved it to `docs/plans/completed/188-review-workbench-i18n.md`.
- 2026-06-12: added component-local Chinese/English dictionary, `sliceStudio.reviewLanguage.v1` persistence, and a topbar language switch in `ReviewWorkbenchClient.tsx`.
- 2026-06-12: localized visible Review Workbench labels, status messages, progress text, modal copy, placeholders, and aria labels while leaving project names, file names, asset names, API enum values, and export contracts unchanged.
- 2026-06-12: stabilized command button widths and text overflow in `globals.css` so Chinese/English labels do not reshape the toolbar.
- 2026-06-12: changed Asset Overview grid to fixed five columns per row.
- 2026-06-12: moved Select/Draw/Pan from the top command bar into a Pencil-style floating canvas tool rail on the left side of the stage.
- 2026-06-12: fixed Review Workbench inspector height allocation so Assets keeps a stable reserved region and Details scrolls independently instead of pushing asset rows out of view.
- 2026-06-12: fixed Review Workbench zoom/layout regressions: top command bar remains one visible row at narrow/zoomed widths, canvas tool buttons moved to the left of the command bar, canvas floating page info card removed, duplicate Overview button removed from Assets, and Asset Overview cards no longer stretch when there are few assets.
- 2026-06-12: completed plan 187 and moved it to `docs/plans/completed/187-slice-studio-figma-workbench-implementation.md`.
- 2026-06-12: implemented Figma node `607:207` in `ReviewWorkbenchClient.tsx` as a real workbench: command bar, Pages rail, canvas meta/footer, Assets panel, Details panel, AI progress panel, independent Assets collapse, and full inspector collapse.
- 2026-06-12: added adaptive CSS for the Review Workbench using `clamp()`, component `container-type`, named `@container` rules, `:has()` state styling, fluid grid columns, and container-sized panel density.
- 2026-06-12: preserved existing upload, page list, page reorder, Konva select/draw/pan, manual box create/move/resize, asset rename, bbox editing, crop mode, delete, overview, AI current/all pages, and export controls.
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
- Begin plan 189 implementation by choosing the first production slice: auth/session boundary and route protection, or AI provider replacement if that is prioritized tomorrow.
- Before implementation, update the direction contract and product docs to stop treating auth/billing/cloud sync as local-phase non-goals for the new production phase.
- Keep payment provider selection separate from the internal subscription/entitlement model.
- Keep Review Workbench behavior stable unless auth/app-shell integration requires route changes.

## Blocked or deferred
- Figma shows persistent page processing states, asset lock state, and redo behavior. These are not currently backed by persisted Slice Studio contracts and must be treated as missing interfaces unless implemented later.
- Figma-style asset semantic categories beyond `cutMode` are not currently backed by `SliceRecord`; filtering remains limited to existing crop-mode data.
- Crop super-resolution / UpscalerJS is deferred; current evidence does not justify adding it to the mainline dependency path.
- Source images that already contain blue detection boxes/labels still preserve those pixels as raster; this fix prevents double-emitting them as visible OCR text layers.

## Validation log
- 2026-06-13: concrete-analysis production launch planning completed from current docs and code facts: current API is open, project state is SQLite/filesystem-backed, no user ownership/session/payment entitlement exists, and current AI provider config is already OpenAI-compatible enough to support provider replacement planning.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed after Review Workbench i18n: TypeScript passed, Vitest 8 files / 55 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed after Review Workbench i18n: Next.js production build completed successfully.
- 2026-06-12: `git diff --check` passed after Review Workbench i18n.
- 2026-06-12: browser smoke passed on `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`: default/fresh state rendered Chinese (`html lang=zh-CN`), Upload/Page/Asset/tool labels were Chinese, and topbar `scrollWidth == clientWidth` at 1280x720.
- 2026-06-12: browser smoke passed after switching to English: visible labels switched to English, `html lang=en`, canvas tool rail labels became `Select tool` / `Draw tool` / `Pan tool`, and topbar still had no hidden overflow at 1280x720.
- 2026-06-12: Asset Overview browser smoke passed after i18n: 7 cards rendered with 5 cards in the first row and five equal grid columns.
- 2026-06-12: Asset Overview browser smoke passed at 1280x720 after five-column change: first row rendered 5 cards, each about 231x212, with `grid-template-columns` resolving to five equal columns.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed after five-column overview change: TypeScript passed, Vitest 8 files / 55 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed after five-column overview change: Next.js production build completed successfully.
- 2026-06-12: `git diff --check` passed after five-column overview change.
- 2026-06-12: canvas tool rail browser smoke passed at 1280x720: top command bar no longer contained Select/Draw/Pan, `.canvasToolRail` rendered inside the stage at 46x128, and Select/Draw/Pan buttons exposed proper aria labels and active state.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed after canvas tool rail move: TypeScript passed, Vitest 8 files / 55 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed after canvas tool rail move: Next.js production build completed successfully.
- 2026-06-12: `git diff --check` passed after canvas tool rail move.
- 2026-06-12: inspector split browser smoke at 1280x720 passed: Assets panel height 446px, asset list height 295px, exactly 5 asset rows visible in the asset list, asset list `scrollHeight > clientHeight`, Details height 224px, and Details scrolls independently.
- 2026-06-12: selected-asset browser smoke passed: after clicking an asset, asset list still showed 5 rows, Details expanded to `scrollHeight=864` while keeping the same panel height, and the asset list remained independently scrollable.
- 2026-06-12: inspector split browser smoke at 2400x1350 passed: Assets panel height 480px, asset list height 324px, Details height 820px, and both asset list and details used their own scroll behavior as needed.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed after inspector split fix: TypeScript passed, Vitest 8 files / 55 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed after inspector split fix: Next.js production build completed successfully.
- 2026-06-12: `git diff --check` passed after inspector split fix.
- 2026-06-12: post-fix browser smoke at 1280x720 passed: topbar action `scrollWidth == clientWidth`, no hidden topbar controls, no document horizontal overflow, `stageMetaBar` absent, and only one Overview button remained.
- 2026-06-12: post-fix browser smoke at 1067x600, approximating 120% zoom pressure, passed: all topbar controls remained visible in the command row, no hidden topbar controls, no document horizontal overflow, and only one Overview button remained.
- 2026-06-12: Asset Overview browser smoke passed after fix: 7 asset cards rendered at stable 220x228 card boxes instead of stretching across the sparse grid.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed after zoom/layout fixes: TypeScript passed, Vitest 8 files / 55 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed after zoom/layout fixes: Next.js production build completed successfully.
- 2026-06-12: `git diff --check` passed after zoom/layout fixes.
- 2026-06-12: `pnpm --dir apps/slice-studio run check` passed after plan 187 implementation: TypeScript passed, Vitest 8 files / 55 tests passed.
- 2026-06-12: `pnpm --dir apps/slice-studio run build` passed after plan 187 implementation: Next.js production build completed successfully.
- 2026-06-12: `git diff --check` passed after plan 187 implementation.
- 2026-06-12: browser smoke passed on `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`; at 1280x720 there was no document horizontal overflow, topbar wrapped to two rows, and Pages/Stage/Inspector remained visible.
- 2026-06-12: browser smoke passed on the same page at 1672x941; topbar returned to one row, Pages/Stage/Inspector expanded proportionally, required controls were present, visible Review Workbench text had no Chinese copy, and browser console logs were empty.
- 2026-06-12: Figma MCP `get_design_context` and `get_screenshot` succeeded for file `rUcERiwtUnlb6ONy6xvrE5`, node `607:207`; screenshot size is 1672x941.
- 2026-06-12: concrete-analysis judgment: main contradiction is mapping a high-fidelity Figma workbench to existing live handlers/contracts without turning unsupported controls into fake functionality.
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
- 2026-06-12 23:58 CST: Review Workbench i18n is implemented and validated; local page remains usable at `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`.
