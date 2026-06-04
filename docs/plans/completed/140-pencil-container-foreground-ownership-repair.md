# 140 Pencil Container Foreground Ownership Repair

Status: completed

## Summary

Fix Pencil Python Backend complex UI exports where large raster/container layers own foreground UI items that should remain independently draggable/editable.

The first regression sample is `/Users/luhui/Downloads/Screenshot - 腾讯动漫_018_1440.png.png`, but the implementation must not use sample path, file name, brand, visible text, fixed coordinates, bottom/tab/mobile-navigation checks, or page-specific logic.

## Root Cause

Current PSD-like to Pencil export can preserve visual content by emitting large raster/container crops, but those crops can swallow foreground objects. Evidence from the regression sample shows raw OCR blocks contain local labels that are absent from `layer_stack.v1.json` text layers, and the final `.pen` places a large raster over the region. The owner defect is upstream of Pencil/Figma import: container/background ownership is too broad.

## Scope

- Add `container_foreground_audit.v1.json` debug artifact.
- Detect large container/raster layers that contain raw OCR text blocks and local raster/shape evidence not emitted as independent Pencil layers.
- Detect repeated local foreground item groups using geometry, OCR bboxes, primitive bboxes, containment, alignment, spacing, and local bounds.
- Release safe foreground items from broad container ownership for `clean-editable` and `visual-ocr`.
- Preserve `visual-fidelity` as the visual fallback.
- Keep media/product/comic/image internal text raster-owned unless it is proven to be ordinary UI chrome text.

## Non-Goals

- No bottom-tab, mobile-nav, brand, file-name, text-literal, fixed-coordinate, or fixed-bbox special cases.
- No Figma plugin changes.
- No `services/pencil-go` changes.
- No Codia golden/runtime hints.
- No full semantic UI tree or Auto Layout reconstruction.

## Validation

Required commands:

```bash
cd services/pencil-python-backend
make check
```

Regression export:

```bash
PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE=psdlike OCR_PROVIDER=baidu_ppocrv5 pencil-export \
  --input "/Users/luhui/Downloads/Screenshot - 腾讯动漫_018_1440.png.png" \
  --out /Volumes/WorkDrive/pencil-exports/tencent-comic-018-ownership-repair-YYYYMMDD-HHMMSS \
  --project-name "Tencent Comic 018 Ownership Repair" \
  --mode all \
  --columns auto \
  --include-debug
```

Acceptance:

- Export succeeds and manifest has no fatal warnings.
- Debug package contains `container_foreground_audit.v1.json`.
- The audit identifies large container/raster foreground conflicts in the regression sample.
- `clean-editable` and `visual-ocr` retain normal editable text.
- Repeated local foreground items are no longer only embedded in one broad raster/container.
- Media/comic/product image internal text is not promoted as ordinary editable UI text.
- `visual-fidelity` is not visibly degraded versus the pre-repair output.
- All three modes have `badRefs=0` and `missingRefs=0`.
- Inspect generated preview/debug artifacts, not only command exit codes.

## Anti-Specialization

Before commit, inspect production code for:

```text
sample path/name checks
brand or visible text checks
fixed coordinates
bottom/tab/mobile-nav strings
single screenshot structure assumptions
```

Any thresholds must be documented by geometry rationale and failure mode.

## Current Implementation Notes

The repair is implemented at the PSD-like evidence adapter and Pencil export ownership layers, not in the Figma plugin.

- `container_foreground_audit.v1.json` records broad container/raster owners, missing OCR blocks, foreground conflicts, and repeated local foreground groups.
- PSD-like adaptation now synthesizes safe foreground text layers when raw OCR evidence was swallowed by a broad container.
- PSD-like adaptation now synthesizes safe repeated foreground image items by cropping from `source.png`, not by stitching existing fragment crops.
- Exporter honors `compileHints.foregroundObjectRelease` so released foreground text is not rejected as raster-owned visual text.
- Exporter prevents a component parent from suppressing a foreground-released child.
- `visual-fidelity` skips synthetic foreground image overlays to preserve the stable visual fallback.
- `clean-editable` and `visual-ocr` include released foreground text/image items so they can be selected independently in Pencil/Figma.

The core policy name is:

```text
container_foreground_ownership_repair.v1
```

The implementation is intentionally generic. It does not branch on bottom tabs, mobile navigation, Tencent, visible text strings, fixed coordinates, file names, or sample paths.

## Local Validation Evidence

The exact prompt-provided Downloads sample path was missing during validation:

```text
/Users/luhui/Downloads/Screenshot - 腾讯动漫_018_1440.png.png
```

Validation used the matching source image found under the local Figma image export directory:

```text
/Users/luhui/Downloads/figma/image/腾讯动漫_018_1440.png
```

Latest export:

```text
/Volumes/WorkDrive/pencil-exports/tencent-comic-018-ownership-repair-20260604-100506
```

Checks passed:

```bash
cd services/pencil-python-backend
make check
```

Result:

```text
26 passed, 2 warnings
git diff --check: clean
```

Export manifest:

```text
boundarySource=psdlike
modes=clean-editable, visual-fidelity, visual-ocr
warnings=[]
```

Page export summary:

```text
clean-editable:  textNodes=41, cropNodes=32, sourceFallbackNodes=0
visual-fidelity: textNodes=0,  cropNodes=70, sourceFallbackNodes=0
visual-ocr:      textNodes=41, cropNodes=36, sourceFallbackNodes=0
```

Final matching-source export summary:

```text
clean-editable:  textNodes=35, cropNodes=27, sourceFallbackNodes=0
visual-fidelity: textNodes=0,  cropNodes=71, sourceFallbackNodes=0
visual-ocr:      textNodes=35, cropNodes=43, sourceFallbackNodes=0
```

Reference checks:

```text
clean-editable:  badRefs=0, missingRefs=0
visual-fidelity: badRefs=0, missingRefs=0
visual-ocr:      badRefs=0, missingRefs=0
```

Audit summary:

```text
containerCount=18
rawOcrBlockCount=47
emittedTextBlockCount=32
missingOcrBlockCount=15
conflictCount=14
repeatedGroupCount=3
```

Final matching-source audit summary:

```text
containerCount=21
rawOcrBlockCount=47
emittedTextBlockCount=32
missingOcrBlockCount=15
conflictCount=17
repeatedGroupCount=3
```

Pencil MCP visual inspection opened:

```text
/Volumes/WorkDrive/pencil-exports/tencent-comic-018-ownership-repair-20260604-095023/clean-editable/design.pen
```

Final matching-source Pencil MCP visual inspection opened:

```text
/Volumes/WorkDrive/pencil-exports/tencent-comic-018-ownership-repair-20260604-100506/clean-editable/design.pen
```

Observed in Pencil screenshot:

- bottom local text labels are visible as independent text objects;
- ranking image cards labeled 1/2/3 are visible as separate foreground raster objects;
- repeated benefit/gift cards are visible as separate foreground raster objects;
- visual-fidelity remains the stable fallback mode.

## Remaining Risk

This is a conservative ownership repair, not a full semantic UI reconstruction. It may still miss complex foreground object groups when repetition, local texture, OCR support, or safe boundaries are weak. That is acceptable for this phase: missed release is safer than merging unrelated controls into an unusable object.

Do not broaden the rule by adding sample-specific checks. If a new failure appears, add a debug artifact and a regression test that proves the generic source fact: swallowed OCR, swallowed foreground image item, unsafe container owner, or broken asset reference.
