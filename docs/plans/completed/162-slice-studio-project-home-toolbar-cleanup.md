# 162 Slice Studio Project Home Toolbar Cleanup

## Summary

Clean up the `apps/slice-studio` `/projects` home page so global actions and project-list controls are no longer duplicated.

## Scope

- Remove the duplicated top `Design / Assets / All` filter.
- Remove the always-visible top project-name input.
- Move project creation into a page modal opened by `新建项目`.
- Keep a single project search input in the content toolbar.
- Keep list controls in one row: status tabs, search, sort, and grid/list view.
- Make card rename/delete actions appear on hover/focus, while preserving keyboard access.
- Do not change APIs, SQLite schema, export behavior, or the review workbench.

## Validation

- `cd apps/slice-studio && bun run check` passed.
- `cd apps/slice-studio && bun run build` passed.
- Browser check at `http://127.0.0.1:3010/projects` passed:
  - topbar has no duplicated `Design / Assets / All` filter.
  - topbar has no always-visible project-name input.
  - page has one project search input.
  - `新建项目` opens the create-project modal.
  - card actions are hidden by default and remain accessible on focus/hover.
  - console had no errors or warnings.
- `git diff --check` passed.
