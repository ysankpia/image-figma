# M37 M31-to-M30 Hierarchy Readiness And Ownership Bridge

- 状态：active
- 日期：2026-05-20

## Goal

M37 audits whether M31 reconstruction units are ready to become future DSL hierarchy containers. It does not change visible DSL or Figma output.

First-principles boundary:

```text
M31 reconstruction unit ownership
is not yet the same thing as
M30 visible DSL node ownership
```

M37 proves the bridge before M38 nested DSL work.

## Plan

- Add a read-only hierarchy readiness stage after M30 DSL has been materialized and assets have been published.
- Read M31 tree/report and M30 DSL/report from task storage.
- Match M30 visible nodes to M31 units using direct source ids first, then diagnostic-only geometry/text or geometry/type matches.
- Mark safe container candidates only when a unit has enough primitives, enough mapped M30 children, no duplicate bbox, no micro-unit shape, no relative coordinate violations, and a generic supported visual kind.
- Write `storage/m30_1_uploads/{taskId}/m37/m37_hierarchy_readiness_report.json`.

## Report Metrics

The report summary includes:

```text
m30NodeCount
m31UnitCount
mappableM30NodeCount
unmappedM30NodeCount
safeContainerUnitCount
unsafeContainerUnitCount
microUnitCount
duplicateUnitBBoxCount
unitChildCoverage
relativeCoordinateViolationCount
fallbackConflictRiskCount
createdVisibleFrameCount = 0
dslChanged = false
```

## Non-Goals

- No nested DSL generation.
- No visible frame creation.
- No node movement.
- No per-unit fallback output.
- No Renderer coordinate semantic change.
- No product use of geometry-only matches.

## Acceptance

- M37 report exists after normal M31+M30 upload runs.
- Report can explain safe and unsafe hierarchy candidates.
- `/api/tasks/{taskId}/dsl` is unchanged by M37.
- `createdVisibleFrameCount` remains `0`.
- `dslChanged` remains `false`.

## Verification

```bash
cd backend
uv run pytest tests/test_m37_hierarchy_readiness.py tests/test_m30_upload_pipeline.py -q
```
