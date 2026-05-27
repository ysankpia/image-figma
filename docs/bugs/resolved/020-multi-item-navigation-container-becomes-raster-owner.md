# Bug: Multi-Item Navigation Container Becomes Raster Owner

- 状态：resolved
- 创建日期：2026-05-28
- 影响范围：M29 model-first perception source compiler, M29.5 replay, Figma-visible bottom tab assets

## Summary

真实上传中，底部 tab 的文字和图标已被 M29.2/source compiler 识别，但 perception source compiler 又把整条底部导航容器编译成一个 `media_region / preserve_raster / image_replay`。M29.5 选择这个大图 replay 后，内部 tab icon 被 visible overlap suppression 压掉，Figma 里看到的是一条不可拆的大资产加部分文字。

## Reproduction

复现样本：

```text
backend/storage/uploads/task_4e22c557223a/original.png
```

旧 artifact 里可见：

```text
m292_perception_control_image_0001 bbox [30,1548,886,122]
internalRole = internal_control_raster_background
M29.5 image_replay suppressed bottom icon source objects
```

## Root Cause

`perception_source_compiler` 的 complex text-control raster fallback 把“单个复杂按钮/控件”与“多 item 导航容器”混成同一种 owner。

第一性原理上，底部 tab bar 是容器背景加重复 tab item，不是一个前景图片资产。它不能拥有内部 icon/text 的前景像素；否则 source ownership 会从多个可选前景对象退化成一个整条 raster owner。

## Fix

- 在 complex text-control raster fallback 前增加 multi-item text container 判定。
- 至少三个 OCR 文本在同一水平带内、横向跨度明显、列间距足够大时，该候选被视为重复 item 容器，不得编译成 `internal_control_raster_background`。
- 单个复杂长按钮仍可走 selectable raster crop，不受该规则影响。

该修复只发生在 M29 perception source compiler，不修改 public API、DSL schema、Renderer、Figma plugin protocol，也不恢复 legacy M29.6/promotion loop。

## Regression Guard

`tests/test_perception_source_compiler.py::test_multi_item_navigation_container_does_not_become_raster_owner` 覆盖：

- 多 item navigation 容器不生成整条 `media_region / internal_control_raster_background`。
- 内部 tab icon 仍进入 `icon_replay`。
- 内部 tab text 仍进入 `text_replay`。

## Validation Evidence

```bash
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py -q
# 84 passed
```

真实接口复跑：

```text
POST /api/upload-preview backend/storage/uploads/task_4e22c557223a/original.png
new task: task_622a38fd029e
```

验证结果：

```text
bottom region has no whole-tab m29_image at [30,1548,886,122]
bottom DSL includes 7 m29_symbol nodes at y >= 1559
bottom DSL includes 5 m29_text nodes at y >= 1616
ownership_conservation conflictCount = 0
```

## Prevention Notes

容器不是前景 owner。任何横向重复 item 容器、tab bar、toolbar 或 action row 都不能被当成单个 selectable raster asset 去压住内部 children。修这类问题时应先看 source ownership 和 M29.5 suppression，不要在 materializer、Renderer、plugin 里补节点，也不要按文案、颜色、文件名、task id 或固定坐标写规则。
