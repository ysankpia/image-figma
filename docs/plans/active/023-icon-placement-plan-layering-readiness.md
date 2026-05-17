# M23 Icon Placement Plan And Layering Readiness Harness

- 状态：completed
- 创建日期：2026-05-17
- 负责人：Codex

## Summary

M23 在 M22 region-guided icon gap candidate 后新增 icon placement plan 合同层。它消费 M20 icon candidates、M22 gap icon candidates、M19 asset slice candidates 和当前 DSL collision facts，把已有 icon PNG 候选统一成 placement plan。

M23 不裁新 icon，也不把 icon 放进 Figma 可见画布。它只判断每个 icon 后续进入可见分层前的状态：`ready_for_visible_icon`、`needs_fallback_mask`、`needs_slice_coordination`、`needs_fallback_coordination`、`review_required`、`blocked` 或 `deduped`。

M23 不改变 Figma 可见输出，不新增可见 DSL 节点，不修改任何已有 DSL element，不修改 DSL `assets` 数组，不删除 fallback，不做全局 icon detection，不做 Codia 式全量可拖动图层，不做 SVG/icon semantic recognition，不做图标库匹配，不接 AI，不引入 Pillow/OpenCV。

## Key Changes

- 新增 `backend/app/icon_placement_plan.py`。
- 新增存储 `backend/storage/icon_placement_plans/{taskId}.json`。
- 新增 debug overlay `backend/storage/assets/{taskId}/debug/icon_placement_overlay.png`。
- 新增只读接口 `GET /api/tasks/{taskId}/icon-placement-plan`。
- 新增 SQLite 表 `icon_placement_plan_results`。
- overlay asset 写入 `assets` 表，role 为 `asset_icon_placement_overlay`。

M23 默认开启：

```bash
ICON_PLACEMENT_PLAN_ENABLED=true
ICON_PLACEMENT_PLAN_OVERLAY_ENABLED=true
ICON_PLACEMENT_PLAN_DEDUP_IOU=0.50
ICON_PLACEMENT_PLAN_TEXT_OVERLAP_IOU=0.10
ICON_PLACEMENT_PLAN_SLICE_OVERLAP_IOU=0.50
ICON_PLACEMENT_PLAN_MAX_PLACEMENTS=128
```

## Contract

`IconPlacementPlanDocument v0.1` 包含：

- `placements`：保留后的 icon placement plan，包含 source stage、source icon、asset、bbox、decision、collision、futureDslNodeHint 和 reasons。
- `dedupedIcons`：因 M20/M22 重复而被丢弃的 icon。
- `blockedIcons`：资产缺失、bbox/引用非法或与 text/cover/candidate_text 冲突的 icon。
- `placementOverlay`：按 decision 着色的 bbox 调试图。
- `meta`：placement、ready、fallback mask、slice coordination、fallback coordination、review、blocked、deduped 统计。

M23 只追加 DSL 顶层 meta：

```json
{
  "qualityFlags": ["m23_icon_placement_plan"],
  "iconPlacementPlanCount": 34,
  "iconPlacementReadyCount": 0,
  "iconPlacementNeedsFallbackMaskCount": 28,
  "iconPlacementNeedsSliceCoordinationCount": 4,
  "iconPlacementNeedsFallbackCoordinationCount": 0,
  "iconPlacementReviewRequiredCount": 0,
  "iconPlacementBlockedCount": 2,
  "iconPlacementDedupedCount": 6
}
```

`futureDslNodeHint` 只存在于 report，不写入 DSL，不是 Renderer 输入。

## Placement Rules

- M20 `icons[] status == candidate` 和 M22 `gapIcons[] status == candidate` 合并为同一个 icon pool。
- bbox IoU >= `ICON_PLACEMENT_PLAN_DEDUP_IOU` 或中心点/尺寸高度相近时判定重复；保留 bbox 更完整者，其次保留更高 confidence，其次优先 M20。header/trailing 等 M20 不覆盖来源允许优先 M22。
- 与 `visible_text_replacement`、`text_replacement_cover` 或 hidden `candidate_text` IoU 超过 `ICON_PLACEMENT_PLAN_TEXT_OVERLAP_IOU` 时 blocked。
- 位于 fallback region 内时为 `needs_fallback_mask`，因为直接放回会与 fallback 原图重复。
- 不在 fallback 内但落入 M19 slice candidate 时为 `needs_slice_coordination`。
- 来源弱或 role 不明确时为 `review_required`。
- 无 fallback、slice、text、cover、candidate_text 冲突且引用完整时为 `ready_for_visible_icon`。

overlay 颜色：

```text
绿色：ready_for_visible_icon
紫色：needs_fallback_mask
蓝色：needs_slice_coordination
橙色：needs_fallback_coordination
黄色：review_required
红色：blocked
灰色：deduped
```

## Validation

M23 校验：

- document version、taskId、id 唯一性。
- sourceStage/sourceIconId 必须指向 M20 或 M22 的真实 candidate。
- candidate assetPath 必须存在。
- bbox 必须在 image bounds 内。
- component/text/binding 引用必须可解析，允许为空。
- decision/status/placementRole/risk 枚举合法。
- dedupedIcons.keptPlacementId 必须存在。
- blockedIcons 必须对应 source icon。
- placementOverlay 若存在，文件必须存在。
- meta 计数与 placements/dedupedIcons/blockedIcons 一致。
- M23 不新增 root children，不修改 DSL assets，不修改任何 element 字段。

validation failed 时保存 failed document，写 `error_logs(stage=icon_placement_plan)`，错误码 `ICON_PLACEMENT_PLAN_VALIDATION_FAILED`，DSL 回退 M22 输出，上传仍 completed。

## Test Evidence

- 新增 `backend/tests/test_icon_placement_plan.py`。
- 覆盖默认上传、禁用、endpoint not found、M20/M22 去重、fallback/slice/text decision、futureDslNodeHint 不写入 DSL、overlay asset。
- 已跑：

```bash
cd backend
uv run pytest tests/test_icon_candidate.py tests/test_icon_coverage.py tests/test_icon_gap_candidate.py tests/test_icon_placement_plan.py tests/test_upload_flow.py -q
```
