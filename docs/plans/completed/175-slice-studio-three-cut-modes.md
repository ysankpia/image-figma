# 175 Slice Studio Three Cut Modes

## Summary

Split the current ambiguous `shape` cut mode into explicit cut semantics:

```text
rect    -> rectangular crop
subject -> remove local background and keep the foreground subject/icon
card    -> remove only outside/edge background and preserve internal card/image content
```

This fixes the current contradiction where one "transparent" mode is expected to both remove icon white backgrounds and preserve photo/card interiors.

## Facts

- Current `shape` mode mixes two incompatible user intents.
- `subject` examples: icon, logo, badge, cart button, plus button, Google icon.
- `card` examples: product image card, banner, photo-like operation image, full button/card that must keep internal fills/textures.
- Size is not a valid authority: large icons and small image cards both exist.
- AI/VLM is not needed for v1; users can choose or batch switch the mode, and later AI may only suggest modes.

## Implementation

- Change `CutMode` to `rect | subject | card`.
- Migrate legacy `shape` DB values to `subject`.
- Allow DB values `rect`, `subject`, `card`.
- Keep export manifest field name `cutMode`; values change to the new union.
- Implement:
  - `subject`: original background flood fill behavior, no large interior guard.
  - `card`: guarded flood fill behavior that preserves internal content.
  - `rect`: unchanged rectangular crop.
- Update review UI:
  - Page-level segmented control: 矩形 / 抠主体 / 保内图.
  - Asset row cycle or selector supports all three modes.
  - Asset gallery labels show the selected mode.
- Update tests for normalization, manifest, and shape cutout behavior.

## Validation

- `#12` and `#18` should work in `subject` mode and not keep a big white square.
- `#15` and `#16` should work in `card` mode and not leak transparency into the image interior.
- Existing rectangular crops remain opaque.

Commands:

```bash
cd apps/slice-studio
bun run check
bun run build

cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
git diff --check
git status --short --branch
```
