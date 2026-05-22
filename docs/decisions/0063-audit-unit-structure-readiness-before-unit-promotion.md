# ADR: Audit Unit Structure Readiness Before Unit Promotion

- 状态：accepted
- 日期：2026-05-22

## Context

M30 now materializes editable text, shapes, product images, and composite media. M37 bridges M31 units to M30 visible nodes, and M38 can safely move a small direct-match subset into transparent groups. M39 protects content/chrome boundaries.

The remaining gap is not another single visual element. The pipeline needs a stable explanation of why most M31/M37 units are still micro, unsafe, duplicated, unsupported, lineage-poor, or model-only.

## Decision

Introduce M39.1 as a report-only unit structure readiness audit after M38. It reads existing evidence and writes `unit_structure_readiness_report.json` with normalized candidates, blocker reasons, and future promotion hints.

M39.1 may use `/Volumes/WorkDrive/Models/model_fp16.onnx` only as an optional box proposer. Model boxes are diagnostic candidates unless corroborated by M30 geometry, M39 boundary labels, and existing M31/M37 evidence. They cannot directly become DSL structure.

## Consequences

- The next implementation step can be based on measurable blockers instead of single-element patches.
- M40 nested hierarchy is deferred until unit candidates are stronger.
- UIC/Codia-like ideas remain architectural references: evidence, judgment, construction plan, and adapter output stay separate.
- The final DSL and assets remain unchanged by M39.1.
