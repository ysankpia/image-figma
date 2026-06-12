# Progress

This file is the live execution ledger for Image-to-Figma Design. It does not replace `docs/roadmap.md`, active plans, bug records, or validation docs.

## Current objective
Resume Slice Studio multi-user production launch work after completing repository structure cleanup.

## Active plan
- Current plan: `docs/plans/active/189-slice-studio-multi-user-production-launch.md`
- Most recently completed:
  - `docs/plans/completed/191-repository-legacy-code-physical-archive.md`
  - `docs/plans/completed/192-promote-slice-studio-to-repository-root.md`

## Current phase
Slice Studio multi-user production launch planning

## Now
- Repository root is now the Slice Studio product app: `app/`, `components/`, `server/`, `shared/`, `scripts/`, and `tests/`.
- Legacy/reference source code lives under `archive/legacy-code/`; archived runtime artifacts remain ignored and archived packages are not part of the active workspace.
- Local Slice Studio data now lives under root `storage/`; current observed project directory count is `17`.
- Root `.env.local` carries Slice Studio local keys; the previous root env was backed up to an ignored `.env.local.legacy-backup-*` file.
- Plan 189 remains the formal multi-user launch plan for auth/session, ownership, production database/storage, entitlement, payment, and deployment.

## Done
- 2026-06-13: completed plan 192 and moved it to `docs/plans/completed/192-promote-slice-studio-to-repository-root.md`.
- 2026-06-13: completed plan 191 and moved it to `docs/plans/completed/191-repository-legacy-code-physical-archive.md`.
- 2026-06-13: physically archived legacy/reference code under `archive/legacy-code/`, added archive recovery rules, and removed the empty root `tools/` directory.
- 2026-06-13: promoted Slice Studio from `apps/slice-studio/` to the repository root; root scripts now run Slice Studio directly.
- 2026-06-13: moved local Slice Studio runtime data to root `storage/`; browser/API validation confirmed `17` projects still list.
- 2026-06-13: completed plan 190 and moved it to `docs/plans/completed/190-slice-studio-prelaunch-codebase-hardening.md`.
- 2026-06-13: backed up Slice Studio local storage to `backups/slice-studio-storage-20260613-023319` with `projects=17`, `pages=47`, `slices=643`, size `223M`.
- 2026-06-13: added root Slice Studio scripts, marker READMEs for legacy/reference directories, backup/release/local smoke runbooks, and OpenRouter/OpenAI-compatible chat-completions AI provider support.
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
- Continue plan 189 with auth/session and project ownership.
- Confirm the first production auth contract: Better Auth as the session/user identity boundary, Chinese default language with browser-language auto selection, and Google login only when provider credentials are configured.
- Keep archived legacy code under `archive/legacy-code/` unless a new active plan revives a specific component.
- Run a real OpenRouter provider smoke after the user provides a key and model.

## Blocked or deferred
- Figma shows persistent page processing states, asset lock state, and redo behavior. These are not currently backed by persisted Slice Studio contracts and must be treated as missing interfaces unless implemented later.
- Figma-style asset semantic categories beyond `cutMode` are not currently backed by `SliceRecord`; filtering remains limited to existing crop-mode data.
- Crop super-resolution / UpscalerJS is deferred; current evidence does not justify adding it to the mainline dependency path.
- Source images that already contain blue detection boxes/labels still preserve those pixels as raster; this fix prevents double-emitting them as visible OCR text layers.

## Validation log
- 2026-06-13: plan 191/192 validation passed: `pnpm install` completed; `pnpm run check` passed with 8 test files / 60 tests; `pnpm run build` completed successfully; `pnpm run smoke` created and deleted temporary project `project_mqbju82i_bf09eab6` and exported both `assets.zip` and `project.zip`.
- 2026-06-13: plan 191/192 completion audit passed after repository-root promotion: `pnpm run check` passed with 8 test files / 60 tests; `pnpm run build` completed successfully; `pnpm run smoke` created temporary project `project_mqbku312_d343ee48` and exported `project.zip`; targeted current-doc grep found no stale `apps/slice-studio` mainline commands or active-path references.
- 2026-06-13: plan 191/192 browser smoke passed on `http://127.0.0.1:3010/projects`: API returned `17` projects, UI showed `共 17 个项目。`, source-image preview requests returned 200, and console had no errors.
- 2026-06-13: plan 191/192 browser smoke passed on `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`: source image loaded at `1672x941`, 7 asset previews loaded, Konva canvas rendered at `649x769`, network requests returned 200, and console had no errors.
- 2026-06-13: plan 191/192 artifact discipline check passed: `git diff --check` produced no output; `git ls-files` runtime-artifact grep only matched `storage/.gitkeep` plus archived source paths whose names contain `storage`.
- 2026-06-13: plan 190 completion validation passed: `pnpm --dir apps/slice-studio run check` passed with 8 test files / 60 tests; `pnpm --dir apps/slice-studio run build` passed; `pnpm -r run check` passed across Slice Studio, packages, services, and figma-plugin.
- 2026-06-13: plan 190 API smoke passed with `pnpm --dir apps/slice-studio run smoke`: created temporary project `project_mqba2sqe_67812ca4`, uploaded pages, saved slices, exported `assets.zip`, exported `project.zip/design.pen`, and deleted the temporary project.
- 2026-06-13: plan 190 browser smoke passed on `http://127.0.0.1:3010/projects`: existing local projects rendered in the UI, `17` projects were visible, and browser console reported no errors.
- 2026-06-13: plan 190 browser smoke passed on `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`: source image loaded at `1672x941`, 7 asset previews loaded, Konva canvas rendered, there was no document horizontal overflow, and browser console reported no errors.
- 2026-06-13: plan 190 artifact discipline checks passed: `git diff --check` produced no output; tracked runtime artifact grep only matched `apps/slice-studio/storage/.gitkeep` and source files whose path contains `storage`.
- 2026-06-13: prelaunch codebase hardening plan 190 was created, executed, and archived to `docs/plans/completed/190-slice-studio-prelaunch-codebase-hardening.md`; facts used: Slice Studio checks/build pass, root workspace check passes, current local data lives under `apps/slice-studio/storage/`, and legacy/reference code remains present at root-level paths.
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
- 2026-06-13 07:20 CST: plans 191/192 are implemented and validated; Slice Studio runs from the repository root, local `storage/` still contains 17 projects, and the dev app is available at `http://127.0.0.1:3010/projects`.
