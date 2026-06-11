# 174 Slice Studio Shape Cutout Contour Barrier

## Summary

Fix `apps/slice-studio` transparent cutout leakage. The current shape mode treats "edge-connected pixels similar to background color" as removable background, but it does not build a real contour barrier. On UI screenshot assets with soft photo/card content, flood fill leaks through weak boundaries and removes internal pixels.

This plan changes only the shape cutout algorithm. It does not change API, SQLite, export ZIP structure, UI workflow, or project storage.

## Facts

- `applyShapeCutout()` estimates a background color from expanded crop edges.
- It marks every pixel within threshold as `backgroundMask`.
- `pushFloodSeed()` can move through any `backgroundMask` pixel.
- There is no edge, contour, foreground, or closed-boundary mask.
- Real sample `slice_0015` and `slice_0016` show large internal transparent regions because internal light pixels are connected to the expanded crop edge.

## Target Behavior

Shape mode should mean:

```text
remove outside/background around the asset
keep pixels inside the asset contour
do not remove internal content just because it resembles the surrounding background
```

## Implementation

- Keep `cropSliceToPng()` public behavior unchanged.
- Replace the pure background-color flood fill with a contour-aware mask:
  - Continue using expanded crop context.
  - Estimate outside background from expanded crop edges.
  - Build a background candidate mask.
  - Build a protected foreground/interior mask from the requested bbox region and color/edge evidence.
  - Prevent outside flood fill from crossing protected interior pixels.
  - Use morphology to close tiny gaps so the mask does not leak through anti-aliased or weak boundaries.
- Keep final PNG dimensions exactly equal to the requested bbox.

## Tests

- Existing simple icon/shape cutout still removes outside background.
- Dark enclosed content remains opaque.
- Tight crops still use surrounding context and return requested bbox size.
- New regression: an image card with internal pixels similar to the outside background must not have its interior removed.
- Real sample check: `slice_0015` and `slice_0016` alpha masks should not show flood fill crossing the full card interior.

## Validation

```bash
cd apps/slice-studio
bun run check
bun run build

cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma
git diff --check
git status --short --branch
```
