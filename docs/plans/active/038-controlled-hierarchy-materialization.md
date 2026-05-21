# M38 Controlled Hierarchy Materialization

- 状态：active
- 日期：2026-05-21

## Goal

M38 materializes a small, safe subset of M37 hierarchy readiness evidence into nested DSL `group` containers.

First-principles boundary:

```text
M38 changes ownership and relative coordinates.
M38 does not create new visual evidence.
```

The output should let Figma users select and move coherent groups while preserving the exact absolute visual positions of existing M30 nodes.

## Plan

- Add an M38 stage after M37 hierarchy readiness and before task completion.
- Read the flat M30 DSL plus `m37_hierarchy_readiness_report.json`.
- Use only M37 safe unit reports with at least two `direct_match` M30 children.
- Ignore geometry-only matches for product hierarchy in this first version.
- Create transparent DSL `group` containers with `role=m38_container`.
- Move existing materialized M30 children under those groups and convert child coordinates from page-absolute to parent-local coordinates.
- Preserve the original absolute layout in `rawLayout` and child meta.
- Keep `original_reference`, `fallback_region`, audit-only, mixed, future, and non-materialized nodes at root.

## Outputs

M38 writes:

```text
storage/m30_1_uploads/{taskId}/m38/hierarchy_materialization_report.json
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl_flat.json
storage/m30_1_uploads/{taskId}/m30/m30_materialized_dsl.json
```

`m30_materialized_dsl_flat.json` exists only when M38 changes the DSL.

## Report Metrics

The report summary includes:

```text
sourceSafeContainerCount
selectedContainerCount
createdContainerCount
movedChildCount
ignoredGeometryMatchCount
skippedContainerCount
skipReasonCounts
absolutePositionViolationCount
fallbackMovedCount
originalReferenceMovedCount
assetChanged
dslChanged
maxContainers
```

## Non-Goals

- No OCR, M29, M31, or M37 mutation.
- No new bbox detection.
- No image asset creation.
- No icon/vector extraction.
- No Auto Layout.
- No Figma Component/Instance.
- No `1/6` or image-internal overlay recovery.
- No nested container hierarchy in the first version.

## Acceptance

- M38 report exists after normal uploads when M37 exists and M38 is enabled.
- Final DSL can contain `role=m38_container` groups.
- Every moved child preserves its original absolute page bbox.
- `fallback_region` and `original_reference` remain outside M38 groups.
- DSL assets are unchanged.
- Renderer clears explicit transparent group fills so no white blocks appear.

## Verification

```bash
cd backend
uv run pytest tests/test_hierarchy_materialization.py tests/test_m37_hierarchy_readiness.py tests/test_m30_upload_pipeline.py tests/test_config_env.py -q
cd ..
pnpm run check
```

## Follow-up Notes from 2026-05-21

Today's discussion clarified the next boundary after M38:

- More `unit` candidates do not automatically create hierarchy; hierarchy only appears when parent-child relations are validated and materialized.
- The remaining search area, bottom chrome, and similar fixed UI shells should be treated as a separate content-vs-chrome boundary problem, not as a one-off per-element patch.
- `/Volumes/WorkDrive/Models/model_fp16.onnx` can be used later only as a candidate proposer to improve recall. It should not become the truth source for hierarchy.
- The useful pattern from `ui-contract` is the contract split: evidence -> semantic judgment -> canonical AST -> renderable document.
- The next likely phase is M39, which should define a generic boundary between content, chrome, candidate units, and validated groups before any further hierarchy policy changes.
