# M25 Region-Guided Business Icon Candidate Harness

- 状态：completed
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M25 补的是业务 icon 候选覆盖，不是可见回放，也不是 Codia 式全量拆层。真实学生端 smoke 已经说明 M20-M24 的结构依赖链只稳定覆盖了 header icon：M20 icon 数量长期为 0，M21 主要产生 header hints，M22 主要补裁 header nav/action，M23 只规划这些 header placement，M24 也只能回放这些 header icon。

所以 M25 绕开“必须先有完整业务组件结构”的假设，直接用 region-guided probes 在稳定业务区域裁高价值业务 icon PNG candidate。M25 默认开启，因为它不改变可见 DSL/Figma 输出；它只写报告、候选 PNG、overlay、SQLite 摘要和 DSL 顶层 meta。

M25 不新增可见 DSL 节点，不修改 DSL `assets`，不把 icon 放进画布，不做全图无边界 detection，不做 Codia 式全量拆层，不处理插画、头像、建筑或床位平面图复杂资产，不做 SVG/icon semantic recognition，不做图标库匹配，不接 AI，不引入 Pillow/OpenCV。

上传链路扩展为：

```text
M14 -> M15 -> M16 -> M17 -> M18 -> M19 -> M20 -> M21 -> M22 -> M23 -> M24 -> M25 -> save final DSL
```

## Key Changes

- 新增 `backend/app/icon_business_candidate.py`。
- 新增存储 `backend/storage/icon_business_candidates/{taskId}.json`。
- 新增业务 icon PNG 目录 `backend/storage/assets/{taskId}/icons_business/*.png`。
- 新增 debug overlay `backend/storage/assets/{taskId}/debug/icon_business_overlay.png`。
- 新增只读接口 `GET /api/tasks/{taskId}/icon-business-candidates`。
- 新增 SQLite 表 `icon_business_candidate_results`。
- 新增 asset role：`asset_icon_business_candidate`、`asset_icon_business_overlay`。
- 上传链路在 M24 输出 DSL 之后运行 M25；M25 failed/skipped 时 DSL 回退 M24/M23 输出。

配置默认值：

```bash
ICON_BUSINESS_CANDIDATE_ENABLED=true
ICON_BUSINESS_CANDIDATE_MAX_CANDIDATES=80
ICON_BUSINESS_CANDIDATE_MIN_CONFIDENCE=0.70
ICON_BUSINESS_CANDIDATE_MIN_SIZE=8
ICON_BUSINESS_CANDIDATE_MAX_SIZE=96
ICON_BUSINESS_CANDIDATE_FOREGROUND_DISTANCE=32
ICON_BUSINESS_CANDIDATE_RETRY_PADDING=12
ICON_BUSINESS_CANDIDATE_EDGE_CLIP_TOLERANCE=3
ICON_BUSINESS_CANDIDATE_OVERLAY_ENABLED=true
ICON_BUSINESS_BOTTOM_NAV_ENABLED=true
ICON_BUSINESS_PRIMARY_BUTTON_ENABLED=true
ICON_BUSINESS_SHORTCUT_CARD_ENABLED=true
ICON_BUSINESS_METRIC_CARD_ENABLED=true
ICON_BUSINESS_ROOM_CARD_ENABLED=true
ICON_BUSINESS_TRAILING_ENABLED=true
ICON_BUSINESS_TIP_INFO_ENABLED=true
```

## Contract

`IconBusinessCandidateDocument v0.1` 包含：

- `businessIcons`：成功裁出的业务 icon candidate，含 source、probeId、bbox、confidence、placementRole、assetId、assetPath、assetUrl 和 quality reasons。
- `blockedCandidates`：探测到但因重复、文字/cover 重叠、状态栏、排除区、线条/文字形态、尺寸或置信度门禁被阻断的候选。
- `businessOverlay`：调试 overlay，只画 bbox，不画文字标签。
- `warnings`：候选数量上限、overlay 写入失败等非致命问题。
- `meta`：businessIconCount、croppedBusinessIconCount、blockedCount、failedCropCount、sourceSummary 和 blockedReasonSummary。

M25 只允许追加 DSL 顶层 `meta`：

