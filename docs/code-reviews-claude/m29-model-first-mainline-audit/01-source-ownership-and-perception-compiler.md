# 01 Source Ownership and Perception Compiler Audit

## Fact: Source Ownership Boundaries
Source objects are classified in `backend/app/source_ui_physical_graph/` and compiled in `backend/app/perception_source_compiler/`.
* **OCR Text**: Handled in [text.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/text.py). High-confidence OCR text becomes `editable_text` with a replay decision of `text_replay`.
* **Shape Geometry**: Handled in [shapes.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/shapes.py). UI elements with simple geometries, low color counts, and low texture scores are replayed as `shape_replay`.
* **Raster Icons**: Handled in [icons.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/icons.py). Small symbol fragments and complex textured foreground components are clustered and replayed as `icon_replay`.
* **Media Regions**: Handled in [media.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/media.py). Large image-like regions or low-confidence unknowns are classified as `media_region` with an `image_replay` decision.

## Fact: Compiler Boundary Compliance
The compiler in [perception_source_compiler/pipeline.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/perception_source_compiler/pipeline.py) compiles model-proposed candidates into M29.2 source objects. It does not materialize nodes, write DSL files, or generate files in `materialized_design/`.
Compliance is guaranteed by the schema validation in [validation.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/perception_source_compiler/validation.py), which enforces `dslChanged = False`, `assetChanged = False`, and `createdVisibleNodeCount = 0`.

## Fact: Media Swallowing/Blocking Logic
In [media.py](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/media.py#L93-L101), the function `media_blocks_child_foreground` determines if a media region should block and swallow contained child foreground icons/shapes:
```python
def media_blocks_child_foreground(media: M292SourceObject) -> bool:
    if media.visual_kind != "media_region" or media.pixel_owner != "preserve_raster":
        return False
    if "low_confidence_media_region" in media.risks:
        return False
    if "contains_internal_text" in media.risks:
        return False
    return "m29_image_region" in media.reasons
```
This is called in [icons.py L35](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/icons.py#L35) and [shapes.py L59](file:///Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/app/source_ui_physical_graph/shapes.py#L59) to filter out icons/shapes.

## Inference: Protection Against Swallowing
1. **High-Confidence Media (Photos/Graphics)**: Blocks inner candidates (`return True`), which is correct because we do not want to crop-replay vector shapes or small text components inside a photo of a landscape or an illustration.
2. **Low-Confidence Media or Text-Containing Containers**: Returns `False` due to checking `"low_confidence_media_region"` and `"contains_internal_text"`. This protects inner icons and text inside cards, bottom tab bars, toolbars, and action rows from being blocked/swallowed. These child objects remain visible for separate replay.

## Risk
The swallowing protection is correct and robust. The primary risk lies downstream in the M29.5 replay plan layer where overlap suppression occurs. If a large container background is incorrectly replayed as `image_replay` and overlaps with children, or if icon containment thresholding is too aggressive, it will still suppress them (see `02-replay-cleanup-materializer-boundaries.md`).

## Recommendation
Keep the swallowing logic at M29.2. Never implement swallowing or blocking overrides in the materializer or Figma plugin UI.
