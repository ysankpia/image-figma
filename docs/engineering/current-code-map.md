# Current Code Map

This document maps the current `main` branch. It describes where new work should land. It is authoritative for new product code.

## Product Mainline

```text
1..N images
-> services/pencil-python-backend
-> candidates.v1.json
-> HTML Canvas assisted slice workspace
-> manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

The current product truth source is `manual_slices.v1.json`. Automatic evidence
from PSD-like, M29, OCR, foreground audit, or model experiments only creates
candidates/debug data.

## Pencil Asset Handoff Surface

`services/pencil-asset-backend` is the slim 151 product surface for image/icon
asset handoff. It intentionally does less than the assisted slice workspace:
it produces only PNG `image` and `icon` assets, writes a single
`pencil-handoff` `design.pen`, and leaves non-asset UI reconstruction to Pencil
MCP/manual follow-up. The `.pen` includes a source screenshot reference layer so
reviewers can judge selected slices in context; that reference is not a selected
asset and is excluded from `selected-assets.zip`.

Current asset handoff flow:

```text
POST /api/asset-projects
-> save uploaded source images
-> collect YOLO/M29/PSD-like/OCR evidence
-> normalize image/icon candidates
-> serve /api/asset-projects/{projectId}/review
-> user confirms image/icon slices
-> PUT /api/asset-projects/{projectId}/manual-slices
-> POST /api/asset-projects/{projectId}/export-preview
-> POST /api/asset-projects/{projectId}/export
-> GET project.zip and selected-assets.zip
```

Primary files:

```text
services/pencil-asset-backend/app/projects.py
services/pencil-asset-backend/app/evidence.py
services/pencil-asset-backend/app/exporter.py
services/pencil-asset-backend/app/routes/asset_projects.py
services/pencil-asset-backend/app/routes/pages.py
services/pencil-asset-backend/scripts/asset_acceptance.py
services/pencil-asset-backend/tests/test_asset_projects.py
```

Hard asset handoff rules:

```text
manual_slices.v1.json is the final truth source
only image/icon slices are exported
assets are cropped from source.png
design.pen selected slice refs must be ./assets/visible/...
design.pen source reference refs must be ./assets/reference/page_XXXX/source.png
selected-assets.zip must not contain source reference images
no Codia-like tree, Draft graph, TextLayer knockout, SVG, or auto ownership judge
```

## Pencil Assisted Slice Surface

`services/pencil-python-backend` is the current product delivery route. It is
separate from the Draft runtime packages and does not import the renderer/plugin
packages. It uses the already-validated Python Pencil exporter plus a plain HTML
Canvas review workspace.

Current assisted slice flow:

```text
POST /api/pencil/slice-projects
-> save uploaded source images
-> normalize PSD-like/M29/OCR/audit evidence into candidates.v1.json
-> serve /api/pencil/slice-projects/{projectId}/review
-> user confirms or draws slices
-> PUT /api/pencil/slice-projects/{projectId}/manual-slices
-> POST /api/pencil/slice-projects/{projectId}/export-preview
-> POST /api/pencil/slice-projects/{projectId}/export
-> GET project.zip and selected-assets.zip
```

Primary files:

```text
services/pencil-python-backend/app/slice_projects.py
services/pencil-python-backend/app/routes/slice_projects.py
services/pencil-python-backend/app/routes/slice_project_pages.py
services/pencil-python-backend/scripts/slice_workspace_acceptance.py
services/pencil-python-backend/tests/test_api.py
```

Operational files:

```text
services/pencil-python-backend/Makefile
services/pencil-python-backend/README.md
services/pencil-python-backend/deploy/pencil-python-backend.env.example
services/pencil-python-backend/deploy/pencil-python-backend.service
services/pencil-python-backend/scripts/http_smoke.py
services/pencil-python-backend/scripts/server_smoke.py
docs/reference/pencil-python-backend-api.md
docs/runbooks/pencil-python-backend-handoff.md
docs/runbooks/pencil-python-backend-deploy.md
```

For non-mainline directories, read [legacy-code-inventory.md](legacy-code-inventory.md) before editing or deleting code.

## Automatic Pencil Export Surface

The older automatic Pencil package route remains available for explicit
batch/diagnostic use. It is not the current product judge.

The default HTTP/CLI boundary source is `psdlike`; explicit `m29` and `hybrid`
remain available.

```text
1..N PNG
-> PSD-like boundary source by default
-> Python Pencil exporter
-> project ZIP builder
-> clean-editable / visual-fidelity / visual-ocr .pen ZIP
```

Automatic project endpoints:

```text
POST /api/pencil/projects
GET  /api/pencil/projects/{taskId}
GET  /api/pencil/projects/{taskId}/manifest
GET  /api/pencil/projects/{taskId}/download.zip
```

`services/pencil-go` is retained as a superseded experiment and should not be extended as the current product delivery path.

## PSD-like And M29 Dependency Boundary

Some older-looking code is still a current dependency:

```text
services/psdlike-python/
services/backend-go/cmd/m29extract/
services/backend-go/internal/m29/
```

`services/pencil-python-backend/app/psdlike_runner.py` invokes `services/psdlike-python/tools/run_one.py` for `boundarySource=psdlike`. `services/pencil-python-backend` also supports `boundarySource=m29/hybrid`, and the deploy bundle includes `m29extract` plus the Go M29 kernel. These directories are not dead code.

They remain evidence/candidate dependencies. They do not decide final visible assets; `manual_slices.v1.json` does.

## Go Draft / M29 Surface

`services/backend-go` is split:

- `cmd/m29extract` and `internal/m29` are retained current diagnostic/dependency code for Pencil boundary evidence.
- Draft server/compiler/vision/app packages are historical/deferred as a product delivery route on this branch.

New current-product work should not land in the deferred Draft packages unless a new active plan explicitly resumes the Draft runtime.

```text
services/backend-go/
  cmd/
    draftserver/
    draftcompile/
    draftdetect/
    drafteval/
    m29extract/
    m29trace/

  internal/
    app/
      server/
      storage/
      task/

    image/
      crop/
      geometry/
      pngio/
      color/
      mask/

    m29/
      primitive/
      evidence/
      relation/
      visualtree/
      ocr/
      pipeline/

    vision/
      detector/
      provider/
      prompt/
      review/

    draft/
      contract/
      assemble/
      asset/
      group/
      exportdsl/
      validate/
      report/

    eval/
      codia/
      metrics/
