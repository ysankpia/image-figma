# 072 M29 Model-First Selectable Raster Crop Fallback

- 状态：completed
- 创建日期：2026-05-27
- 负责人：Codex

## Goal

让模型已经发现、但暂时没有足够证据矢量化为 shape/icon 的低风险 UI 候选，仍然通过 M29.2 source ownership 进入 M29.5 和 materializer，成为 Figma 中可选、可拖、可调整层级的 raster crop。

当前目标不是 Codia 级全矢量化，而是先提高可选择性：明显的 UI foreground 不能因为暂时无法判定具体语义就停在 `report_only`。

## Scope

包含：

- 在 `backend/app/perception_source_compiler/` 增加低风险 selectable raster crop fallback。
- fallback 仍写成 M29.2 source object，再经 M29.3/M29.4/M29.5/materializer，不直接创建 DSL node。
- 更新 M29.5 overlap 规则，避免 fallback crop 被父 media 或同类 image replay 错误压掉。
- 增加 targeted pytest 覆盖低风险 fallback、文字重复风险、大面积 residual media 保护。
- 用 `/Users/luhui/Downloads/m29` 真实样本验证稳定性和 selectable 数量变化。

不包含：

- 不恢复旧 M29.6 -> transparent -> evidence -> promotion -> rerun loop。
- 不修改 public API、DSL schema、Renderer、Figma plugin protocol。
- 不把 fallback 猜成 button、icon、component 或 Auto Layout。
- 不做 OCR 修正、品牌/文案/文件名/坐标特化。
- 不在 materializer、Renderer 或 plugin 里发明 source ownership。

## Contract

低风险 fallback 的本质是：

```text
model candidate
-> perception source compiler writes selectable_foreground_raster source object
-> M29.5 authorizes image_replay
-> materializer crops source pixels into m29_image
```

它必须满足：

```text
not huge residual media
not near-equal existing replay owner
not mostly OCR text
not excessive text overlap
bounded area ratio
non-trivial local visual signal
```

失败时仍保留 `perception_fate_trace` 的 `report_only` 阻断原因。

## Steps

1. 补 source compiler fallback source object 和 options。
2. 补 M29.5 overlap 保留规则，允许 perception foreground crop over parent residual media。
3. 补 regression tests 和 regression matrix。
4. 跑 targeted pytest。
5. 跑 16 张真实样本 batch，比较 compiled source object / materialized visible node / ownership conflict。
6. 收口文档并阶段提交。

## Acceptance

- 低风险未知模型候选可以成为 selectable raster crop。
- 大图/主视觉 residual media 仍不会被 fallback 吞掉。
- OCR 文本候选或高文字重叠候选不会变成重复 raster crop。
- fallback 不授权 copied image cleanup；cleanup 仍只能来自 M29.5 的既有安全路径。
- `/Users/luhui/Downloads/m29` 16 张真实图无 crash、无 missing artifact、无 ownership conflict。
- 硬图中 `insufficient_ownership_evidence` 阻断减少，compiled/materialized 数量上升。

## Validation

```bash
cd backend
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_m29_perception_fate_trace.py -q
UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/m29 \
  --poll-timeout 300
git diff --check
git status --short --branch
```

## Notes

新增阈值必须是通用尺度/风险约束，不得绑定样本、路径、品牌、文案、主题色、固定 bbox 或固定坐标。

## Result

实现完成：

- 低风险未知模型候选可编译为 `internal_selectable_raster_crop`，作为 `media_region / preserve_raster / image_replay` 进入 M29.5。
- selectable raster crop 不授权 copied-image cleanup。
- selectable raster crop over parent residual media 在 M29.5 overlap 和 ownership conservation 中可解释。
- selectable raster crop 不能压掉更具体的 icon/shape replay。

验证结果：

```text
uv run pytest tests/test_perception_source_compiler.py tests/test_m29_replay_plan.py tests/test_ownership_conservation.py tests/test_m29_perception_fate_trace.py -q
83 passed

UPLOAD_PREVIEW_RUNTIME_MODE=interactive uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29 --poll-timeout 300
16 completed, 0 failed, 0 backend crash, 0 missing artifacts, 0 ownership conflicts
compiledSourceObjectCount: 170 -> 225
materializedVisibleNodeCount: 1939 -> 1990
plannedIconReplayCount: 430 -> 430
hard image compiledCount: 8 -> 9
```
