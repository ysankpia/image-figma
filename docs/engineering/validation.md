# Validation Strategy

Current validation protects the Pencil assisted slice delivery path.

```text
1..N images
-> candidates.v1.json
-> review_state.v1.json
-> manual_slices.v1.json
-> export-preview
-> project.zip + selected-assets.zip
```

## Canonical Checks

Repository-level baseline:

```bash
git diff --check
git status --short --branch
```

Current Pencil backend:

```bash
cd services/pencil-python-backend
make check
make slice-acceptance IMAGE=/absolute/path/to/image-or-dir OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

Historical/deferred Go backend:

```bash
cd services/backend-go
go test ./...
```

Renderer:

```bash
pnpm --filter @image-figma/image-to-figma-renderer run typecheck
pnpm --filter @image-figma/image-to-figma-renderer run test
```

Plugin:

```bash
pnpm --filter @image-figma/figma-plugin run typecheck
pnpm --filter @image-figma/figma-plugin run build
```

## Targeted Checks

Draft contract and assembly, only when explicitly working on Go Draft:

```bash
cd services/backend-go
go test ./internal/draft/...
```

Vision provider/detector/review:

```bash
cd services/backend-go
go test ./internal/vision/...
```

Server and task runtime:

```bash
cd services/backend-go
go test ./internal/app/... ./cmd/draftserver
```

M29 evidence:

```bash
cd services/backend-go
go test ./internal/m29/...
```

## Real Sample Validation

Use at least these samples for pipeline-visible changes:

```text
Tencent 018
Tencent 022
Lizhi 011
Xianyu
```

For each sample, inspect:

```text
editable_layer_graph.v1.json
draft_runtime.dsl.v1.json
draft_validation_report.md
asset_manifest.json
renderer/plugin warning output
```

Required signals:

- asset missing = 0;
- plugin image load failed = 0;
- visible full-page backing = 0;
- visible body-scale backing under editable children = 0;
- TextLayer covered by RasterLayer = 0;
- unauthorized large sibling overlap = 0;
- ordinary OCR text remains editable;
- compact image/icon/avatar/cover evidence becomes RasterLayer when supported;
- ShapeLayer does not carry foreground text pixels;
- major regions can be moved as groups.

## Codia Eval

Codia golden samples may be used only for eval:

```text
docs/reference/codia-samples/
internal/eval/codia
```

Generation packages must not import Codia eval packages or read golden JSON.

Useful eval metrics:

- image/icon recall;
- text editable recall;
- extra raster count;
- missing asset count;
- overlap violations;
- region grouping stability.

Tree match metrics are diagnostic only and must not become the product acceptance gate.

## Failure Ownership

Fix the owning layer:

```text
OCR/source issue -> OCR adapter or source normalization
physical bbox/crop issue -> M29 or image package
semantic label/missing candidate -> vision detector/review
emit/consume/suppress issue -> draft/assemble
asset reference issue -> draft/asset or app/server
DSL shape issue -> draft/exportdsl
render warning issue -> renderer after confirming DSL is valid
plugin flow issue -> plugin route/wiring
```

Do not patch the renderer or plugin to hide backend layer ownership bugs.
