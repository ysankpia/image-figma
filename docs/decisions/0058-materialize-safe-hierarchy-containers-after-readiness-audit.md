# ADR: Materialize Safe Hierarchy Containers After Readiness Audit

- 状态：accepted
- 日期：2026-05-21

## Context

M30 currently emits trusted text and image nodes, but the DSL remains mostly flat under the root frame. A flat layer list is visually usable, but it is hard to edit in Figma because coherent rows, cards, and regions cannot be selected and moved as a unit.

M37 already audits whether M31 reconstruction units can be mapped to visible M30 nodes. It intentionally keeps `createdVisibleFrameCount=0` and `dslChanged=false`.

## Decision

Add M38 as a controlled hierarchy materialization stage after M37.

M38 reads:

```text
M30 materialized DSL
M37 hierarchy readiness report
```

It writes:

```text
m38/hierarchy_materialization_report.json
m30/m30_materialized_dsl_flat.json
m30/m30_materialized_dsl.json
```

First version only consumes M37 safe units with at least two `direct_match` M30 children. It creates transparent DSL `group` containers and rewrites moved children from page-absolute coordinates to parent-local coordinates while preserving their original absolute layout in `rawLayout` and meta.

Geometry-only matches remain diagnostic evidence and are not product hierarchy truth in this version.

## Consequences

Benefits:

- Turns the flat M30 output into more usable Figma layer structure.
- Keeps visual pixels stable because moved children preserve absolute page position.
- Reuses M37 as an explicit ownership bridge instead of doing new recognition.

Costs:

- Adds a new DSL mutation stage and report.
- Requires Renderer/schema support for explicit transparent group fill.
- Some safe-looking units may still be skipped when z-order or ownership is not clean enough.

Explicit non-goals:

- No OCR or visual re-detection.
- No image asset cleanup.
- No icon/vector extraction.
- No Auto Layout or Figma Components.
- No nested hierarchy in the first version.
