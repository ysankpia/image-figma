# Current Code Map

This document maps the current Editable Draft branch. It describes where new work should land. Historical files may still exist while the destructive refactor is in progress; this map is authoritative for new code.

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

## Current Legacy To Avoid

Do not add new product behavior to:

```text
services/backend-go/internal/codia/assembly
services/backend-go/internal/codia/control
services/backend-go/internal/codia/tree
services/backend-go/internal/codia/emitter
services/backend-go/internal/codia/compiler
services/backend-go/internal/codia/canvasexport
services/backend-go/internal/codia/leaf
services/backend-go/internal/codia/ir
services/backend-go/internal/codia/dsl02
```

These packages may remain temporarily for comparison or until the cleanup stage removes or archives them.

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

`cmd/drafteval` is the eval CLI and may read Codia golden samples.

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
