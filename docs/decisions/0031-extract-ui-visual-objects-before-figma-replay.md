# ADR 0031: Extract UI Visual Objects Before Figma Replay

## Status

Accepted.

## Context

M20-M25 fixed-region icon rules produced useful evidence but did not scale to dense commerce UI. M26 compared provider directions, and M27 proved that SAM2 tiny can run locally with MPS and cached runtime. On the M28 fixed complex screenshot, M27 accepted only a tiny subset because its filters still carried old page-specific assumptions such as bed-map and illustration zones.

The next decision is not to replay icons into Figma. The missing primitive is a clean object-level visual extraction contract: image assets should stay whole, icons should be independently cropped, and text/background/container fragments should not become accepted assets.

## Decision

M28 introduces a single-image SAM2 UI visual extraction harness. It uses SAM2 automatic masks as proposals and then applies object-level classification:

- whole hero/banner/product/supplier images become `image_asset`;
- image assets create protection zones, and their internal SAM2 fragments are blocked;
- UI icons become `icon_candidate`;
- button-like composed objects become `control_candidate`;
- text, numbers, lines, card/background fragments and status bar objects are blocked.

M28 does not use M25/M27 page-specific exclusions. It also does not modify DSL, Renderer input or Figma output. The output is a JSON report, cropped PNGs, overlay and preview sheet for manual review.

## Consequences

- The project stops treating every visual mask as an icon candidate.
- Product photos and hero images are preserved as usable assets instead of being split into tomatoes, vegetables or texture fragments.
- The next replay stage can consume a cleaner object pool.
- M29 should be based on M28 evidence, not on further expansion of fixed coordinate rules.
- The harness is intentionally single-image and evidence-only until the extraction quality is good enough to generalize.
