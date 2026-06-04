# 113 PSD-like Vertical Media Stack Raster Splitting

## Status

Active.

## Summary

Fix the case where a vertical stack of repeated media thumbnails is emitted as one tall `RasterLayer` asset. The observed latest server task is:

```text
/Users/luhui/Downloads/psdlike_python_server_tasks/412b114b777e4d4a8ce04cece3c6fe7c
```

In that task, the product image column is currently emitted as:

```text
raster_0009
reason = foreground_object_on_surface
bbox = x256 y472 w232 h992
asset = assets/raster_0009.png
```

The problem is not that the asset is missing. The problem is that the media column is owned as one large vertical raster instead of independent repeated image crops.

## First Principles

PSD-like ownership should make editable layers correspond to independent visible objects. A repeated list of product thumbnails is not one object just because foreground extraction connected or merged the column. If repeated high-texture image regions are separated by horizontal gutters or low-texture background bands, each media item should own its own raster asset and the parent strip should be suppressed.

The correct chain is:

```text
large vertical raster candidate
-> detect repeated high-texture media slices along y
-> emit independent RasterLayer assets for each slice
-> suppress parent vertical strip raster
```

## Scope

Allowed:

- `services/psdlike-python/app/core/candidates.py`
- `services/psdlike-python/app/core/pipeline.py`
- `services/psdlike-python/tests/test_core_pipeline.py`
- this plan document

Forbidden:

- renderer/plugin coordinate hacks;
- sample id, file path, visible text, brand, theme, fixed coordinate, fixed bbox, or fixed screen size rules;
- changing DSL/API schema;
- deleting real long media, maps, charts, or posters just because they are tall.

## Generic Gate

Only split a raster when all physical conditions hold:

- candidate reason is media-like (`foreground_object_on_surface`, `high_texture_low_text_overlap`, or `high_texture_with_internal_text`);
- candidate is tall enough relative to width;
- candidate area is large enough to plausibly contain repeated image slices;
- candidate has low text overlap;
- there are at least two high-texture child bands;
- child bands have similar x-span and substantial width coverage;
- child bands are separated by visible horizontal gutters or low-texture/background-like rows;
- children are not tiny fragments and are not mostly OCR text.

Do not split:

- a single tall poster/cover/map/chart with no repeated horizontal gutters;
- text-heavy raster regions;
- small icons or controls;
- wide banners.

## Implementation Sketch

Add a function near raster candidate refinement:

```text
split_vertical_media_stack_rasters(rgb, raster_candidates, text_mask)
```

For each tall media-like raster:

1. Analyze the crop row-by-row using local edge/texture/foreground evidence.
2. Find horizontal gutter runs with low texture/low edge/low foreground occupancy.
3. Convert the spans between gutters into child bboxes.
4. Keep child bboxes that preserve most of the parent width and have enough visual texture.
5. If at least two children are accepted and their combined area explains the parent media content, suppress the parent and append child raster candidates.

Children should carry source evidence:

```text
reason = vertical_media_stack_item
scores.verticalMediaStackItem = 1
scores.parentRasterId = ...
```

Rejected/suppressed decisions should include:

```text
kind = vertical_media_stack_parent_suppressed
reason = vertical_media_stack_split
```

## Tests

Add synthetic fixtures:

- a vertical column with three image-like textured rounded rectangles separated by gutters splits into at least three `RasterLayer`s;
- a single tall textured poster without internal gutters does not split;
- existing control/text/media ownership tests remain passing.

## Validation

Static:

```bash
cd /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/services/psdlike-python
python -m py_compile $(find app tools -name '*.py' | sort)
uv run pytest -q
```

Runtime targeted:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/draft-preview \
  -F 'image=@/path/to/latest-tea-order-input.png'
```

Acceptance for the latest tea-order task:

- the old `232x992` parent strip is not the only product-column media owner;
- the product image column is emitted as multiple independent raster assets;
- no full-page visible raster, no tiny raster fragments, no missing assets;
- draft preview does not visually lose the product images.

## Validation Evidence

Pending.
