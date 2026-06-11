# 181 Slice Studio TS M29 Physical Evidence

Status: active

## Problem

Slice Studio editable text export uses OCR for text content and M29 physical evidence for tighter visual bboxes. The working local path previously called the Go `m29extract` binary as:

```text
m29extract --ocr-provider none
```

That deployment dependency is unnecessary for Slice Studio, but the TypeScript replacement must preserve the actual Go behavior Slice Studio consumes. The current product does not need a new OCR-derived text-region algorithm. It needs the Go no-OCR physical evidence kernel: bitmap pixels become foreground components and classified physical primitives; OCR is used later by the locator to match text lines to those physical fragments.

## Scope

- Add a TypeScript `m29-physical-evidence` module inside `apps/slice-studio/server/`.
- Port the current Go M29 no-OCR physical kernel behavior used by Slice Studio:
  - PNG decode;
  - edge background estimate;
  - foreground mask;
  - 4-neighbor connected components;
  - component measurements;
  - Go-compatible primitive classification;
  - physical relation graph.
- Keep OCR as text-content authority in Slice Studio.
- Keep manual slices as final visible asset truth source.
- Keep Pencil/Figma text node output strategy unchanged.
- Keep Go `m29extract` as explicit reference/fallback via config.

## Non-Scope

```text
Draft/Codia revival
semantic UI reconstruction
automatic M29 cut ownership as final layer truth
sample/file/text/coordinate-specific thresholds
OCR-derived tight text_region synthesis
subject/card cutout changes
```

The first TS implementation intentionally does not port Go OCR-provider, OCR-anchored surface, debug mask/crop asset writing, or internal raster crop branches into the default Slice Studio path. Those branches are not used by the existing Slice Studio `m29extract --ocr-provider none` call.

## Design

The default provider is controlled by:

```text
SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER=ts_m29_physical_evidence
```

Allowed providers:

```text
ts_m29_physical_evidence
go_m29extract
ocr
```

Provider semantics:

```text
ts_m29_physical_evidence:
  source PNG -> TS M29 no-OCR physical primitives -> OCR lines matched by locator

go_m29extract:
  source PNG -> Go m29extract --ocr-provider none -> OCR lines matched by locator

ocr:
  no physical evidence; keep OCR bbox fallback
```

The public high-level bbox provider reported in Slice Studio artifacts remains `m29_ocr_hybrid`: OCR identifies text content; M29 supplies physical foreground evidence only.

## Go Parity Notes

The TS module ports these Go behaviors:

```text
EstimateBackground:
  edge sample step = max(1, min(width,height)/160)
  median RGB
  threshold = clamp(max(18, p95*2.2), 18, 52)

Foreground mask:
  ColorDistance(pixel, background) > threshold
  text mask is empty in the default no-OCR path

Connected components:
  4-neighbor flood fill
  minArea = max(8, width*height/90000)
  maxAreaRatio = 0.80

Classification:
  line / rect / surface_region / image_region / symbol_region / unknown_region
  ordered to match Go primitive.Classify
```

For the real P1 sample:

```text
/Users/luhui/Downloads/project_mq8plzjo_257c14b7-project (6)/assets/originals/P1.png
```

TS no-OCR output matches the Go reference distribution:

```text
foregroundThreshold: 33.36465195382682
foregroundPixelCount: 394985
componentCount: 448
primitiveCount: 448
types:
  symbol_region: 428
  line: 8
  image_region: 8
  rect: 3
  surface_region: 1
```

## Acceptance

- TS extractor returns deterministic `M29PhysicalEvidence` documents from PNG buffers.
- No-OCR TS output does not synthesize `text_region`.
- OCR line matching can use TS physical primitives and still falls back per line to OCR bbox when no physical match exists.
- If the TS extractor throws, export still succeeds and manifest records OCR fallback reason.
- Go binary is no longer required for the default Slice Studio editable text bbox path.
- P1 distribution remains aligned with Go no-OCR output.

## Validation

```bash
pnpm --dir apps/slice-studio run check
pnpm --dir apps/slice-studio run build
git diff --check
git status --short --branch
```

Reference check:

```bash
cd services/backend-go
go test ./internal/m29/... ./cmd/m29extract
```
