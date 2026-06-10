# 161 Slice Studio Projects Home UI

## Summary

Improve `apps/slice-studio` `/projects` from a plain CRUD page into a Figma-like project browser.

## Scope

- Keep the existing API, SQLite schema, export contract, and review workbench unchanged.
- Add a stable project-home layout: top toolbar, search, filter tabs, project cards, and list/grid view.
- Use existing project detail API to show first-page preview thumbnails when a project has uploaded pages.
- Preserve current actions: create, open, rename, delete.

## Validation

- `cd apps/slice-studio && bun run check` passed.
- `cd apps/slice-studio && bun run build` passed.
- Browser check at `http://127.0.0.1:3010/projects` passed:
  - topbar, full-width project content, project card grid, and first-page preview render at 1280px.
  - search empty state works.
  - grid/list switching works.
  - with-assets filter works.
  - console had no errors or warnings.
- `git diff --check` passed.
