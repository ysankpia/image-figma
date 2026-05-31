# Artifact Policy

Artifacts are part of the Draft pipeline contract. They must be deterministic enough to debug and compare, but they are not all product outputs.

## Runtime Artifacts

Completed Draft tasks must write:

```text
source.png
ocr.json
m29/m29_physical_evidence.v1.json
draft/editable_layer_graph.v1.json
draft/draft_runtime.dsl.v1.json
draft/draft_validation_report.md
assets/asset_manifest.json
assets/*.png
```

Optional artifacts:

```text
vision/ui_detector_candidates.v1.json
vision/ui_candidate_review.v1.json
logs/task_report.md
eval/*
```

## Git Policy

Do not commit runtime artifacts:

```text
backend/storage/
services/backend-go/storage/
services/backend-go/tmp/
logs/
*.log
*.db
*.sqlite
*.sqlite3
dist/
build/
```

Reference fixtures are allowed only when they are intentionally curated under `docs/reference/` or test fixture directories and contain no secrets.

## Report Policy

Reports should be written when they help locate ownership decisions:

```text
draft_validation_report.md
draft_assembly_report.md
vision_detector_report.md
vision_review_report.md
asset_manifest.json
```

Reports must not contain API keys, bearer tokens, full provider request headers, or full local env dumps.

## Asset Policy

Raster assets must be local crop outputs with stable IDs and resolvable URLs.

A completed task must not contain a visible `RasterLayer` whose asset is missing. If an asset cannot be written, the task should fail or the layer should be suppressed with a report reason before completion.

The source PNG may be written for traceability, but it must not be emitted as a visible full-page backing layer.
