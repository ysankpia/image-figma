# M29 B-Stage Report And Permission Program

- 状态：active
- 创建日期：2026-05-25
- 负责人：未指定

## Goal

把 M29 已有的 pixel owner、relation、weak cluster、replay plan 主链继续向 Codia 级结构能力推进，但仍坚持先证据、后权限、再 materialization。B 阶段只做当前主链依赖的 report-only / permission-only 层，不直接生成 Figma Group、Frame、Auto Layout、Component、Instance、Variant 或 Vector。

## Current Anchor

已完成：

- `043-pixel-ownership-conservation-report.md`
- `backend/app/ownership_conservation/`
- 真实上传 `task_ed8387636f80` 已验证 report artifact 生成。
- `045-m29-5-visible-replay-overlap-suppression.md`

初始真实上传暴露的第一项修复事实：

```text
ownership_conservation_report.conflictTypeCounts.visible_ownership_overlap = 9
```

冲突集中在同类 `raster_icon/raster_icon` 和 `control_background/control_background` visible replay overlap。它们属于 M29.5 replay owner 去重缺口，不应在 materializer、Renderer 或 plugin 层修。

Phase 1 已把单图 `visible_ownership_overlap` 从 9 降到 0。但单图不再作为后续阶段的充分验收。后续每个 phase 必须使用 `/Users/luhui/Downloads/m29` 下全部 15 张 PNG 做 batch upload validation。

## Scope

包含：

- M29.5 visible replay overlap suppression。
- Hierarchy candidate report。
- Sibling group candidate report。
- Layout energy report。
- Auto Layout permission report。
- Single-page design token report。
- B-stage quality/repair-cost report。

不包含：

- 不做 PSD/PDF/Web 多源输入。
- 不做 Component Isomorphism、Variant、Vectorization。
- 不创建 Figma Component/Instance。
- 不把 M29.4 weak cluster 直接提升成 materialization 权限。
- 不在 materializer、Renderer 或 plugin 按颜色、文案、主题、行业、文件名、固定 bbox 特化。

## Execution Phases

### Phase 1: M29.5 Visible Replay Overlap Suppression

目标：在 M29.5 replay plan 层压制同类 accepted visible claims 的明显重复 owner，修复 ownership conservation report 暴露的 replay owner 不守恒。

边界：

- 同类 icon/icon 或 shape/shape 强重叠、near-equal、contained duplicate 可以 `suppress_duplicate`。
- shape/text、shape/icon background/foreground overlap 继续允许。
- image/text 仍只由 copied image asset cleanup 解释。
- 不改变 materializer 逻辑。

### Phase 2: M29 Hierarchy Candidate Report

目标：基于 M29.2 source objects 和 M29.3 relation graph 输出 candidate parent/child report。

边界：

- report-only。
- 不创建 DSL group/frame。
- 不改变 replay order。
- 输出 parent candidates、confidence、risk、conflict reasons。

### Phase 3: M29 Sibling Group Candidate Report

目标：基于 relation density、alignment、gap regularity、owner pattern 输出 sibling group candidates。

边界：

- report-only。
- 不创建 component 或 group。
- 只给后续 layout/component 阶段提供候选证据。

### Phase 4: M29 Layout Energy Report

目标：对 candidate group/container 计算 row/column/grid/overlay/absolute energy。

边界：

- report-only。
- 不生成 Auto Layout。
- 只输出 layout model candidates、energy、confidence、drift risk。

### Phase 5: M29 Auto Layout Permission Report

目标：把 layout energy 转成 permission report，明确哪些 container/group 在未来可以安全尝试 Figma Auto Layout。

边界：

- permission-only。
- 不改变 DSL。
- 不写 Figma layoutMode。
- 不处理 responsive inference。

### Phase 6: M29 Design Token Report

目标：从当前 source objects、plan items、materialized DSL 中抽取单页颜色、字号、间距、圆角 token candidates。

边界：

- report-only。
- 不绑定 Figma variables。
- 不做多页设计系统合并。
- 不做语义命名承诺。

### Phase 7: M29 B-Stage Quality Report

目标：汇总 ownership、hierarchy、group、layout、auto-layout permission、token reports，输出 B-stage quality and repair-cost summary。

边界：

- report-only。
- 不改变 API response shape。
- 不阻断 upload-preview，除非 report builder 自身编程错误。

## Per-Phase Validation Loop

每个执行 phase 必须完成：

```bash
cd backend
uv run pytest <focused tests> -q
uv run pytest tests/test_upload_preview_pipeline.py tests/test_m29_replay_plan.py tests/test_m29_plan_materializer.py tests/test_source_ui_physical_graph.py -q
cd ..
git diff --check
```

每个 phase 完成后必须：

1. 重启 backend。
2. 使用全部真实样本上传验证：

```text
/Users/luhui/Downloads/m29/*.png
```

3. 首选命令：

```bash
cd backend
uv run python scripts/run_upload_preview_batch_validation.py --input-dir /Users/luhui/Downloads/m29
```

4. 检查 batch ledger、每个 task completed、stage timings、phase artifact、materialization report。
5. 若新增 report 暴露本阶段应修问题，先修完再提交。
6. 独立提交。

## Stop Conditions

遇到以下情况停止后续依赖阶段：

- backend 无法启动。
- `/api/upload-preview` 无法完成。
- `/api/tasks/{taskId}/dsl` 无法返回。
- materialized DSL 或 asset response shape 被本阶段改变。
- batch validation 中任意样本 task failed 或缺少必备 artifact。
- focused/backend tests 出现和本阶段相关的失败且无法在当前边界内修复。
- 需要进入 Component/Variant/Vectorization/Figma materialization 权限时。

## Acceptance

- B 阶段所有新增能力都可从 repo docs、tests 和 upload-preview artifacts 审计。
- 每个 phase 有独立 completed plan 和 commit。
- 当前 product mainline 仍是 M29 plan-driven flat materialization。
- B 阶段完成后才重新评估 Component Isomorphism、Variant、Vectorization 和 Figma Component/Instance。
