# 146 Pencil Assisted Slice Mainline Cleanup And Handoff

Status: completed

## Summary

Align repository documentation with the current delivery reality on
`feat/pencil-assisted-slice-review`.

The current usable product mainline is:

```text
images
-> services/pencil-python-backend
-> candidates.v1.json
-> plain HTML + Canvas assisted slice workspace
-> user-confirmed manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

`manual_slices.v1.json` is the delivery truth source. Automatic evidence from
PSD-like, M29, OCR, foreground audit, or model experiments is candidate/debug
input only.

## Scope

- Remove stale execution plans from `docs/plans/active/`.
- Archive superseded automatic Draft, PSD-like, YOLO, Pencil-Go, and ownership
  repair plans under `docs/plans/archive/superseded/`.
- Move completed bounded hybrid Pencil boundary work to `docs/plans/completed/`.
- Update navigation docs so new work starts from the assisted slice workspace
  instead of the old Go Draft or automatic ownership routes.
- Update the Pencil handoff/runbook surface with the current workspace,
  acceptance script, and package contracts.
- Record document classification and archive decisions in repo docs, because no
  usable `bd` database exists in this workspace.

## Non-Goals

- No core code changes.
- No Figma plugin changes.
- No `services/pencil-go` revival.
- No YOLO mandatory semantic chain.
- No return to Codia, Go Draft, or fully automatic ownership as the current
  product judge.
- No deletion of historical plan files.

## Document Classification

Current:

```text
services/pencil-python-backend/app/routes/slice_projects.py
services/pencil-python-backend/app/routes/slice_project_pages.py
services/pencil-python-backend/app/slice_projects.py
services/pencil-python-backend/scripts/slice_workspace_acceptance.py
services/pencil-python-backend/README.md
docs/reference/pencil-python-backend-api.md
docs/plans/completed/141-pencil-assisted-slice-review-and-export.md
docs/plans/completed/142-pencil-assisted-slice-review-workbench.md
docs/plans/completed/143-assisted-slice-workbench-p0-hardening.md
docs/plans/completed/144-assisted-slice-project-workspace.md
docs/plans/completed/145-assisted-slice-workspace-acceptance-hardening.md
```

Stale entry/navigation docs to rewrite:

```text
AGENTS.md
README.md
docs/index.md
docs/engineering/current-code-map.md
docs/engineering/current-mainline-code-map.md
docs/runbooks/pencil-python-backend-handoff.md
```

Historical or superseded after this plan, from old active paths to archive paths:

```text
093-editable-draft-layer-pipeline-rebuild.md -> docs/plans/archive/superseded/
094-ui-layout-ir-html-preview-gateway.md -> docs/plans/archive/superseded/
095-unified-vision-section-based-layout-style.md -> docs/plans/archive/superseded/
096-backend-python-omniparser-vlm-draft-mvp.md -> docs/plans/archive/superseded/
097-psd-like-layer-decomposition-experiment.md -> docs/plans/archive/superseded/
098-psd-like-v2-vector-surface-experiment.md -> docs/plans/archive/superseded/
099-psd-like-v3-deki-yolo-v1-enhancement.md -> docs/plans/archive/superseded/
102-fix-text-to-image-classification-by-first-principles.md -> docs/plans/archive/superseded/
104-clean-python-psdlike-draft-service-mechanical-migration.md -> docs/plans/archive/superseded/
113-psdlike-vertical-media-stack-raster-splitting.md -> docs/plans/archive/superseded/
114-m29-pencil-editable-text-production-export.md -> docs/plans/archive/superseded/
115-pencil-go-backend-formalization.md -> docs/plans/archive/superseded/
```

Completed but misplaced:

```text
docs/plans/active/118-pencil-hybrid-boundary-source.md
```

## Archive Decisions

- Plans `093`, `094`, `095`, `096`, `097`, `098`, `099`, `102`, `104`, `113`,
  `114`, and `115` are moved to `docs/plans/archive/superseded/`.
- Plan `118` is moved to `docs/plans/completed/` because bounded
  `boundarySource=hybrid` is already present in the Pencil Python Backend
  contract and README.
- `docs/plans/active/README.md` remains as the active placeholder after this
  plan completes.

## Required Validation

```bash
cd services/pencil-python-backend
make check
git diff --check
git status --short --branch
```

## Completion Criteria

- `docs/plans/active/` contains only genuinely active work while this plan is
  running, and only `README.md` after completion.
- Repository entry docs point to assisted slice workspace as the current usable
  delivery path.
- Old Go Draft/Codia/PSD-like/YOLO/Pencil-Go plans remain available as archived
  historical context, not active execution guidance.
- Pencil handoff tells an operator how to run, accept, and hand off the current
  workspace path.
- Validation commands pass.

## Implementation Summary

Aligned the repository reading path with the current Pencil assisted slice
delivery route:

- Updated `AGENTS.md`, `README.md`, `docs/index.md`, `docs/roadmap.md`,
  `docs/product/vision.md`, `docs/engineering/current-code-map.md`,
  `docs/engineering/validation.md`, `docs/reference/env-vars.md`, and the
  Pencil backend README/runbooks to make the assisted slice workspace the
  current product route.
- Downgraded Go Draft, Codia, PSD-like automatic ownership, YOLO/model
  ownership, and `services/pencil-go` material to historical/deferred context
  unless explicitly resumed by a new active plan.
- Moved stale active plans `093`, `094`, `095`, `096`, `097`, `098`, `099`,
  `102`, `104`, `113`, `114`, and `115` to
  `docs/plans/archive/superseded/`.
- Moved completed `118-pencil-hybrid-boundary-source.md` to
  `docs/plans/completed/`.
- Updated archive/completed indexes and fixed stale active-plan references.

## Completion Evidence

Stale-mainline scan:

```text
searched repository docs for stale active-plan links and old Draft-as-current wording
no matches
```

Backend validation:

```text
cd services/pencil-python-backend
make check
34 passed, 2 warnings
```
