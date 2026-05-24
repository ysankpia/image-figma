# M40 Nested Multi-Level Hierarchy Materialization

- 状态：deferred
- 日期：2026-05-22

## Deferral Note

本计划暂缓。ADR 0064 已将当前下一阶段改为：

```text
M39.1.1 Unit Candidate Quality Gate
-> M39.2 Unit Promotion
-> M40 Layout Semantics
-> M41 Component / Instance Extraction
```

原因：M39.1 报告已经显示当前 candidate unit 仍包含小 icon、小图片碎片、重复 bbox、micro unit 和模型孤证。若现在直接做嵌套层级，会把错误候选固化成错误结构。

本文件保留为 M40 历史草案，后续 M40 应在 M39.2 promoted units 稳定后重写为 layout semantics / nested hierarchy 的最终计划。

## Goal

M40 supports nesting multiple levels of transparent `group` containers (e.g. text/icon inside button inside card inside content body) to accurately model real UI nesting.

First-principles boundary:
```text
M40 structures container nodes hierarchically and applies recursive local coordinate translations.
M40 does not create new visual nodes or alter original absolute positions.
```

The output must yield clean nested Figma groups with zero absolute position drift, while keeping fallback layers flat at the root frame.

## Scope

包含：
- Support for nested container hierarchies up to depth of 4 and total container limit of 24.
- Parent-child container relationship builder based on bounding box containment:
  - Container B is inside A if $Area(A \cap B) / Area(B) \ge 0.98$.
  - Resolve tree/forest topology.
- Node ownership assignment: each M30 node is assigned to the deepest containing container.
- Recursive coordinate translation:
  - $x_{local} = x_{absolute} - x_{parent\_absolute}$
  - $y_{local} = y_{absolute} - y_{parent\_absolute}$
- Multi-level z-order interleaving checks (only check overlap among siblings at the same hierarchy level).
- Output report `m40_hierarchy_materialization_report.json` and nested final DSL.
- Zero-drift coordinates validation.

不包含：
- Generating new bounding boxes or visual evidence.
- Hiding/masking fallback layers or grouping fallback/original_reference nodes.
- Auto Layout, Figma Component/Instance, or responsive layouts.

## Proposed Changes

### Backend Components

#### [NEW] [nested_hierarchy_materialization.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/nested_hierarchy_materialization.py)
- Read M30 materialized DSL and M37 readiness report.
- Sort safe container candidates by area descending.
- Build container containment tree/forest.
- For each container:
  - Collect owned direct children (both leaf nodes and nested sub-containers).
  - Verify z-order interleaving safety at this layout level.
- Recursively build tree starting from page root.
- Apply local coordinate offset transformations.
- Run drift validation on all output leaf nodes.
- Write report `m40_hierarchy_materialization_report.json` under `storage/m30_1_uploads/{taskId}/m40/`.

#### [MODIFY] [m30_upload_pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/m30_upload_pipeline.py)
- Replace M38 stage with M40 nested hierarchy materialization (or keep M38 as configuration option and default to M40).
- Register `m40_nested_hierarchy_materialization` stage.

### Tests

#### [NEW] [test_nested_hierarchy_materialization.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/backend/tests/test_nested_hierarchy_materialization.py)
- Test tree/forest building from overlapping bboxes.
- Test coordinate translation correctness on deep nested children.
- Test z-order safety checks at parent/child level.
- Test drift-checking assertion.

## Verification Plan

### Automated Tests
- Run focused backend tests:
  ```bash
  cd backend
  uv run pytest tests/test_nested_hierarchy_materialization.py tests/test_m30_upload_pipeline.py -q
  ```
- Run all backend tests to ensure zero regression:
  ```bash
  cd backend
  uv run pytest -q
  ```