```

## Removed Legacy Generation

The old `services/backend-go/internal/codia/*` generation tree has been removed. Do not recreate Codia assembly/control/tree/emitter/compiler/leaf/DSL 0.2 packages as product-generation paths.

Codia comparison-only code lives under:

```text
services/backend-go/internal/eval/codia
```

## Frozen Research Assets

These directories are intentionally retained but are not current product entrypoints:

```text
backend/
services/backend-python/
services/pencil-go/
packages/dsl-schema/
packages/image-to-figma-renderer/
figma-plugin/
docs/reference/legacy/
docs/plans/archive/
docs/code-reviews*/
docs/reports/
docs/prototypes/
```

Treat them as historical, deferred runtime, eval, or research assets according to [legacy-code-inventory.md](legacy-code-inventory.md). Do not delete or revive them by default.

## Package Responsibilities

`internal/app` owns HTTP, task lifecycle, storage paths, safe file names, and panic recovery.

`internal/image` owns generic image math and file handling. It must not know about UI roles, Draft layer kinds, Codia roles, or providers.

`internal/m29` owns physical evidence and source measurements.

`internal/vision` owns provider-neutral model configuration, detector passes, response parsing, bounded concurrency, and review decisions.

`internal/draft` owns the product contract: layer ownership, asset references, group hints, z-order, validation, report output, and runtime DSL export.

`internal/eval` owns Codia/golden comparison and metrics. Generation packages must not import it.

## Command Responsibilities

`cmd/draftserver` is the historical/deferred Draft HTTP runtime.

`cmd/draftcompile` is the local CLI for one PNG to Draft artifacts.

`cmd/draftdetect` is the detector-only CLI.

`cmd/drafteval` is the eval CLI and may read Codia golden samples. It supports Codia canvas analysis, Codia IR diff, and failure audit only; it does not generate Draft output.

`cmd/m29extract` and `cmd/m29trace` remain M29 diagnostic commands.

## Artifact Names

Draft artifact names:

```text
m29_physical_evidence.v1.json
ui_detector_candidates.v1.json
ui_candidate_review.v1.json
editable_layer_graph.v1.json
draft_runtime.dsl.v1.json
draft_validation_report.md
asset_manifest.json
```

Artifact names should include a version when they are contracts.

## Import Rules

Allowed high-level direction:

```text
app -> m29 / vision / draft
draft -> image / m29 / vision contract types
vision -> image
m29 -> image
eval -> draft / m29 / vision / Codia samples
renderer/plugin -> DSL only
```

Forbidden:

```text
draft -> eval
vision -> eval
m29 -> eval
renderer -> backend
plugin UI -> Figma API
generation -> Codia golden
```
