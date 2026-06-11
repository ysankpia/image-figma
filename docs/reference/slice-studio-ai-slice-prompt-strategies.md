# Slice Studio AI Slice Prompt Strategies

This note records the prompt strategy decision for Slice Studio AI rect slicing on 2026-06-11.

## Current Default

The default strategy is `CC`:

```text
tile prompt: C / Inclusive-Icons
overview prompt: C / Inclusive-Icons Overview
```

The current priority is recall and repeatability. Extra slices are acceptable because the user can delete them during review. Missing custom icons are more expensive because they may force the user to redraw SVGs from the screenshot.

## Strategy Matrix

The first letter controls the six tile prompts. The second letter controls the compressed full-page overview prompt.

| Strategy | Meaning |
| --- | --- |
| `A` | Strict. Crop only obvious high-fidelity raster assets such as photos, hero illustrations, cover art, rich badges, and brand logos. Exclude common utility icons, tabs, bottom navigation, and controls. |
| `B` | Balanced. Crop photos, illustrations, brand marks, and visually complex or colorful icons. Avoid ordinary controls and flat navigation icons. |
| `C` | Inclusive-Icons. Actively crop distinct icons, stylized UI icons, navigation icons, action icons, photos, illustrations, logos, and decorative graphics while still excluding text and structural containers. |

Nine combinations are possible:

```text
AA AB AC
BA BB BC
CA CB CC
```

`CC` is the current default. `BB` remains the clean-mode reference if future samples show unacceptable over-slicing.

## Evidence

Local prompt experiments used repeated model calls on the unstable `525测试` samples. Each result below is three runs on the same page.

| Sample | Strategy | Counts | Bottom counts | Stable 3/3 clusters | Judgment |
| --- | --- | --- | --- | ---: | --- |
| P1 | `CC` | `21 / 24 / 24` | `7 / 8 / 9` | 20 | Stable, high recall, cuts bottom/action icons. |
| P4 | `CC` | `15 / 17 / 17` | `5 / 6 / 5` | 14 | Stable, high recall, cuts playback/nav icons. |
| P4 | `BB` | `4 / 3 / 3` | `0 / 0 / 0` | 3 | Clean but too conservative for the current product priority. |

The controlling contradiction is not whether the asset list is maximally clean. It is whether AI gives a stable, useful starting point and avoids missing icons that are hard to reconstruct from icon libraries.

## Product Boundary

This strategy does not change the Slice Studio data contract:

```text
AI returns transient boxes
frontend turns boxes into normal rect slices
manual slices remain the export truth source
Pencil/Figma export behavior is unchanged
```

This decision also does not add consensus, source metadata, or mode switching. If repeated-click behavior becomes the next bottleneck, solve it separately by making AI-generated slices replaceable or by adding a high-quality consensus mode.
