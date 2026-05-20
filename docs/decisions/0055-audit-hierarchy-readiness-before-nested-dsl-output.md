# ADR: Audit Hierarchy Readiness Before Nested DSL Output

- 状态：accepted
- 日期：2026-05-20

## Context

Figma hierarchy requires local relative motion: children must belong to a real parent container, then their coordinates can be translated from absolute page space to parent-local space.

M31 already builds reconstruction units, but M31 unit ownership is over primitive evidence. M30 visible DSL nodes are materialized later from M29.0.5 text members, shape candidates, and visual assets. Those two ownership systems are related, but not yet a stable product contract.

## Decision

Add M37 as a read-only hierarchy readiness diagnostic before any nested DSL output.

M37 reads:

```text
M31 reconstruction tree/report
M30 materialized DSL/report
```

It writes:

```text
m37_hierarchy_readiness_report.json
```

The report identifies safe future hierarchy candidates only when M31 units can be mapped to visible M30 children with enough confidence and without duplicate bbox, micro-unit, unsupported visual kind, or relative-coordinate violations.

M37 must keep:

```text
createdVisibleFrameCount = 0
dslChanged = false
```

## Consequences

Benefits:

- Prevents treating a diagnostic reconstruction tree as a finished Figma layer tree.
- Gives M38 an auditable ownership bridge.
- Keeps production DSL and Renderer output unchanged.

Costs:

- Adds another diagnostic artifact and stage timing.
- Geometry-only matches remain diagnostic and cannot be used as product truth until a later explicit nested DSL stage.

Explicit non-goals:

- No nested frame output.
- No per-unit fallback output.
- No Renderer coordinate contract change.
- No production hierarchy change.
