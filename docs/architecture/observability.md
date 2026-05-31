# Observability

Draft runtime observability is artifact-first. The backend should write enough evidence to locate the owning layer of a failure without reading chat history.

## Task Diagnostics

Draft task directories should contain:

```text
source.png
ocr.json
m29/m29_physical_evidence.v1.json
vision/ui_detector_candidates.v1.json
vision/ui_candidate_review.v1.json
draft/editable_layer_graph.v1.json
draft/draft_runtime.dsl.v1.json
draft/draft_validation_report.md
assets/asset_manifest.json
logs/task_report.md
```

Vision artifacts are optional when vision is disabled or fails as a best-effort source.

## Stage Timing

Stage timing should use Draft stage names:

```text
draft_queued
ocr
m29_physical_evidence
vision_detector
vision_review
draft_assemble
draft_assets
draft_validate
draft_export
draft_completed
draft_failed
```

## Debugging Order

For visible output defects, inspect in this order:

1. `draft_validation_report.md`
2. `editable_layer_graph.v1.json`
3. `asset_manifest.json`
4. `draft_runtime.dsl.v1.json`
5. renderer/plugin warnings
6. M29 and vision source artifacts

Do not patch renderer or plugin before checking whether Draft assembly/export already emitted a bad contract.

## Report Boundaries

Reports must not include secrets, API keys, bearer tokens, provider request headers, or full `.env.local` contents.

Codia eval reports may exist under eval-specific output directories. They are diagnostic only and not generation inputs.
