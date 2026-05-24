# M29.2 Source-Level UI Physical Graph

- 状态：completed
- 创建日期：2026-05-22
- 负责人：未指定

## Goal

把 M29 Direct Replay 的问题前移到源头：先在 M29.2 判定每块像素的 UI 物理归属，再决定是否进入 flat DSL。

核心链路：

```text
PNG + OCR + M29 primitive evidence
-> M29.2 source-level UI physical graph
-> M29 direct replay DSL
-> Figma Compare 左侧肉眼验证
```

M29.2 只影响 `experiment/m29-direct-replay` 分支上的 `m29_direct` variant，不替换默认 `/api/tasks/{taskId}/dsl`，不修改 M30/M37/M38/M39 主线输出。

## Scope

包含：

- 新增 `m29_2_source_ui_physical_graph` 可选阶段。
- 输出 `m29_2/source_ui_physical_graph.json` 和 `source_ui_physical_graph_overlay.png`。
- 为 source object 记录 `visualKind`、`pixelOwner`、`replayDecision`、来源证据、confidence、reasons、risks。
- M29 Direct Replay 优先消费 M29.2 的 replay 决策。
- fallback 只擦除被 M29.2 判定为安全 replay 的 bbox。

不包含：

- 不接 ONNX、SAM、UIC 或新模型。
- 不做 Auto Layout、Figma Component/Instance、代码生成。
- 不为黑条、搜索框、轮播图写固定坐标、固定文本或固定样图规则。
- 不把 M29.2 写入主线 `/dsl`。

## Design

M29.2 第一版使用通用源头像素规则：

```text
editable_ui_text       -> editable_text      -> text_replay
preserve_raster_text   -> preserve_raster    -> preserve_in_parent_raster
media_region           -> preserve_raster    -> image_replay
raster_icon            -> raster_icon        -> icon_replay
control/card/separator -> shape_geometry     -> shape_replay
shadow_or_blur/unknown -> diagnostic_only    -> skip
```

核心策略：

- OCR 只作为证据。高置信、稳定局部背景、非 media 内部文字才 replay 为 editable text。
- 大面积、高纹理、高色彩的 M29 image/unknown 成为 media region；内部文字和碎片默认保留在 raster 中。
- 小 symbol fragments 先按空间邻近合并成 raster icon，再裁成一个 image node。
- shape 只允许稳定 UI 几何 replay：card/input/button 背景、badge、separator。
- 同 bbox 高 IoU 候选去重，优先级为 editable text、media、icon、shape、diagnostic。

## Acceptance

- `m29_2/source_ui_physical_graph.json` 和 overlay 在上传任务中生成。
- M29 direct report summary 包含 `m292SourcePhysicalGraph`。
- M29 direct visible nodes 由 M29.2 `replayDecision` 控制。
- `preserve_in_parent_raster` 不生成 DSL node，也不擦 fallback。
- 合并 icon 使用合并 bbox crop，不再只复制第一个 symbol fragment asset。
- M29.2 失败不阻断主线，M29 direct 可回退旧 replay 行为。

## Validation

```bash
cd backend
uv run pytest \
  tests/test_source_ui_physical_graph.py \
  tests/test_m29_direct_replay.py \
  tests/test_m30_upload_pipeline.py \
  tests/test_routes_tasks.py -q

uv run pytest -q

cd ..
pnpm run check
git diff --check
git status --short --branch
```

Manual smoke:

```text
start backend
open Figma plugin
click Generate Compare
inspect M29 Direct Replay left side:
  ordinary UI text editable
  art/banner/media text preserved as raster
  icons not fragmented into colored blocks
  fallback has no obvious ghost for replayed objects
```
