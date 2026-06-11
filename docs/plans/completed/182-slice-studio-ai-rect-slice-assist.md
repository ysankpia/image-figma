# 182 Slice Studio AI Rect Slice Assist

## Summary

Add AI batch drawing to Slice Studio. AI computes rectangular bboxes from compressed image tiles; the review workbench turns those bboxes into normal `SliceRecord` entries and saves through the existing `/api/projects/:projectId/slices` path.

The feature must not create a second persistent proposal system. Manual slices remain the only export truth source.

## Scope

- Add Slice Studio-specific AI slice environment variables.
- Add `POST /api/projects/:projectId/pages/:pageId/ai-boxes`.
- Split each source image into six overlapping compressed tiles before sending it to the provider.
- Add "AI 当前页" and "AI 全部页" buttons to the review workbench.
- Add page navigation inside the asset gallery modal.

## Non-Goals

- Do not feed M29 or OCR evidence into the AI prompt.
- Do not auto-pick `subject` or `card`; AI-created slices are `rect`.
- Do not change Pencil/Figma export contracts.
- Do not persist AI proposals separately from normal slices.
- Do not hardcode sample names, visible text, coordinates, or brand-specific rules.

## Acceptance

- AI boxes are appended to existing slices with IoU de-dupe against current manual slices.
- Batch mode saves page-by-page so completed pages survive later failures.
- Refreshing the page after AI drawing keeps the new boxes.
- Re-running AI on the same page does not duplicate high-overlap boxes.
- Exported `project.zip` remains driven only by saved slices.

## Validation

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
git status --short --branch
```

If provider credentials are available, run a real project smoke through the local API and inspect the returned boxes before using the UI flow.

Completed validation:

- `pnpm --dir apps/slice-studio run check` passed with 8 test files and 48 tests.
- `pnpm --dir apps/slice-studio run build` passed.
- `git diff --check` passed.
- Real provider smoke used a local 7-image `525测试` sample set.
- Created a fresh 7-page Slice Studio project, AI completed 7/7 pages, failed 0 pages, added 109 normal slices, skipped 8 invalid/duplicate boxes.
- Refresh API readback reported 7 pages and 109 saved slices.
- `POST /api/projects/:projectId/export-project` produced `project.zip` with 7 pages and 109 slice assets.
- Export manifest/package inspection found no absolute `/Users/`, `/Volumes/`, `../`, `source.png`, `raw`, or `debug` visible references.
