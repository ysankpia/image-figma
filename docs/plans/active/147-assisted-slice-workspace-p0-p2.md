# 147 Assisted Slice Workspace P0-P2

Status: active
Created: 2026-06-05 04:44 +0800

## Objective

把 Pencil Assisted Slice Workspace 从“能用”推进到“日常批量使用更稳、更顺、更可验收”。本轮只做 P0、P1、P2；明确禁止 P3、P4 以及任何后续扩展。

当前主线保持不变：

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

核心真相源不变：

```text
manual_slices.v1.json = final delivery truth source
review_state.v1.json = workbench/UI state only
PSD-like / M29 / OCR / foreground audit / model evidence = candidates/debug/eval only
```

## Standards Read

- `AGENTS.md`
- `docs/index.md`
- `docs/engineering/validation.md`
- `docs/reference/pencil-python-backend-api.md`
- `docs/plans/completed/141-pencil-assisted-slice-review-and-export.md`
- `docs/plans/completed/144-assisted-slice-project-workspace.md`
- `docs/plans/completed/145-assisted-slice-workspace-acceptance-hardening.md`
- `docs/plans/completed/146-pencil-assisted-slice-mainline-cleanup-and-handoff.md`

## Scope

Allowed:

- `services/pencil-python-backend` assisted slice routes, HTML Canvas workspace/review page, slice project storage, exporter guardrails, acceptance script, and tests.
- Current docs for API, handoff, validation, and this plan.
- Plain HTML + Canvas + native JavaScript only.

Forbidden:

- P3/P4 and later backlog.
- React/Vue/frontend build-chain rewrite.
- YOLO/model output as final ownership judge.
- Fully automatic ownership arbitration as product delivery truth.
- Codia route restoration, Go Draft revival, `services/pencil-go` restoration, Figma plugin changes.
- Default transparent export.
- Sample name/path/page/text/coordinate/brand-specific rules.

## Affected Layers

- source input: user-uploaded image files.
- intermediate data: `candidates.v1.json`, `review_state.v1.json`, `manual_slices.v1.json`.
- decision point: user actions in Canvas review/workspace.
- output surface: export-preview, `project.zip`, `selected-assets.zip`, workspace/review HTML.
- validation surface: unit/API tests, acceptance script, Chrome DevTools smoke when practical, ZIP contract inspection.

## Priority Contract

### P0: Delivery Stability

The workspace must not lose or corrupt delivery truth during normal daily use.

Acceptance:

- Refreshing review page after saving keeps selected slices and rejected candidates.
- Page switching keeps active page, selected slices, rejected state, and filters consistent.
- Export preview count matches final ZIP selected asset count.
- `project.zip` and `selected-assets.zip` download links are obvious after export and backed by real URLs.
- Rename, clone, and delete preserve metadata correctness.
- `manual_slices.v1.json` remains the only export truth.

### P1: Daily Review Operations

The workspace must make the common batch workflow efficient enough for 10-50 image projects.

Acceptance:

- Candidate hover, active, selected, and rejected states are visually and behaviorally distinct.
- Box-select multiple visible candidates and batch add them to selected slices.
- Batch reject and restore candidates persist through refresh.
- Selected assets panel click focuses the canvas item.
- Search selected assets.
- Batch delete visible selected slices.
- Batch rename display names.
- Edit kind/tags/review state.
- Keyboard nudge selected slice with arrow keys.
- Save/delete/export feedback is explicit.

### P2: Verification And Handoff Polish

The project must be easy to validate and hand off without relying on chat context.

Acceptance:

- API docs mention P0/P1 workspace behavior that affects persisted state or artifact URLs.
- Acceptance script exercises persisted review state and selected asset/export-preview/ZIP consistency.
- Completed plan records exact validation evidence.
- `make check`, representative `make slice-acceptance`, `git diff --check`, and `git status --short --branch` pass before final commit.

## Explicit Non-Goals

- Better automatic candidate quality beyond simple UI-level tiering/visibility.
- Transparent background extraction.
- Full-page editable Figma reconstruction.
- Auto Layout/component reconstruction.
- Model training or model integration.
- New database/index service.
- Formal frontend refactor.

## Stage Plan

1. P0 audit and fixes.
   - Inspect existing review/workspace state flows.
   - Fix any delivery-contract bugs found in refresh, page switch, export preview/export, clone/delete/rename.
   - Add targeted tests for the fixed behavior.
   - Commit with a P0-scoped Conventional Commit message.

2. P1 daily workflow.
   - Improve existing plain Canvas interactions instead of adding a new frontend framework.
   - Add only operations that feed `manual_slices.v1.json` or `review_state.v1.json`.
   - Keep tests focused on contracts; use browser smoke for UI behavior.
   - Commit with a P1-scoped Conventional Commit message.

3. P2 docs and acceptance.
   - Update docs and acceptance report surfaces.
   - Run canonical checks and representative acceptance samples.
   - Move this plan to `docs/plans/completed/`.
   - Commit with a P2-scoped Conventional Commit message.

## Commands

```bash
cd services/pencil-python-backend
make check
make slice-acceptance IMAGE=/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance-147/tencent-comic
uv run python scripts/slice_workspace_acceptance.py \
  --base-url http://127.0.0.1:8100 \
  --input "/Users/luhui/Downloads/PencilBridge_Admin_UI_XcodeDark/01_UI_Pages" \
  --input "/Users/luhui/Downloads/dorm_selection_ui_assets 2" \
  --out /Volumes/WorkDrive/pencil-exports/slice-acceptance-147/batch
git diff --check
git status --short --branch
```

## Stop Conditions

- Any needed change would require P3/P4 scope.
- Any needed change would require restoring a forbidden old product route.
- A dirty tree contains unrelated user-owned changes that cannot be isolated safely.
- Representative acceptance exposes candidate quality issues that require a new product decision rather than P0/P1/P2 workspace hardening.
