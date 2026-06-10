# 160 Slice Studio Canvas-First UI

## Summary

Optimize `apps/slice-studio` Review from a three-column admin layout into a canvas-first manual slicing workbench.

## Scope

- Move upload/export/save/zoom into one global topbar.
- Replace the wide left sidebar with a narrow page rail.
- Keep the black canvas and floating tool palette as the primary workspace.
- Turn the right panel into a collapsible asset inspector.
- Do not change APIs, SQLite, export contract, slicing behavior, or `Figma-design`.

## Validation

- `cd apps/slice-studio && bun run check` passed.
- `cd apps/slice-studio && bun run build` passed.
- `cd apps/slice-studio && bun run smoke` passed.
- Browser check at `/projects/{projectId}/review` passed:
  - 1280px viewport canvas width increased to 892px with inspector expanded.
  - Collapsed inspector increased canvas and Konva width to 1148px.
  - Page rail switching, active asset inspector, and tool switching work.
  - Console had no errors or warnings.
- `git diff --check` passed.
