# Draft Runtime DSL

Draft Runtime DSL is the renderer input produced from `editable_layer_graph.v1.json`.

It is a rendering contract, not the ownership authority. Ownership decisions belong to Draft assembly.

## Source Chain

```text
Editable Layer Graph
-> Draft Runtime DSL
-> Renderer
-> Figma nodes
```

OCR, M29 evidence, vision candidates, review decisions, and Draft assembly reports are backend artifacts. Renderer consumes only DSL and asset URLs.

## Top-Level Shape

The first Draft DSL version should contain:

```text
version
kind
taskId
page
assets
root
meta
```

Recommended values:

```text
version = "1.0"
kind = "draft_runtime"
```

## Node Types

Draft DSL should represent:

```text
frame
group
text
shape
image
line
```

Draft graph layer mapping:

```text
Page           -> frame
GroupLayer     -> group
TextLayer      -> text
ShapeLayer     -> shape/line
RasterLayer    -> image
ReferenceImage -> hidden image or omitted from visible output
```

## Layout

First version uses absolute pixel layout:

```text
x
y
width
height
z
```

Auto Layout, responsive constraints, components, instances, variables, variants, and vector reconstruction are out of scope for the first Draft runtime.

## Assets

Image nodes reference `assets` by `assetId`.

Assets are served from:

```text
/api/draft-preview/{taskId}/assets/{assetId}.png
```

A completed task must not contain visible image nodes whose asset cannot be resolved.

## Z-Order

DSL export must preserve Draft graph z-order. Text should render above same-region shape/raster siblings.

Exporter must not reorder elements by Codia role names or legacy tree rules.

## Reference Image

The source PNG may be available as a hidden locked reference image for debugging. It must not be visible full-page backing.

If the renderer cannot represent hidden locked references cleanly, omit the reference from visible DSL and keep it only in task artifacts.

## Exporter Boundary

`draft/exportdsl` is mechanical conversion:

```text
layer kind -> DSL type
bbox -> layout
z -> child order/order metadata
text -> content
assetId -> imageFill
semanticTags/sourceRefs -> meta
```

It must not decide:

```text
whether a candidate should emit
whether text should be consumed by image
whether a raster should suppress background
whether a region is a Button/ListView/BottomNavigation
```
