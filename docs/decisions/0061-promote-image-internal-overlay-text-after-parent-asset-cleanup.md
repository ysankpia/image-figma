# ADR 0061: Promote Image-Internal Overlay Text After Parent Asset Cleanup

## Status

Accepted

## Context

M29.3 can bind small overlay text evidence to a parent accepted image. M29.4 can optionally recognize that overlay as a narrow counter such as `1/6`. The remaining failure is materialization: if M30 simply creates a text node above the original parent bitmap, the old glyph pixels remain inside the image asset and create a visible double-render.

The parent image asset may also be skipped by normal M30 materialization because the very text we want to promote creates unsafe text overlap. Therefore the promotion stage must be able to create a cleaned parent image node when no parent image node exists yet.

## Decision

Add M30.5 as a controlled promotion stage after M30 materialization and before M30 asset publish.

M30.5 consumes only M29.4 `promotion_ready` items with a tight OCR bbox from local crop OCR. It copies the parent image asset, erases glyph pixels mapped from `recognizedTextBBox`, adds the cleaned copy as a new DSL asset, retargets or creates the parent image node, and appends an editable text node.

The first release defaults to one promotion per task.

## Consequences

- M29.2, M29.3, and M29.4 remain evidence/audit stages.
- M30.5 is the first stage that may turn image-internal overlay recognition evidence into visible DSL output.
- Original parent image assets remain unchanged and the cleaned asset is reproducible.
- M30 asset publish can publish cleaned parent assets through the existing `/files/assets/{taskId}/m30/...` path.
- Complex inpainting, dark-on-light overlays, OCR budgeting, and async OCR stay out of this stage.
