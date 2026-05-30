# DSL v0.1

DSL v0.1 是后端 M29 plan-driven materializer 和 Figma Renderer 之间的稳定合同。

```text
M29 trusted evidence
-> M29.5 replay plan
-> M29 plan-driven DSL
-> Renderer
-> Figma nodes
```

OCR、raw M29 evidence、M29.2/M29.3/M29.4/M29.5 reports、M29 materialization reports 和 storage artifacts 都不是 Renderer 输入。Renderer 只消费 DSL。

历史 M30 reports、M29 Direct reports、M31/M37/M38/M39/M39.1 downstream reports 也不是 Renderer 输入。

## Top-Level Shape

DSL 顶层必须包含：

```text
version
taskId
page
assets
root
meta
```

`version` 当前固定为 `"0.1"`。

## Element Types

v0.1 schema 支持：

```text
frame
group
text
shape
image
icon
line
```

当前 M29 upload path 只允许 materialize visible:

```text
frame
text
shape
image
line when already present in base DSL
```

M29 upload path does not need visible `icon` nodes. Raster icons are represented as `image` nodes with role `m29_symbol` because the current renderer path does not need a separate icon materialization type.

Every element needs:

```text
id
type
layout
```

Common optional fields:

```text
role
name
style
content
source
imageFill
children
meta
```

## Layout

v0.1 uses absolute pixel layout:

```text
x
y
width
height
```

M29 materialization must not infer Auto Layout, responsive constraints, Hug Content, Fill Container, or component structure from a PNG.

Although the schema supports nested `children`, the current M29 upload output remains absolute-layout root children. Any future nested DSL mode must be explicit and must translate child coordinates into parent-local coordinates before Renderer consumption.

## Assets

Image nodes reference `assets` through `assetId`.

M29 preview publishes local image assets under:

```text
storage/assets/{taskId}/m29/
/files/assets/{taskId}/m29/...
```

Asset URLs returned to the plugin must be fetchable by the Figma renderer.

## Fallback

Fallback is part of the contract, not a failure.

Current M29 DSL starts from deterministic fallback:

```text
root frame
  original_reference hidden
  full_image_fallback visible
  m29_shape*
  m29_image*
  m29_symbol*
  m29_text*
```

The materializer samples root/page background from source PNG instead of exposing a fixed light default as the visible page background.

Fallback cleanup is not a generic inpaint pass. It runs only when M29.5 plan items include a `fallback` cleanup target. If cleanup is not authorized, fallback pixels remain intact.

## Current Node Roles

Current visible roles:

```text
m29_text
m29_shape
m29_image
m29_symbol
fallback_region
original_reference
```

Historical roles such as `m30_text_member`, `m30_shape_candidate`, `m30_visual_asset`, `m30_composite_media_asset`, and `m29_direct_*` are not emitted by the current product runtime.

### Text

M29 text nodes come from M29.5 `text_replay` plan items backed by M29.2 `editable_text` ownership and OCR evidence.

Required trace in `meta`:

```json
{
  "m29PlanDrivenMaterialization": true,
  "sourceKind": "m29_5_replay_plan_item",
  "sourceM292ObjectId": "...",
  "sourceM295PlanItemId": "...",
  "sourceOcrBlockId": "...",
  "sourceBBox": [0, 0, 0, 0],
  "m292PixelOwner": "editable_text",
  "m295FinalReplayAction": "text_replay",
  "m295CleanupTargets": []
}
```

Text foreground color is sampled from source pixels around the text bbox. If sampling cannot confidently recover a style, the node remains traceable through report warnings/meta; it must not create a new owner decision.

### Shape

M29 shape nodes come from M29.5 `shape_replay` plan items backed by M29.2 `shape_geometry` ownership.

They should only be emitted when M29.2 has already accepted the source object as replay-safe. Fill is sampled from the source bbox. Radius may be written only when raw M29 geometry fit provides non-low-confidence radius evidence.

### Image And Raster/Icon Preservation

M29 image nodes come from M29.5 `image_replay` plan items backed by M29.2 `preserve_raster` ownership. These preserve complex media such as photos, avatars, charts, textured regions, and other areas that should not be redrawn as simple shape/text.

M29 symbol nodes use DSL `type=image` and role `m29_symbol`. They come from M29.5 `icon_replay` plan items backed by M29.2 `raster_icon` ownership.

Copied image asset text cleanup is allowed only when the corresponding M29.5 plan item includes a `copied_image_asset` cleanup target. The materializer cannot re-run contains/overlap policy on its own.

## Audit-Only Evidence

The following may appear in reports or DSL meta references, but must not become visible children:

```text
mixed_symbol_text_candidate
future_promotable_uncertain_symbol_candidate
candidate_for_future_uncertain_review
keep_mixed_symbol_text_conflict
text_owned_rejected_lineage audit examples
residual mixed review output
M29.1.3 classification output
M29.0.3.2 review output
M29.4 weak cluster role hints
M29.5 diagnostic_only / fallback_only / suppress_duplicate plan items
```

This rule is the main safety gate between evidence/audit world and Renderer-visible DSL.

## Mask Metadata

The schema still tolerates historical `meta.maskBBoxes` on image/fallback elements. Current M29 materialization does not rely on Renderer-side Boolean subtraction for cleanup; cleanup is executed in copied assets or fallback only when M29.5 authorizes it.

Renderer must ignore unknown `meta` fields and must not depend on historical M30/M39 labels.

## Codia Runtime DSL v0.2 Side Path

DSL v0.2 是 Go Codia-like compiler 的 Beta artifact，不替代当前 Python `/api/upload-preview` 产品主线。

```text
services/backend-go/cmd/codiacompile
-> codia_tree_ir.v1.json
-> codia_figma_like_tree.v1.json
-> codia_runtime.dsl.v0_2.json
-> renderCodiaRuntimeDesign
```

顶层固定：

```text
version = "0.2"
kind = "codia_runtime"
```

v0.2 节点使用 Codia runtime roles：

```text
Root
ViewGroup / ListView / ActionBar / StatusBar / BottomNavigation
Button / EditText / TextView / ImageView
Background / bg_Button / bg_EditText
```

v0.2 渲染类型只允许：

```text
frame / group / text / shape / image
```

v0.2 的职责只是把 Go Codia 已经裁决好的 tree 转成 Renderer 可消费的 runtime DSL。它不做 OCR、detector 调用、ownership 仲裁、control synthesis、parent assignment、golden diff 或样本规则。

第一版 v0.2 `ImageView` 允许没有可 fetch asset；Renderer 会用占位矩形继续渲染并记录 warning。后续如果 Go server 产出 crop asset，再把 `image.assetId` 或 `image.url` 接入同一个 DSL 0.2 合同。

## Removed Legacy DSL Paths

M30.2.2 removed the old pre-M29 upload chain. This stage removed M29 Direct compare and legacy M30 materialization from the product path. DSL patch, visible text replacement, component annotation, slice candidate, icon fallback replay, perception, SAM harness outputs, M29 Direct compare DSL, and M30 materialized DSL are historical and no longer part of the active upload DSL path.

Historical behavior remains in ADRs, archived plans, and git history.
