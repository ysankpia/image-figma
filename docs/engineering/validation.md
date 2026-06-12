# Validation Strategy

Current validation protects the Slice Studio delivery path:

```text
1..N UI screenshots/design images
-> repository root
-> saved SliceRecord boxes in SQLite
-> assets.zip
-> project.zip / design.pen
```

Static checks are baseline evidence. User-facing slice, OCR, AI, export, and handoff work also needs a real project or artifact validation pass.

## Canonical Checks

Run these before handoff for ordinary Slice Studio changes:

```bash
pnpm run check
pnpm run build
git diff --check
git status --short --branch
```

Use `pnpm run dev` from the repository root for local manual validation:

```text
Next web:  http://127.0.0.1:3010
Elysia API: http://127.0.0.1:4110
```

## Slice Studio Runtime Validation

For visible workflow, export, OCR, M29, AI boxes, or persistence changes, validate a real project:

1. Start Slice Studio from the repository root.
2. Upload one or more real UI screenshots/design images.
3. Draw or generate slices.
4. Save and refresh the page.
5. Confirm saved boxes still appear in the canvas and asset list.
6. Export `assets.zip`.
7. Export `project.zip`.
8. Inspect `manifest.json`, `project.json`, and `design.pen`.

Required signals:

- project pages remain in the expected order;
- saved slices are preserved after refresh;
- duplicate AI runs do not create excessive overlapping boxes;
- `assets.zip` contains only package-local paths;
- `project.zip` contains `design.pen`, originals, visible remainder assets, and visible slice assets;
- `.pen` visible image refs are package-local and do not point to absolute paths, `source.png`, debug assets, or `../`;
- OCR text overlays do not cover confirmed raster assets;
- M29 physical evidence only affects text bbox placement and does not create visible layers;
- export fails clearly when there are no slices instead of producing a misleading package.

## AI Slice Box Validation

For `server/ai-slice-boxes/` and Review Workbench AI controls:

```bash
pnpm run check
```

Then run a real smoke when a provider key is available:

```text
Open a multi-page project
-> AI 当前页
-> verify boxes appear as normal slices
-> save/refresh
-> AI 全部页
-> verify progress, failures, and added count
-> export assets/project
```

The current default prompt strategy is documented in [../reference/slice-studio-ai-slice-prompt-strategies.md](../reference/slice-studio-ai-slice-prompt-strategies.md). Prompt changes must update that reference when they change inclusion/exclusion behavior.

## OCR And M29 Text Validation

For editable text handoff work:

- validate with `SLICE_STUDIO_OCR_PROVIDER=baidu_ppocrv5` when a local token is configured;
- validate `SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=ts_m29_physical_evidence` as the default;
- use `go_m29extract` only as an explicit reference/fallback comparison;
- inspect `project.zip/design.pen` and manifest metadata for text layer counts, bbox source, provider failures, and skipped noisy text.

Required signals:

- OCR remains the text-content authority;
- TypeScript M29 physical evidence only improves OCR line bboxes;
- OCR failure still allows raster handoff export with recorded diagnostics;
- Go `m29extract` is not required for default Slice Studio deployment.

## Historical Checks

Use these only when a task explicitly targets old paths.

Python Pencil assisted slice reference:

```bash
cd archive/legacy-code/services/pencil-python-backend
make check
make slice-acceptance IMAGE=/absolute/path/to/image-or-dir OUT=/Volumes/WorkDrive/pencil-exports/slice-acceptance
```

Go Draft/M29 reference:

```bash
cd archive/legacy-code/services/backend-go
go test ./...
```

Renderer:

```bash
cd archive/legacy-code/packages/image-to-figma-renderer
pnpm run typecheck
pnpm run test
```

Figma plugin:

```bash
cd archive/legacy-code/figma-plugin
pnpm run typecheck
pnpm run build
```

## Codia Eval Boundary

Codia golden samples are eval/reference only:

```text
docs/reference/codia-samples/
archive/legacy-code/services/backend-go/internal/eval/codia
```

Generation code must not import Codia eval packages or read golden JSON. Tree-match metrics are diagnostic only and must not become the product acceptance gate.

## Failure Ownership

Fix the owning layer:

```text
Slice persistence issue -> server/projects.ts or server/db.ts
source image/crop issue -> shape-cutout/exporter/pencil-exporter
AI bbox issue -> ai-slice-boxes provider, tiling, parsing, merge, or prompt contract
OCR source issue -> text-ocr provider
physical bbox issue -> m29-physical-evidence or m29-text-locator
Pencil package issue -> pencil-exporter or pencil-package
legacy Draft issue -> archive/legacy-code/services/backend-go/internal/draft
renderer/plugin warning -> verify the contract first, then fix renderer/plugin only if the contract is valid
```

Do not patch export artifacts by hardcoding sample names, visible text, fixed coordinates, or screenshot-specific rules.
