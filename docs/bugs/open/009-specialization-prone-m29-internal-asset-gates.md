# Bug: M29 internal asset chain 存在特化倾向的证据门控

- 状态：open
- 创建日期：2026-05-25
- 影响范围：M29.6 media internal decomposition、transparent asset report、internal source promotion、M29 contract docs/tests

## Summary

M29.6 内部资产分解已经避免了文案、文件名、行业、主题色、固定 bbox 这类硬特化；当前生产代码搜索也没有确认到这类 active literal/fixed-sample 特化规则。

但这条链路仍有两类需要后续处理的结构性特化风险：

1. **OCR-anchor evidence bias**：内部 foreground pixel scanning 目前主要来自 raw M29 primitive 与 OCR 附近多方向窗口。它已经不是“只看文字上方”，但仍可能漏掉没有 OCR 锚点的内部图形、装饰对象、table marker、圆点或小图标。
2. **confidence gate drift**：当前实现已允许 `high` confidence 或 `groupSupportedExecution=true` 的 medium candidate 继续进入透明资产和 promotion gate，但文档、合同矩阵、reason 命名仍有 “high-confidence only” 的旧表述，容易把后续实现拉回单一置信度特化。

这不是要删除数学阈值。面积、长宽比、foreground contrast、hero/texture penalty、text overlap、alpha coverage 这类阈值是正常数学参数；问题只出现在规则依赖单张样本、固定方向、固定文案、文件名、行业、主题色、固定 bbox，或把一个证据源当成唯一事实源。

## Reproduction

复现方式：

1. 上传真实图 `/Users/luhui/Library/Application Support/PixPin/Temp/PixPin_2026-05-25_14-43-04.png`，观察复合 media 区域内部的 action icon、未带 OCR 锚点的蓝色/圆形内部图形、以及底部 table 内小元素。
2. 查看最近上传任务 `backend/storage/upload_previews/task_4bcd6d4f5f7b` 的 M29.6 / transparent asset / promotion artifacts。
3. 旧行为中，只有部分 OCR 附近 icon 被提升，部分候选因 `internal_candidate_not_high_confidence` 被挡住，未被 OCR 锚定的内部 foreground 仍可能没有 source object。
4. 搜索 active backend code：
   - 未确认到按 `充值` / `提币` / `划转` / `买币`、文件名、行业、主题色、固定 bbox 的 active 特化。
   - 确认存在 OCR 多方向 anchor 窗口与 `high or groupSupportedExecution` gate。
5. 搜索 docs/contract：
   - `docs/architecture/backend.md`
   - `docs/engineering/current-mainline-code-map.md`
   - `docs/engineering/testing-strategy.md`
   - `docs/engineering/m29-contract-regression-matrix.md`
   仍有 high-confidence only 或类似旧表述，和当前 group-supported medium 逻辑不完全一致。

## Root Cause

根因是 evidence source 还不完整：

- M29.6 目前把 OCR anchor 当成最强的内部 UI foreground 证据。这对 icon-label row 有效，但不能覆盖所有内部图形资产。
- medium confidence 原本被当成不可执行，这在真实图上会把弱但有重复组支持的 icon 卡住。后续已引入 `groupSupportedExecution`，但合同和命名还没有完全跟上。
- 没有独立的 anti-specialization regression guard 来阻止后续代码退化成“只看一个方向 / 只看一个文案 / 只看一个固定区域”的修补。

## Latest Evidence: task_8d5806b08f44

最新真实上传任务 `backend/storage/upload_previews/task_8d5806b08f44` 显示当前问题不是 pipeline 崩溃，而是 evidence -> asset -> promotion 的质量不足：

- pipeline 全部 stage completed；M29.6、transparent assets、promotion、final replay plan、materializer、visual comparison 都已产出。
- M29.6 生成 `229` 个 internal candidates，`140` 个 accepted report candidates，但 transparent asset 只允许 `10` 个，internal source promotion 只提升 `8` 个。
- transparent asset rejection 主因包括：
  - `internal_candidate_not_high_confidence`: `139`
  - `internal_candidate_not_accepted`: `54`
  - `overlaps_ocr_text`: `47`
  - `transparent_candidate_too_thin`: `29`
  - `unstable_background`: `34`
