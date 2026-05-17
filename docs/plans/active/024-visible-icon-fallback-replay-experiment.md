# M24 Visible Icon Fallback Replay Experiment Harness

- 状态：completed
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M24 是第一个会改变可见 DSL/Figma 输出的 icon 阶段。它不继续找 icon，不补漏裁，不处理 M21 missed hints 或 M22 blocked hints；它只消费 M23 `icon placement plan`，把已经由 M20/M22 裁出、且 M23 判定为 `needs_fallback_mask` 的低风险 icon 做小范围可见回放实验。

M24 默认关闭：

```bash
ICON_VISIBLE_FALLBACK_ENABLED=false
```

显式开启后，M24 会选择允许角色内的低风险 placement，先 append `icon_fallback_cover` shape 节点遮住 fallback 原图对应位置，再 append `visible_icon_fallback` image 节点，并只把实际使用的 icon asset 追加进 DSL `assets`。

M24 不做全量拆 icon，不做 Codia 式全量可拖动图层，不做全局 icon detection，不做新的 icon crop，不做透明 PNG/SVG/icon semantic recognition，不做图标库替换，不接 AI，不引入 Pillow/OpenCV。没拆出来的 icon 仍留给 M25/M26 继续优化。

## Key Changes

- 新增 `backend/app/icon_visible_fallback.py`。
- 新增存储 `backend/storage/icon_visible_fallbacks/{taskId}.json`。
- 新增 debug overlay `backend/storage/assets/{taskId}/debug/icon_visible_fallback_overlay.png`。
- 新增只读接口 `GET /api/tasks/{taskId}/icon-visible-fallback`。
- 新增 SQLite 表 `icon_visible_fallback_results`。
- overlay asset 写入 `assets` 表，role 为 `asset_icon_visible_fallback_overlay`。
- Renderer 增加 M24 shape cover + image node 的回归测试。

配置：

```bash
ICON_VISIBLE_FALLBACK_ENABLED=false
ICON_VISIBLE_FALLBACK_MAX_PLACEMENTS=12
ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE=0.85
ICON_VISIBLE_FALLBACK_MASK_PADDING=2
ICON_VISIBLE_FALLBACK_MAX_MASK_SIZE=96
ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE=28
ICON_VISIBLE_FALLBACK_ALLOWED_ROLES=nav_icon,header_nav_icon,header_action_icon,leading_icon
ICON_VISIBLE_FALLBACK_OVERLAY_ENABLED=true
```

## Contract

`IconVisibleFallbackDocument v0.1` 包含：

- `visibleIcons`：实际 applied 的可见 icon fallback 项，记录 placement、asset、bbox、coverNodeId、iconNodeId、mask 和 quality reasons。
- `blockedPlacements`：M23 选中但因角色、置信度、asset、bbox、文字/cover/candidate_text 冲突或背景不稳定而阻断的 placement。
- `visibleFallbackOverlay`：可见回放实验 overlay，只作为调试资产。
- `meta`：selected/applied/blocked/skipped、roleSummary 和 blockedReasonSummary。

M24 允许的 DSL 改动只有：

- 追加 DSL 顶层 `meta`。
- 追加实际 applied icon 的 asset 到 DSL `assets`，且不重复追加。
- 向 `root.children` append `icon_fallback_cover` shape 节点。
- 向 `root.children` append `visible_icon_fallback` image 节点。

节点顺序固定为 cover 在前、icon 在后。

## Selection Rules

placement 必须满足：

- M23 document status 为 `completed`。
- `decision == "needs_fallback_mask"`。
- `status == "planned"`。
- sourceStage 为 `m20` 或 `m22`。
- assetId、assetPath、assetUrl 存在，且 assetPath 文件存在。
- bbox 在 image bounds 内。
- confidence >= `ICON_VISIBLE_FALLBACK_MIN_CONFIDENCE`。
- placementRole 在 allowlist 内：`nav_icon`、`header_nav_icon`、`header_action_icon`、`leading_icon`。
- bbox 和 mask bbox 不与 `visible_text_replacement`、`text_replacement_cover`、hidden `candidate_text` IoU > 0.10。
- mask bbox 最大边不超过 `ICON_VISIBLE_FALLBACK_MAX_MASK_SIZE`。

优先级固定为：

```text
nav_icon
> header_nav_icon
> header_action_icon
> leading_icon
```

M24 用 cover bbox 外围采样背景色，只有 `max_channel_delta <= ICON_VISIBLE_FALLBACK_SOLID_BG_TOLERANCE` 时才允许 solid shape cover。复杂背景、渐变、图片或不稳定采样全部 blocked，第一版不做 patch PNG、透明抠图或 inpainting。

## Validation

M24 校验：

- document version、taskId、id 唯一性。
- visibleIcons 必须引用真实 M23 placement，sourceStage/sourceIconId/assetId 必须一致。
- assetPath 必须存在。
- bbox 和 mask bbox 必须在 image bounds 内。
- coverNodeId/iconNodeId 必须存在于最终 DSL。
- cover node 必须是 `shape`，role 为 `icon_fallback_cover`，`style.fill` 为 `#RRGGBB`。
- icon node 必须是 `image`，role 为 `visible_icon_fallback`，source.assetId 指向已追加 DSL asset，imageFill.mode 为 `fit`。
- DSL assets 内 assetId 不重复。
- 新增 cover/icon 不遮挡 visible text、text replacement cover 或 hidden candidate_text。
- meta 计数和 summary 与 arrays 一致。
- overlay 若存在，文件必须存在。

validation failed 时保存 failed document，写 `error_logs(stage=icon_visible_fallback)`，错误码 `ICON_VISIBLE_FALLBACK_VALIDATION_FAILED`，DSL 回退 M23 输出，上传仍 completed。

## Test Evidence

- 新增 `backend/tests/test_icon_visible_fallback.py`。
- Renderer 增加 `visible_icon_fallback` image 和 `icon_fallback_cover` shape 回归。
- 覆盖默认关闭、开启上传、endpoint not found、角色/置信度/text/background blocked、DSL append 回归安全、overlay asset API。
- 已跑：

```bash
cd backend
uv run pytest tests/test_icon_visible_fallback.py tests/test_icon_placement_plan.py
pnpm --filter @image-figma/image-to-figma-renderer test -- packages/image-to-figma-renderer/tests/renderDesign.test.ts
uv run pytest
pnpm run check
git diff --check
```

七张学生端真实 smoke 已跑两轮：

- `ICON_VISIBLE_FALLBACK_ENABLED=false`：7 张图均不生成 M24 result，DSL qualityFlags 停在 `m23_icon_placement_plan`，新增 visible icon/cover/icon asset 计数均为 0。
- `ICON_VISIBLE_FALLBACK_ENABLED=true`：01 applied 1 个 header action icon；02、03、04 各 applied 2 个 header nav/action icon；05、06、07 因 M23 placementCount 为 0，M24 completed 但 selected/applied 均为 0。
- overlay 已生成在 `backend/storage/m24_smoke_enabled/assets/{taskId}/debug/icon_visible_fallback_overlay.png`。storage 为 ignored 调试产物，不进入提交。
