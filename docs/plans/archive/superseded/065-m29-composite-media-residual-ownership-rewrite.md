# 065 M29 Composite Media Ownership Rewrite

- 状态：superseded
- 创建日期：2026-05-26
- 负责人：Codex

归档说明：本计划代表 pre-model residual ownership rewrite 路线，已被 model-first perception compiler 主线取代。复合 media 的当前修复入口以 068 之后的 model-first source ownership、M29.5 replay 和 materializer 合同为准。

## Goal

把 M29 对复合 media 的模型从“完整大图保护”改成“残差图 ownership”。

当前 `media_region + preserve_raster + image_replay` 在复合 UI 图片里仍近似表示父图拥有整块像素。这个早期保守策略保护了复杂主视觉，但现在会阻止轮播图、登录海报、banner 内部的按钮、icon、pill、badge、circle control 成为真正可选对象，也会导致父图残影和双重 ownership。

本阶段的目标输出是：

```text
ResidualRaster(original - proven foreground)
+ editable text
+ selectable icons
+ selectable control shapes
+ selectable overlay badges
```

而不是：

```text
FullRaster + overlay nodes
```

## Scope

包含：

- 重定义 M29 内部合同：`preserve_raster` 对复合 UI media 表示 residual-capable media owner，不再表示内部全部不可拆。
- 在 M29.6 增加 foreground ownership claim proposal：button background、pill、badge、circle control、overlay control、icon、marker 等都必须有可审计 claim evidence。
- 把 evidence contract 从单纯 visible replay gate 扩展为 foreground ownership gate。
- 让 internal source promotion 把通过合同的 foreground claims 写回增强版 M29.2 source objects。
- 让 final M29.5 为 promoted foreground claims 生成 copied media residual cleanup 授权。
- 增强 materializer 对 M29.5 授权的 geometry-mask cleanup 执行。
- 升级 bridge fate trace，显示 foreground claim、promotion、final replay、residual cleanup 的第一阻断层。

不包含：

- 不修改 public API、DSL schema、Renderer、Figma plugin protocol。
- 不让 materializer、Renderer 或 plugin 发明 source ownership、visible nodes 或 cleanup 权限。
- 不把复杂主视觉、星空、波形、发光 S 等强行矢量化。
- 不引入 AI inpaint、SAM、remove.bg 或外部背景移除依赖。
- 不按品牌、可见文案、文件名、任务 id、固定坐标、固定 bbox、主题色或行业特化。

## Steps

1. **合同收口**：更新 bug、regression matrix 和主线文档，明确 full-raster ownership 是 composite UI media 的 legacy 行为，当前方向是 residual media ownership。
2. **Overlay control primitive detection**：在 M29.6/source 前段加入通用 overlay control shape 检测和 fragment merge，识别 pill、badge、circle、control background。
3. **Foreground claim proposal**：扩展 M29.6 report，给内部候选输出 `claimDecision`、`claimScore`、`maskKind`、`foregroundLayerEvidence`、`parentMediaSourceObjectId`。
4. **Evidence ownership gate**：evidence contract 输出 `allow_foreground_claim` / `report_only` / `reject`，并兼容现有 `allow_visible_replay` 读取路径，直到全部调用点迁移完成。
5. **Promotion rewrite**：internal source promotion 写回 `promotionSource=m29_6_foreground_claim` 的增强 M29.2 objects；control/pill/badge/circle 走 `shape_geometry / shape_replay`，icon 走 `raster_icon / icon_replay`。
6. **Residual cleanup contract**：M29.5 为 promoted foreground claims 生成 copied image asset cleanup targets，reason 为 `foreground_claim_removed_from_residual_media`，并携带 `foregroundClaimId`、`maskKind`。
7. **Materializer cleanup**：materializer 只执行 M29.5 授权；shape/pill/badge/circle 使用 geometry mask，icon 使用 alpha mask，fallback 为 bbox/ring fill。
8. **Trace and validation**：bridge fate 增加 claim/cleanup fields；跑 focused tests、真实 40 图验收集和 525 回归。

## Acceptance

- 复合 media 中已证明的 overlay controls 能成为 selectable nodes，包括 button background、pill badge、language selector、circle badge。
- 父 media 不再对 promoted foreground pixels 保持最终独占 ownership；M29.5 能授权 residual cleanup。
- cleanup 风险高时，visible replay 保留，只拒绝 copied media cleanup，并在 bridge fate 中标明 cleanup blocker。
- 复杂主视觉仍保留 raster residual，不被误拆成大量 shape/icon。
- bridge fate 能一眼说明 candidate 死在 M29.6、evidence、promotion、M29.5 cleanup 还是 materializer。
- 没有品牌、文案、文件名、路径、固定坐标、固定 bbox、主题色、行业特化。

## Validation

Focused tests:

```bash
cd backend
uv run pytest \
  tests/test_media_internal_decomposition.py \
  tests/test_m29_evidence_contract.py \
  tests/test_internal_source_promotion.py \
  tests/test_m29_replay_plan.py \
  tests/test_m29_plan_materializer.py \
  tests/test_ownership_conservation.py \
  tests/test_m29_bridge_fate_trace.py \
  -q
```

Real sample validation:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/测试/images \
  --poll-timeout 300
```

525 regression:

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py \
  --input-dir /Users/luhui/Downloads/525测试 \
  --poll-timeout 300
```

Static closeout:

```bash
git diff --check
git status --short --branch
```

## Notes

- `preserve_raster` 字段名短期保留，避免 public/runtime surface 大范围 rename；语义在 composite UI media 内部改为 residual-capable media owner。
- 第一版 residual cleanup 使用局部 ring fill / geometry mask，不做复杂 inpaint。
- 本计划是 063/064 之后的破坏性主线修正：不再继续在 full-raster protection 下叠补丁。
