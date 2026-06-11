# Anti-Specialization Rules

Slice Studio and historical Draft logic must generalize across screenshots. Do not trade broad correctness for one good sample.

## Forbidden Inputs For Generation Logic

Generation code must not branch on:

```text
file name
file path
task id
sample id
brand
visible copy/text
fixed bbox
fixed coordinate
fixed screen size
Figma page name
Codia golden node id
```

This applies to Slice Studio AI boxes, cutout/export, OCR, M29 text placement, historical vision, Draft assembly, asset export, renderer, plugin, and validation gates.

## Allowed Evidence

Generation may use:

```text
source image pixels
OCR text/bbox/confidence
M29 primitives/tokens/measurements
vision candidates/review decisions
AI tile/overview bbox candidates
relative geometry
image-scale-normalized thresholds
local color/edge/texture measurements
artifact validation results
saved SliceRecord data
```

## Heuristic Requirements

Any heuristic that affects visible output must have:

- a general rationale;
- a named owning layer;
- tests or real-sample validation;
- no dependency on one screenshot's text/name/path/coordinates.

If a heuristic only improves one sample while degrading others, revert or keep it behind eval-only reporting.

## Codia Golden Boundary

Codia golden data is allowed in eval and offline analysis only.

Forbidden:

```text
internal/draft importing internal/eval/codia
internal/m29 importing internal/eval/codia
internal/vision importing internal/eval/codia
runtime reading docs/reference/codia-samples/*.json
using golden bbox/node names as generation hints
```

Allowed:

```text
drafteval reads generated artifacts and Codia golden
offline reports compare generated layers to Codia reference
training-label extraction happens outside runtime generation
```

## Review Checklist

Before committing visible-output logic, run:

```bash
rg -n "腾讯|动漫|荔枝|闲鱼|东方|茉莉|山野|乌龙|去结算|首页|点单|tencent|lizhi|xianyu|018|022|011|PixPin|ChatGPT_Image|task_|project_mq" apps/slice-studio services/backend-go packages figma-plugin
```

Any match in generation code needs a strong reason or removal.