```json
{
  "qualityFlags": ["m25_icon_business_candidates"],
  "iconBusinessCandidateCount": 18,
  "iconBusinessCroppedAssetCount": 16,
  "iconBusinessBlockedCount": 2,
  "iconBusinessFailedCropCount": 0
}
```

M25 不允许修改 `root.children`、DSL `assets`、任何已有 element、M24 已有 visible nodes、fallback、candidate_text、visible_text_replacement 或 text_replacement_cover。

## Probe Rules

第一版实现这些 region probes：

- bottom nav：扫底部约 88%-97% 高度，按 3 tab 等分；宽屏时允许 4 tab。每个 item 上半区找 icon blob，排除 label 和 home indicator。
- primary button：在页面中下部找大蓝色横向按钮，第一版只裁右侧 white arrow；leading 区域容易把按钮文字笔画误裁成 icon，留到后续有更强结构证据后再做。
- shortcut/menu card：在首页中部两列功能入口区域裁浅蓝 tile + 蓝色 icon 候选。
- metric/stat card：在首页统计区裁楼、房、床类彩色 icon，排除数字和分割线。
- room card：在两列房间卡片左中区域裁门形/状态 icon，排除房号、虚线、文字和卡片边框。
- row/card trailing：在列表行右侧区域裁箭头或 check，排除状态文字。
- tip/info：在浅色提示框左侧裁 info/tip leading icon，排除提示文字和 bullet 点。

候选 source 到 placementRole 的映射固定：

```text
bottom_nav_region_icon        -> nav_icon
shortcut_tile_icon            -> tile_icon
shortcut_leading_icon         -> leading_icon
metric_card_icon              -> metric_icon
primary_button_leading_icon   -> button_leading_icon
primary_button_trailing_icon  -> button_trailing_icon
row_trailing_arrow            -> trailing_icon
row_trailing_check            -> trailing_icon
card_trailing_icon            -> trailing_icon
room_card_status_icon         -> status_icon
bed_status_icon               -> status_icon
tip_leading_icon              -> tip_leading_icon
info_leading_icon             -> info_leading_icon
unknown_business_icon         -> unknown_icon
```

## Quality Gates

M25 使用标准库 PNG 工具链：

```text
decode_png_pixels
-> estimate_background / color-specific blob detection
-> find_foreground_blobs
-> merge_gap_blobs
-> padded_bbox
-> edge clipped retry
-> crop_png
-> encode_rgb_png overlay
```

质量门禁：

- bbox 必须在 image bounds 内。
- bbox 宽高必须在 `ICON_BUSINESS_CANDIDATE_MIN_SIZE` 和 `ICON_BUSINESS_CANDIDATE_MAX_SIZE` 之间。
- 与 `visible_text_replacement`、`text_replacement_cover`、hidden `candidate_text` IoU 必须小于等于 0.10。
- 与 M20/M22/M23/M24 existing icon IoU 大于 0.50 时 blocked 为 duplicate。
- 状态栏、header title、banner/illustration 区域不裁。
- 文字笔画、横线、竖线、分割线、卡片边框不裁。
- confidence 必须大于等于 `ICON_BUSINESS_CANDIDATE_MIN_CONFIDENCE`。
- 总 candidate 数不超过 `ICON_BUSINESS_CANDIDATE_MAX_CANDIDATES`。

M25 的信心分数是规则分数，不是模型判断。它奖励 region probe 命中、前景对比、icon-like 尺寸、预期颜色和 source 几何；惩罚多 blob 模糊、线条/文字形态、重复和排除区。

## Failure Behavior

- `ICON_BUSINESS_CANDIDATE_ENABLED=false`：不生成 result，不追加 M25 meta，endpoint 返回 `ICON_BUSINESS_CANDIDATE_NOT_FOUND`。
- PNG decode unsupported：保存 skipped document，DSL 保持 M24/M23 输出，upload completed。
- 单个 crop 失败：该项 failed/blocked，document 仍可 completed。
- overlay 写入失败：document completed，`businessOverlay=null`，warnings 记录 `icon_business_overlay_write_failed`。
- document validation failed：保存 failed document，写 `error_logs(stage=icon_business_candidate)`，错误码 `ICON_BUSINESS_CANDIDATE_VALIDATION_FAILED`，DSL 回退 M24/M23 输出，upload completed。
- 未预期 exception：保存 failed document，写 `error_logs(stage=icon_business_candidate)`，错误码 `ICON_BUSINESS_CANDIDATE_FAILED`，DSL 回退 M24/M23 输出，upload completed。

