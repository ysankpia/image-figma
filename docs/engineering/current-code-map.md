# Current Code Map

This document maps the current Editable Draft branch. It describes where new work should land. It is authoritative for new code.

## Product Mainline

```text
Figma Plugin
-> /api/draft-preview
-> services/backend-go internal/app
-> internal/m29
-> internal/vision
-> internal/draft
-> Draft Runtime DSL
-> packages/image-to-figma-renderer
-> Figma
```

## Pencil Project Export Surface

`services/pencil-python-backend` is the current Pencil project package export route. It is separate from the Draft runtime mainline and does not import the renderer/plugin/Draft packages. It uses the already-validated Python Pencil exporter. The default HTTP/CLI boundary source is `psdlike`; explicit `m29` and `hybrid` remain available.

```text
1..N PNG
-> PSD-like boundary source by default
-> Python Pencil exporter
-> project ZIP builder
-> clean-editable / visual-fidelity / visual-ocr .pen ZIP
```

Operational files:

```text
services/pencil-python-backend/deploy/pencil-python-backend.env.example
services/pencil-python-backend/deploy/pencil-python-backend.service
services/pencil-python-backend/scripts/http_smoke.py
docs/runbooks/pencil-python-backend-deploy.md
```

`services/pencil-go` is retained as a superseded experiment and should not be extended as the current product delivery path.

## Go Backend Target Layout

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

## Package Responsibilities

`internal/app` owns HTTP, task lifecycle, storage paths, safe file names, and panic recovery.

`internal/image` owns generic image math and file handling. It must not know about UI roles, Draft layer kinds, Codia roles, or providers.

`internal/m29` owns physical evidence and source measurements.

`internal/vision` owns provider-neutral model configuration, detector passes, response parsing, bounded concurrency, and review decisions.

`internal/draft` owns the product contract: layer ownership, asset references, group hints, z-order, validation, report output, and runtime DSL export.

`internal/eval` owns Codia/golden comparison and metrics. Generation packages must not import it.

## Command Responsibilities

`cmd/draftserver` is the Draft HTTP runtime.

`cmd/draftcompile` is the local CLI for one PNG to Draft artifacts.

`cmd/draftdetect` is the detector-only CLI.

`cmd/drafteval` is the eval CLI and may read Codia golden samples. It supports Codia canvas analysis, Codia IR diff, and failure audit only; it does not generate Draft output.

`cmd/m29extract` and `cmd/m29trace` remain M29 diagnostic commands.

## Artifact Names

Current main artifacts:

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
