# Bug: Media-contained long control labels are preserved as raster text

- 状态：resolved
- 创建日期：2026-05-26
- 修复日期：2026-05-26
- 影响范围：M29.2 source ownership, M29.5 replay plan, copied media cleanup authorization

## Summary

最新登录页样例中，`Continue with Google` 和 `Continue with Snapchat` 已被 OCR 和 raw M29 正确识别，但最终 Figma/DSL 没有生成可编辑文本节点，只保留在父级 raster image 内。`Continue with Facebook` 能生成文本节点，导致同一组登录方式处理不一致。

这不是 Figma 插件或 Renderer 问题。丢失发生在 M29.2 source ownership：长一点的 OCR label 被 `large_display_text_inside_media` 规则归为 `preserve_raster_text`，因此 M29.5 只能输出 `preserve_in_parent_raster`，不会 materialize 成 `m29_text`。

## Reproduction

原任务：

```text
task_4ad6622f71b9
```

用户提供的 Figma 节点：

```text
fileKey=NQoqMWv8BUbqtNq2xvlrJH
nodeId=3451:1953
```

关键证据：

```text
ocr/ocr.json:
  ocr_text_003 = Continue with Google
  ocr_text_004 = Continue with Facebook
  ocr_text_005 = Continue with Snapchat

m29/nodes.json:
  text_003 = Continue with Google
  text_004 = Continue with Facebook
  text_005 = Continue with Snapchat

old m29_2/source_ui_physical_graph.json:
  ocr_text_003 -> preserve_raster_text / preserve_in_parent_raster
  ocr_text_004 -> editable_ui_text / text_replay
  ocr_text_005 -> preserve_raster_text / preserve_in_parent_raster

old materialized_design/design.dsl.json:
  Continue with Facebook exists
  Continue with Google missing
  Continue with Snapchat missing
```

Figma MCP `get_design_context` confirmed the rendered Google button was present as part of `Fallback Full Image` / `M29 Image`, but there was no editable `Continue with Google` text node.

## Root Cause

`backend/app/source_ui_physical_graph/text.py` used an absolute and page-width-sensitive display-text gate:

```text
height >= media_display_text_min_height
or width >= image_width * media_display_text_min_width_ratio
   and height >= media_display_text_min_height * 0.75
```

That rule was too blunt. In a tall composite media block, ordinary control labels can have OCR bboxes around 36-40 px high and wide text lines. They are still UI labels, not poster/display art text.

The bad boundary was visible in this sample:

```text
Google label bbox height = 36, width = 278 -> preserved
Facebook label bbox height = 27, width = 300 -> editable
Snapchat label bbox height = 35, width = 299 -> preserved
```

The difference was mostly OCR bbox height, not a real source-ownership difference.

## Fix

M29.2 display-text classification now uses the containing media scale. Text inside media is preserved as display/art text only when it is large relative to the media, not merely because it is a long OCR line on a large page.

New decision shape:

```text
contained by media
+ absolute text height floor
+ relative-to-media height or width evidence
=> preserve_raster_text

otherwise:
  high-confidence OCR text remains editable_ui_text
```

This keeps small/ordinary control labels editable while preserving true large display text in smaller or poster-like media.

No logic keys on literal text, provider names, file names, task ids, fixed coordinates, theme colors, or a single screenshot.

## Regression Guard

Added:

```text
backend/tests/test_source_ui_physical_graph.py::test_long_control_label_inside_large_media_remains_editable_text
backend/tests/test_source_ui_physical_graph.py::test_large_display_text_inside_media_is_still_preserved_by_relative_scale
```

The first test covers the failure shape: a long control label fully contained inside a large media region must stay `editable_ui_text / text_replay`.

The second test is the negative guard: true large display text inside media remains `preserve_raster_text / preserve_in_parent_raster`.

## Validation Evidence

Targeted pytest:

```bash
cd backend
uv run pytest tests/test_source_ui_physical_graph.py -q
```

Result:

```text
24 passed
```

Real upload-preview rerun from the latest task source PNG:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir tmp/single-google-check/input \
  --output-dir tmp/single-google-check/run \
  --poll-timeout 300
```

Result:

```text
taskId = task_207be171abb8
status = completed
visibleTextCount = 9
ownershipConflictCount = 0
totalVisibleOwnershipOverlapConflicts = 0
```

Final DSL now contains:

```text
Continue with Google
Continue with Facebook
Continue with Snapchat
Continue with Phone
```

M29.2 summary after fix:

```text
editableTextCount = 9
preservedRasterTextCount = 0
```

M29.5 summary after fix:

```text
plannedTextReplayCount = 9
copiedImageAssetCleanupTargetCount = 5
visibleOverlapSuppressedCount = 1
warningCount = 0
```

## Prevention Notes

Do not judge editability of media-contained OCR text from text bbox height alone. The decision must consider relative scale against the containing media and preserve true display/art text while allowing ordinary UI labels.
