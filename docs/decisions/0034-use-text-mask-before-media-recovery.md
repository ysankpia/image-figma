# ADR 0034: Use Text Mask Before Media Recovery

## Status

Accepted.

## Context

M29/M29.1 can find many visual fragments, but real screenshots contain dense UI text. Without text boxes, text strokes enter symbol, blocked, and grouping evidence. This makes it hard to tell whether visible pictures/icons are missing, misclassified, or simply hidden among text fragments.

Directly erasing text from final assets would be wrong because banner text, package labels, and button labels can be part of the original bitmap evidence.

## Decision

Add M29.0.2 as a script-only audit harness:

```text
source PNG + OCR/text boxes -> text_mask -> text-suppressed analysis -> media evidence audit
```

The text-suppressed image is only an analysis artifact. All exported evidence crops remain cut from the original source PNG. The harness may run M29 on the suppressed analysis view in a local audit directory, but it does not change M29/M29.1 outputs, upload APIs, DSL, Renderer, or Figma output.

Remote Paddle OCR is opt-in only. Reproducible smoke runs can use `--text-boxes-json` or `--ocr-json`.

## Consequences

- Text noise becomes explicit evidence instead of being confused with image/icon loss.
- Media candidates can be compared before and after text masking.
- The next fix can target the right layer: M29 image acceptance, M29.1 grouping, or M30 OCR text reconstruction.
- Final bitmap assets remain faithful to the original screenshot.