## Validation

M25 校验：

- `version == "0.1"`，`taskId` 非空。
- business icon id 和 blocked candidate id 唯一。
- source、status、placementRole 枚举合法。
- candidate bbox 在 image bounds 内。
- candidate assetPath 文件存在。
- candidate 不与 M20/M22/M23/M24 existing icon 重复。
- candidate 不与 visible text、cover、candidate_text 冲突。
- candidate 不在 status/header/banner exclusion zone。
- overlay 若存在，assetPath 文件存在且 assetId 为 `asset_icon_business_overlay`。
- meta 计数和 summary 与 arrays 一致。
- DSL 只追加 M25 顶层 meta。

## Test Evidence

- 新增 `backend/tests/test_icon_business_candidate.py`。
- 覆盖默认开启生成 report/overlay/assets/DSL meta。
- 覆盖禁用配置不生成 result 且 DSL 保持 M23/M24 输出。
- 覆盖 endpoint missing task、missing result、missing file。
- 覆盖 synthetic probes 裁出 bottom nav、primary button trailing、shortcut tile、metric card、room card、row trailing。
- 覆盖与 M22 existing icon 重复 blocked、与 visible text overlap blocked。
- 覆盖 M25 只修改 DSL 顶层 meta，不改 root、children、assets。
- 覆盖生成的 business icon asset 可通过 `/api/assets/{assetId}` 和静态 URL 读取。

已跑：

```bash
cd backend
uv run pytest tests/test_icon_business_candidate.py -q
uv run pytest tests/test_icon_candidate.py tests/test_icon_coverage.py tests/test_icon_gap_candidate.py tests/test_icon_placement_plan.py tests/test_icon_visible_fallback.py tests/test_icon_business_candidate.py -q
```

七张学生端真实 smoke 已跑，summary 写入 ignored 调试目录：

```text
backend/storage/m25_smoke_after_leading_fix/m25_smoke_summary.json
```

结果：

```text
01 首页：M25 裁 6 个，来源 shortcut_tile_icon=3、metric_card_icon=3
02 楼层：M25 裁 3 个，来源 metric_card_icon=2、room_card_status_icon=1
03 房间：M25 裁 1 个，来源 metric_card_icon=1
04 床位：M25 裁 4 个，来源 bottom_nav_region_icon=3、room_card_status_icon=1
05 确认：M25 裁 3 个，来源 room_card_status_icon=1、info_leading_icon=2
06 结果：M25 裁 4 个，来源 primary_button_trailing_icon=1、shortcut_tile_icon=2、room_card_status_icon=1
07 登录：M25 裁 1 个，来源 metric_card_icon=1
```

七图总计裁出 22 个 business icon candidate：

```json
{
  "bottom_nav_region_icon": 3,
  "info_leading_icon": 2,
  "metric_card_icon": 7,
  "primary_button_trailing_icon": 1,
  "room_card_status_icon": 4,
  "shortcut_tile_icon": 5
}
```

Blocked 总计 65 个，均为 `edge_clipped_unresolved`。这说明当前 probe 窗口仍偏保守，很多贴边/半截风险项没有进入候选。人工抽查 overlay 后修正了一个真实问题：primary button leading 区域会把白色按钮文字横笔误裁为 icon，因此 M25 v0.1 禁止主动探测 primary leading，只保留 trailing arrow，并增加回归测试。

预期不是每张图强行有很多候选；稳定业务 icon 才裁，不为数量误裁文字、边框、状态栏、插画或床位平面图主体。

## Next

M26 应统一规划 M20/M22/M25 icon pool，重新做去重、fallback/slice/text collision 和 future visible replay readiness。M27 再做业务 icon visible replay。M25 本身不负责把 business icon 放进画布。