- 轮播区域四个 action icons 已能被提升，但 promoted icon PNG 仍可能包含局部深色背景/边缘残留；例如 `m292_promoted_internal_icon_0004.png` 的 edge alpha 仍偏高，说明 alpha mask 不是足够干净的 UI icon cutout。
- 当时 parent media cleanup 仍未解决：提升出来的 icon/text 是 overlay，父 media 内部原像素没有针对 promoted internal asset 做稳定擦除，所以视觉上可能仍有重复/残留/块感。第一轮修复已加入 M29.5 copied media cleanup 授权和 materializer alpha-mask 擦除；525 全量样本阶段仍需验证它是否足够稳定。
- table/card 内部小圆点、小图标、局部 marker 仍大量落在 `overlaps_internal_text_mask` 或 OCR-anchor 附近候选里；这证明 OCR anchor 不能继续作为主要入口，必须补 non-OCR internal foreground component 与 marker/circle evidence。

## Fix

已完成第一轮通用修复：

1. M29.6 内部候选来源已拆成多个证据源：
   - raw primitive inside media；
   - OCR-anchor local foreground；
   - non-OCR generic foreground component inside media。
2. OCR 现在只是 relation hint，不再是唯一 foreground 扫描入口。
3. Transparent asset extraction 新增 edge-alpha metrics 和 `edge_alpha_risk` 拒绝门，避免透明 PNG 周边仍带明显背景块。
4. Promotion permission 已明确为：

```text
PromoteInternalAsset(o) =
  accepted_report_candidate(o)
  and TransparentAssetAllowed(o)
  and (
    Confidence(o) = high
    or GroupSupportedExecution(o)
  )
  and not OwnershipConflict(o)
```

5. M29.5 会在 promoted internal asset 与 parent media 的 relation 成立时写入 copied media cleanup 授权。
6. Materializer 只消费 M29.5 cleanup target，并优先用 transparent asset alpha mask 擦 parent copied media asset。

后续修复应继续按通用证据层推进：

1. 增加 repeated small-object pattern 和 circular/marker primitive evidence。
2. 增加 separator/control-background evidence。
3. 需要时再把 `RepetitionSupported(o)` 作为 promotion 许可来源，但必须先有独立 report/test 支撑。
4. 增加代码级/测试级 guard，禁止 literal text、filename、theme、industry、fixed bbox、single-direction-only anchor 进入 active mainline。

## Regression Guard

已有保护：

- `test_media_internal_decomposition.py::test_ocr_anchor_foreground_uses_multiple_relations_not_only_above_text`
- `test_transparent_asset_report.py::test_group_supported_medium_internal_icon_uses_alpha_gate`
- `test_internal_source_promotion.py::test_internal_source_promotion_promotes_group_supported_medium_internal_icon`

已新增：

- 覆盖 non-OCR internal foreground component 的 report-only 候选测试。
- 更新 `docs/engineering/m29-contract-regression-matrix.md`，把 OCR-anchor、non-OCR foreground、group-supported medium 分开列为合同 case。
- 覆盖 transparent asset edge-alpha 风险拒绝。
- 覆盖 promoted internal asset 的 M29.5 copied media cleanup 授权和 materializer alpha-mask 擦除。

仍需新增：

- 覆盖 table/cell 内 circular marker 或 small icon 的通用 source evidence 测试。
- 覆盖 anti-specialization source scan 或 contract test：active M29 chain 不得出现 literal label、filename、industry、theme、fixed bbox 或 single-direction-only execution gate。

## Validation Evidence

当前 bug 记录阶段只做审计，不改运行行为。

已执行的相关验证：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py -q
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
git diff --check
```

最近通过结果：

```text
60 passed
```

最近验证命令：

```bash
cd backend
uv run pytest tests/test_media_internal_decomposition.py tests/test_transparent_asset_report.py tests/test_internal_source_promotion.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_upload_preview_pipeline.py -q
```

## Prevention Notes

后续处理这类问题时，不允许：

- 按 `充值`、`提币`、`划转`、`买币` 等文案写规则。
- 按 PixPin 文件名、上传文件名、行业、App 类型、主题色写规则。
- 按固定 bbox、固定屏幕位置、固定轮播/表格样本写规则。
- 在 materializer、Renderer 或 Figma plugin 里补 source ownership。

允许：

- 增加通用 pixel/component evidence。
- 增加通用 relation graph evidence。
- 增加通用 repetition/group evidence。
- 增加可审计 report-only 阶段。
- 用真实图批量验证阈值，但阈值必须是可解释的数学参数，不得绑定某张图。
