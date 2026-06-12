# Plan 188: Slice Studio Review Workbench I18n

## Status
Completed on 2026-06-12.

## Objective
Add lightweight Chinese/English UI internationalization to the real Slice Studio Review Workbench, with Chinese as the default language and stable command button sizing across languages.

## Input normalization
- User-provided inputs: request to internationalize the current Review Workbench, default to Chinese, provide English, and handle long button text / uneven button widths.
- Truth sources: current `ReviewWorkbenchClient.tsx`, current `globals.css`, existing Slice Studio handlers and contracts.
- Evidence/candidate sources: browser state at `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`.
- Missing inputs: no missing backend/API input; this is a frontend behavior/style change.
- Final output: working Review Workbench with language toggle, Chinese default labels, English alternative labels, and stable command button sizing.

## Scope
- `apps/slice-studio/components/review/ReviewWorkbenchClient.tsx`
- `apps/slice-studio/app/globals.css`
- `PROGRESS.md`

## Non-goals
- No backend API change.
- No database schema change.
- No route-level i18n framework.
- No export manifest or AI prompt change.
- No translation of persisted user/project/asset names.

## Implementation completed
- Added component-local `zh` / `en` dictionary and `LanguageCode` state.
- Defaulted the Review Workbench to Chinese.
- Persisted language choice with `sliceStudio.reviewLanguage.v1`.
- Added a topbar language switch for Chinese and English.
- Replaced visible Review Workbench labels, titles, placeholders, statuses, modal text, progress text, and aria labels with dictionary values.
- Kept internal enum values, API payloads, file names, asset names, database fields, and route names unchanged.
- Stabilized command button widths and text overflow for Chinese and English labels.

## Validation
- `pnpm --dir apps/slice-studio run check` passed: TypeScript passed, Vitest 8 files / 55 tests passed.
- `pnpm --dir apps/slice-studio run build` passed: Next.js production build completed successfully.
- `git diff --check` passed.
- Browser smoke on `http://127.0.0.1:3010/projects/project_mqavhwm7_875518fe/review`:
  - Chinese rendered as the default language after clearing language state.
  - `html lang` was `zh-CN` for Chinese and `en` after switching to English.
  - Language toggle switched visible labels to English.
  - Top command bar had no hidden overflow at 1280x720 in both Chinese and English.
  - Canvas tool rail labels switched between Chinese and English.
  - Asset Overview still rendered five cards per row.
