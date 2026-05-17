# M22 Region-Guided Icon Gap Candidate Harness

- 状态：completed
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M22 在 M21 icon coverage audit 后新增 region-guided icon gap candidate 合同层。它消费 M21 `missedIconHints`、M20 icon candidates、M15-M17 结构索引和原始 PNG 像素，把可靠的 header、trailing、bottom nav、shortcut 等漏裁图标区域补裁成本地 PNG 候选资产。

M22 不是可见替换阶段。它不改变 Figma 可见输出，不新增可见 DSL 节点，不修改任何已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不做全局 icon detection，不做 Codia 式全量可拖动图层，不做 SVG/icon semantic recognition，不做图标库匹配，不接 AI，不引入 Pillow/OpenCV。

## Key Changes

- 新增 `backend/app/icon_gap_candidate.py`。
- 新增存储 `backend/storage/icon_gap_candidates/{taskId}.json`。
- 新增本地候选资产 `backend/storage/assets/{taskId}/icons_gap/*.png`。
- 新增 debug overlay `backend/storage/assets/{taskId}/debug/icon_gap_overlay.png`。
- 新增只读接口 `GET /api/tasks/{taskId}/icon-gap-candidates`。
- 新增 SQLite 表 `icon_gap_candidate_results`。
- gap icon asset 写入 `assets` 表，role 为 `asset_icon_gap_candidate`。
- overlay asset 写入 `assets` 表，role 为 `asset_icon_gap_overlay`。

M22 默认开启：

```bash
ICON_GAP_CANDIDATE_ENABLED=true
ICON_GAP_CANDIDATE_MIN_CONFIDENCE=0.72
ICON_GAP_CANDIDATE_MAX_CANDIDATES=48
ICON_GAP_CANDIDATE_MIN_SIZE=8
ICON_GAP_CANDIDATE_MAX_SIZE=80
ICON_GAP_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_GAP_CANDIDATE_RETRY_PADDING=12
ICON_GAP_CANDIDATE_EDGE_CLIP_TOLERANCE=3
ICON_GAP_CANDIDATE_OVERLAY_ENABLED=true
```

## Contract

`IconGapCandidateDocument v0.1` 包含：

- `gapIcons`：成功补裁或单个 crop failed 的 gap icon candidate。
- `blockedHints`：不安全、不可靠或被文本/已有 M20 icon 覆盖的 hint。
- `gapOverlay`：彩色 bbox 调试图。
- `meta`：`gapIconCount`、`croppedGapIconCount`、`blockedCount`、`failedCropCount`、`sourceSummary`、`blockedReasonSummary`。

允许 source：

```text
header_left_nav_icon
header_right_action_icon
row_trailing_icon
button_trailing_icon
card_trailing_icon
bottom_nav_missing_icon
shortcut_missing_icon
field_missing_icon
```

M21 hint 映射：

```text
header_left_visual_hint        -> header_left_nav_icon
header_right_visual_hint       -> header_right_action_icon
right_arrow_hint               -> row_trailing_icon
card_trailing_icon_hint        -> card_trailing_icon
bottom_nav_missing_icon_hint   -> bottom_nav_missing_icon
shortcut_missing_icon_hint     -> shortcut_missing_icon
field_icon_hint                -> field_missing_icon
low_confidence_icon_like_blob  -> 默认不裁
```

DSL 只追加顶层 meta：

```json
{
  "qualityFlags": ["m22_icon_gap_candidates"],
  "iconGapCandidateCount": 6,
  "iconGapCroppedAssetCount": 5,
  "iconGapBlockedCount": 1,
  "iconGapFailedCropCount": 0
}
```

## Candidate Rules

- M22 优先裁 M21 `missedIconHints`，只补少量高价值主动 probe。
- 主动 probe 限定在 header 左右 action、bottom nav label 上方缺口、card/row/button trailing 区域和 shortcut leading 缺口。
- 顶部右侧小程序胶囊只裁内部 dots/circle 这类小 blob，不裁整块胶囊。
- 与 M20 icon IoU > 0.50 的区域不重复裁。
- 与 visible text、text replacement cover 或 hidden candidate_text IoU > 0.10 的区域不裁。
- 状态栏时间、电量、信号区域不裁。
- 字段页 `field_missing_icon` 保守处理，文字笔画、细条和比例异常区域只写 blocked。
- bbox 贴 search window 边界时先扩大窗口重试；仍贴边则 blocked。
- 多 blob 可合并，但合并后仍必须 icon-like。

## Validation

M22 校验：

- document version、taskId、id 唯一性。
- source/status 枚举。
- `sourceHintId` 若存在必须来自 M21 missedIconHints。
- candidate bbox 在 image bounds 内。
- candidate assetPath 文件存在。
- 不与 M20 icon、visible text、cover、candidate_text 超阈值重叠。
- overlay 若存在，文件必须存在。
- meta 计数与数组一致。

validation failed 时保存 failed document，写 `error_logs(stage=icon_gap_candidate)`，错误码 `ICON_GAP_CANDIDATE_VALIDATION_FAILED`，DSL 回退 M21 输出，上传仍 completed。

## Test Evidence

- 新增 `backend/tests/test_icon_gap_candidate.py`。
- 覆盖默认上传、禁用、endpoint not found、hint 升级裁剪、文本/hidden candidate_text 防误裁、field text-stroke blocked、overlay asset、DSL meta-only 回归。
- 已跑：

```bash
cd backend
uv run pytest tests/test_icon_candidate.py tests/test_icon_coverage.py tests/test_icon_gap_candidate.py tests/test_upload_flow.py -q
```

结果：`42 passed`。

## Next

M23 应该基于 M20/M22 的 icon PNG 和 M21 readiness 做 icon placement plan，决定哪些 icon 未来能进入可见 DSL、哪些必须等 partial fallback replacement。M23 仍不应直接做全量可拖动 Codia 式替换；真正 visible icon fallback experiment 应放在 M24+。
