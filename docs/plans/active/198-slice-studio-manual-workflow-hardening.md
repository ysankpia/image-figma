# 198 Slice Studio Manual Workflow Hardening

## Summary

Current priority is to make Slice Studio usable even when upstream AI/VLM quality is inconsistent. The mainline remains:

```text
upload images -> manually or locally assist boxes -> save SliceRecord -> export assets.zip / project.zip
```

This plan deliberately does not include frontend visual redesign, admin, billing, payment, quota, or management surfaces.

## Scope

### Stage 1: Local YOLO provider hardening

- Keep `SLICE_STUDIO_AI_SLICE_PROVIDER=yolo_local` as a formal experimental provider.
- Keep YOLO model path, class whitelist, confidence, and image size configurable through env vars.
- Default YOLO candidate classes:

```text
Image,BackgroundImage,Map,Icon,Modal,Drawer
```

- Do not include `Card` by default because it is a container class and captures text/buttons/images together.
- Preserve candidate provenance through `reason: yolo:<ClassName>`.

### Stage 2: Manual box workflow

- Copy/paste selected boxes.
- Delete multiple selected boxes.
- Arrow-key nudge selected boxes.
- Shift+arrow-key larger nudge.
- Select multiple boxes through additive selection.
- Keep bbox numeric edits stable and clamped.
- Scroll the asset list to the active slice when selection changes.
- Add conservative snapping during drag/transform to image bounds and nearby slice edges.

### Stage 3: Save/recovery confidence

- Make save state and failure state clearer.
- Add retry for failed saves without losing current in-memory boxes.
- Keep destructive page replacement/deletion warnings clear.
- Add a project backup/export source-data action only if it can use existing export/download contracts without schema changes.

### Stage 4: AI result reveal pacing

- Keep provider execution honest: do not claim the model is still reasoning after the response has returned.
- After a successful AI boxes response, show a short "preparing candidate boxes" stage before writing boxes to the canvas.
- Default reveal pacing is 10-15 seconds per page; if the provider is slower than that, do not add extra delay before the response exists.
- Batch mode may fetch pages concurrently, but candidate boxes are revealed page-by-page so the user can see progress instead of an instant full-project jump.

## Non-Goals

- No UI redesign.
- No admin/payment/billing/entitlement revival.
- No fake random processing delay that says AI is still running after the provider is done.
- No hardcoded sample/page/image/coordinate behavior.
- No database schema change unless separately approved.

## Validation

- `pnpm exec vitest run tests/ai-slice-boxes.test.ts`
- `pnpm run check`
- `pnpm run build`
- `git diff --check`
- Browser/manual smoke on a real project:
  - upload or open existing project;
  - draw/select/copy/paste/delete/nudge boxes;
  - save, refresh, confirm boxes remain;
  - run YOLO current-page assist;
  - export assets/project.

## Implementation Notes

- Stage 1 is implemented as a configurable local YOLO provider behind `SLICE_STUDIO_AI_SLICE_PROVIDER=yolo_local`.
- Stage 1 production hardening also supports `SLICE_STUDIO_AI_SLICE_YOLO_PYTHON`, so deployment can run Ultralytics from an isolated virtualenv instead of relying on system Python packages.
- YOLO candidate filtering is intentionally broader than VLM filtering: it keeps overlapping YOLO candidates instead of suppressing existing-slice or duplicate-IoU matches, while still rejecting invalid, tiny, or whole-page boxes.
- Stage 2 manual workflow now covers copy/paste, multi-select deletion, arrow-key nudge, Shift+arrow larger nudge, conservative drag/resize snapping, list-to-canvas centering, and stable bbox draft inputs.
- Stage 3 keeps save/recovery work inside the existing contracts: save failures keep in-memory edits visible, failed saves expose a retry button, unload is guarded while saving or failed, destructive page replace/delete confirmation remains explicit, and the existing full `project.zip` is treated as the full project package.
- Stage 4 implements non-misleading reveal pacing: once AI results are available, the UI says it is preparing candidate boxes and waits a 10-15 second per-page reveal window before merging them into normal slices. The progress panel does not claim the provider is still computing during that window.

## Stop Conditions

- Manual operations lose existing slices.
- Save retry can overwrite newer in-memory edits with stale state.
- Snapping makes dragging feel unstable.
- YOLO classes require page-specific or coordinate-specific hacks.
