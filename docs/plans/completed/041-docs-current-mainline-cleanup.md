# Docs Current M29 Mainline Cleanup

- 状态：completed
- 创建日期：2026-05-24
- 负责人：Codex

## Goal

把仓库文档事实来源收口到当前 M29/M30 主链，清理 `docs/plans/active`、`docs/index.md` 和 `AGENTS.md` 中的历史阶段噪音。

当前事实链：

```text
raw M29 primitive graph
-> M29.2 source ownership
-> M29.3 region relation
-> M29.4 weak structural cluster
-> M29.5 replay plan
-> M29 Direct compare / M30 materialization
```

本阶段只改文档，不改算法、不删代码、不改测试逻辑。

## Scope

包含：

- 将已完成计划从 `docs/plans/active/` 移到 `docs/plans/completed/`。
- 将 superseded/deferred 计划移到 `docs/plans/archive/` 下对应目录。
- 保留 `039-1-1-unit-candidate-quality-gate.md` 为唯一既有 active 计划。
- 精简 `docs/index.md` 的 Start Here。
- 重写 `AGENTS.md` 的项目状态和实现约束，使 M29/M30 主链成为明确事实。
- 新增当前主线代码地图，给后续无行为变更拆分长文件提供依据。
- 更新文档维护规则，要求计划状态和目录一致。

不包含：

- 不删除 backend 代码。
- 不移动测试。
- 不改 API、DSL、pipeline、Renderer 或插件行为。
- 不修改 ADR 历史记录。
- 不开始代码瘦身。

## Evidence Closure

这些原 active 计划已有实现/测试/架构文档证据，本阶段改为 completed 并移动：

```text
029-2-1-pixel-ownership-consistency.md
029-2-source-level-ui-physical-graph.md
029-3-0-region-relation-kernel.md
029-3-1-region-relation-graph-report.md
029-4-stable-design-cluster.md
029-5-replay-engine-v2-quality-plan.md
029-direct-replay-experiment.md
029-direct-replay-figma-compare-mode.md
029-direct-source-support-and-layer-order-fix.md
029-shape-geometry-fit-before-radius-replay.md
030-6-accepted-image-asset-materialization-policy.md
030-7-raster-layer-deduplication-for-materialized-media.md
034-3-text-symbol-leakage-cleanup-before-m30-materialization.md
036-context-aware-text-foreground-color-sampling.md
036-1-contrast-weighted-text-foreground-sampling.md
037-m31-to-m30-hierarchy-readiness-and-ownership-bridge.md
038-controlled-hierarchy-materialization.md
```

`039-1-1-unit-candidate-quality-gate.md` 保持 active，因为当前代码未看到计划要求的 `promotionReady`、`qualityTier`、`rejectReasons` 字段。

## Acceptance

- `docs/plans/active/` 只保留 `039-1-1-unit-candidate-quality-gate.md`。
- `docs/plans/completed/` 有 completed index，并包含完成计划入口。
- `docs/plans/archive/superseded/` 和 `docs/plans/archive/deferred/` 有 index。
- `docs/index.md` Start Here 不再列出已完成 M29-M39 阶段计划。
- `AGENTS.md` 明确 M29 source truth、M30 consumer、M20-M28/SAM2/perception legacy 边界。
- 新增 `docs/engineering/current-mainline-code-map.md`。
- 文档验收命令通过。

## Result

本阶段完成文档事实层收口：

- 已完成计划移出 `docs/plans/active/`，进入 `docs/plans/completed/`。
- `030-2-1-legacy-pre-m29-surface-freeze.md` 进入 `docs/plans/archive/superseded/`。
- `040-nested-hierarchy-materialization.md` 进入 `docs/plans/archive/deferred/`。
- `docs/index.md` 的 Start Here 改为当前主链入口，不再列出历史阶段计划。
- `AGENTS.md` 改为 M29/M30 主链合同说明，替换旧 M15-M39 长流水账。
- 新增 `docs/engineering/current-mainline-code-map.md`，作为后续无行为变更拆分长文件的依据。
- `docs/engineering/doc-maintenance.md` 明确计划状态和目录必须一致。

## Validation

```bash
git diff --check
python - <<'PY'
from pathlib import Path
active = sorted(Path("docs/plans/active").glob("*.md"))
print([p.name for p in active])
assert [p.name for p in active] == ["039-1-1-unit-candidate-quality-gate.md"]
for p in active:
    text = p.read_text(encoding="utf-8")
    assert "- 状态：active" in text
PY
rg -n "状态：completed|状态：deferred|superseded-by" docs/plans/active
rg -n "当前 .*计划：\\[plans/active/029|当前 .*计划：\\[plans/active/030|当前 .*计划：\\[plans/active/031|当前 .*计划：\\[plans/active/032|当前 .*计划：\\[plans/active/033|当前 .*计划：\\[plans/active/034|当前 .*计划：\\[plans/active/035|当前 .*计划：\\[plans/active/036|当前 .*计划：\\[plans/active/037|当前 .*计划：\\[plans/active/038|当前 .*计划：\\[plans/active/039-content|当前 .*计划：\\[plans/active/039-1-unit" docs/index.md
rg -n "SAM2.*当前主链|perception.*当前主链|M20-M28.*当前主链|M26.*当前主链|M27.*当前主链|M28.*当前主链" AGENTS.md docs/index.md docs/engineering/current-mainline-code-map.md
git status --short --branch
```

For the two `rg` negative checks, no matches is the expected result.
