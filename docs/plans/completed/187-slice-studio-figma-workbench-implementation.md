# Plan 187: Slice Studio Figma Workbench Implementation

## Status
Completed on 2026-06-12.

## Objective
Implement Figma node `607:207` from file `rUcERiwtUnlb6ONy6xvrE5` into the real Slice Studio Review Workbench.

## Input normalization
- User-provided inputs: Figma design URL for the workbench page.
- Truth sources: Figma node `607:207`, current Slice Studio code, saved project/page/slice API contracts.
- Evidence/candidate sources: Figma MCP design context and screenshot downloaded to `/tmp/slice-studio-figma-607-207.png`.
- Missing inputs: none for the visual implementation pass.
- Final output: working `apps/slice-studio` Review Workbench page matching the Figma workbench direction while preserving upload, page list, canvas editing, AI slicing, asset editing, export, overview, and confirmation flows.

## Scope
- Update `apps/slice-studio/components/review/ReviewWorkbenchClient.tsx`.
- Update `apps/slice-studio/app/globals.css`.
- Update execution docs and validation evidence.

## Non-goals
- No backend API redesign.
- No database schema change.
- No AI prompt change.
- No export manifest change.
- No Docker or deployment change.
- No mock-only page.

## Implementation checklist
- Translate the Figma top command bar into real controls.
- Translate the wide Pages rail with thumbnails, metadata, reorder, and derived status.
- Keep the Konva canvas and box editing path intact.
- Translate the right inspector into `Assets` and `Details` work areas.
- Add local asset search/sort/filter only where current slice data can support it.
- Add an independent Assets list collapse while keeping the full inspector collapse.
- Expand Details fields with editable name, bbox, cut mode, readonly format/page/size, box color, page actions, and disabled locked indicator.
- Translate AI progress into the Figma-style bottom batch panel.
- English visible UI copy for the implemented workbench.

## Missing API / contract candidates
- Persistent page processing status (`Completed`, `Processing`, `Skipped`, `In Review`) is not stored today. The UI can only derive local status from active page and slice count.
- Asset lock state is not in `SliceRecord` and has no save/export contract. The lock toggle must remain disabled until the API/model exists.
- Asset semantic categories beyond `cutMode` are not in `SliceRecord`. Filtering can only use all/rect/subject/card for now.
- Redo history is not implemented; the Figma `Redo` button must remain disabled until a redo stack exists.

## Validation
- `pnpm --dir apps/slice-studio run check` passed: TypeScript passed, Vitest 8 files / 55 tests passed.
- `pnpm --dir apps/slice-studio run build` passed: Next.js production build completed successfully.
- `git diff --check` passed.
- Browser smoke on `http://127.0.0.1:3010/projects` and a real review page:
  - real page `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review` loaded;
  - 1280x720 layout had no document horizontal overflow, topbar wrapped to two rows, Pages/Stage/Inspector remained visible;
  - 1672x941 layout had no document horizontal overflow, topbar returned to one row, Pages/Stage/Inspector expanded proportionally;
  - browser console reported no errors or warnings during smoke validation;
  - required controls remained present: Upload, Undo, Fit, AI Current Page, AI All Pages, Download assets.zip, Download project.zip, Pages, Assets, Details.
  - visible Review Workbench text had no Chinese copy remaining.

## Progress checkpoints
- PROGRESS.md update required: before implementation, after code implementation, after validation.
- Module validation cadence: typecheck/build after UI implementation.
- E2E/artifact validation target: browser smoke for real Review Workbench page.
