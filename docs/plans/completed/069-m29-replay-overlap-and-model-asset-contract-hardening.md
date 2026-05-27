# 069 M29 Replay Overlap And Model Asset Contract Hardening

- 状态：completed
- 创建日期：2026-05-28
- 完成日期：2026-05-28
- 负责人：Codex

## Goal

修复 Claude 审核中确认有代码事实支撑的 model-first 主链问题：`perception_model_foreground_claim` 的透明资产消费缺口，以及 M29.5 visible overlap suppression 把真实相邻前景误判为 duplicate 的风险。

本计划修 source-chain 合同，不做单样本调参，不改 public API、DSL schema、Renderer、Figma plugin protocol，也不恢复 legacy `M29.6 -> transparent -> evidence -> promotion -> rerun` 默认主链。

## Scope

包含：

- `plan_materializer` 只消费已有 `transparentAssetPath`，补齐 `perception_model_foreground_claim` provenance。
- `m29_replay_plan` 将 same-action overlap suppression 从单一 `0.20` containment 改为 role/relation/source-evidence aware duplicate contract。
- 增加相邻 icon/marker、near_equal duplicate、parent media child foreground、text/icon overlap 的回归测试。
- 记录 bug 根因和验证证据。

不包含：

- 不改 public DSL/API/Renderer/plugin。
- 不恢复 M29.6/transparent/evidence/promotion loop。
- 不在 materializer 发明 source owner、cleanup 权限或新可见节点。
- 不按图片、文案、颜色、坐标、文件名、task id 写特化规则。
- 不在本提交内清理所有 legacy 模块；active plans 归档单独提交。

## Steps

1. 提交 Claude review/prompt 输入，保持文档输入与 runtime 修复隔离。
2. 修 `transparent_asset_path_for()` 的 source provenance 合同，并补 materializer 测试。
3. 重写 M29.5 same-action overlap duplicate 判定，保留 near_equal 强 duplicate，避免相邻小前景被普通 overlap suppress。
4. 补 focused replay/materializer/ownership/fate trace 回归。
5. 跑 `/Users/luhui/Downloads/m29` 代表集和硬样本 artifact inspection。
6. 通过后提交 runtime 修复。
7. 单独处理 stale active plans 归档。

## Acceptance

- `perception_model_foreground_claim + transparentAssetPath` 使用已存在透明资产；缺 path 或文件不存在时仍 fallback crop。
- 相邻小 icon/marker/status/table foreground 即使有 20-35% overlap，也不会仅因普通 overlap 被 suppress。
- near_equal 或高 IoU duplicate 仍被 suppress。
- parent media/control raster crop 不 suppress 内部 foreground icon。
- text-owned fragment 仍可 suppress；promoted/model foreground icon + label 不被误删。
- 16 张代表集 completed、backend crash 0、ownership conflict 0、visible node count 不系统性下降。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py -q

UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300

git diff --check
git status --short --branch
```

硬样本检查：

```text
backend/storage/uploads/task_4e22c557223a/original.png
```

验收：底部 tab 不出现整条 raster owner 压住 children；底部 icon/text 仍有 `icon_replay` / `text_replay` 和 DSL 节点。

## Completion Evidence

Targeted regression:

```bash
cd backend
uv run pytest tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py -q
```

Result:

```text
89 passed
```

Representative model-first batch:

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300
```

Evidence ledger:

```text
backend/tmp/validation/upload_preview_batch_20260527_180306_969454_35407/upload_preview_batch_validation.json
```

Summary:

```json
{
  "inputCount": 16,
  "completedTaskCount": 16,
  "failedTaskCount": 0,
  "backendCrashCount": 0,
  "totalVisibleReplayClaimCount": 2196,
  "totalVisibleOwnershipOverlapConflicts": 0,
  "totalMaterializedVisibleNodeCount": 2196,
  "ownershipConflictTypeCounts": {}
}
```

Hard regression sample:

```bash
cd backend
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Volumes/WorkDrive/Code/github.com/LuQing-Studio/python/image-figma/backend/storage/uploads/task_4e22c557223a \
  --poll-timeout 300
```

Evidence ledger:

```text
backend/tmp/validation/upload_preview_batch_20260527_181106_297892_45198/upload_preview_batch_validation.json
```

Summary:

```json
{
  "inputCount": 1,
  "completedTaskCount": 1,
  "backendCrashCount": 0,
  "totalVisibleReplayClaimCount": 77,
  "totalVisibleOwnershipOverlapConflicts": 0,
  "totalPlannedShapeReplayCount": 10,
  "totalPlannedIconReplayCount": 35,
  "totalMaterializedVisibleNodeCount": 77
}
```

## Notes

第一性原理：duplicate suppression 判断的是“两个 source object 是否争夺同一个视觉实体”，不是“bbox overlap 是否超过某个单一常数”。阈值只能表达通用几何合同，不能替代 source provenance、role compatibility、relation type 和 ownership intent。
