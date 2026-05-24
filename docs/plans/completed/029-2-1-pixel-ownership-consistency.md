# M29.2.1 Pixel Ownership Consistency

- 状态：completed
- 创建日期：2026-05-23
- 负责人：未指定

## Goal

在 M29 Direct Replay 左侧实验路径里，先修一个最小但根本的 ownership 问题：

```text
同一块 source foreground evidence pixel / replay foreground pixel
不能同时被 editable text、copied raster media 和 fallback 重复表达。
```

本阶段只处理 copied `m29_direct_image` asset 内部的 editable text 重影。它使用 M29.3.0 region relation kernel 判断 text bbox 和 image bbox 的集合关系，不再临时写另一套 contains/near-equal 判断。

## Scope

包含：

- `m29_direct_text` 已经成立，且其 bbox 被 copied `m29_direct_image` bbox 包含或近似同框时，清理 copied image asset 中对应局部像素。
- 只修改 `output_dir/assets/m29_direct_image/...` 中的 copied asset。
- 不修改 source PNG。
- 不修改 raw M29 asset。
- `fallback` 继续只擦 replay-safe objects。
- `preserve_in_parent_raster` 不生成 editable text，不清理 copied image，也不清理 fallback。
- report summary 增加 copied image asset text cleanup 计数。
- 增加回归测试覆盖 editable text、preserved raster text、text outside image 三类场景。

不包含：

- 不实现 M29.3.1 relation graph report。
- 不实现 cluster/component/Auto Layout。
- 不处理 icon fragment ownership。
- 不清理 `card_background` / `control_background` 等既有命名。
- 不改变 `/api/tasks/{taskId}/dsl` 主线输出。
- 不改变 M29.2 source graph 合同。

## Steps

1. 扩展 M29 Direct Replay 内部 replay 记录，使 image/text replay 能带 role、asset id、asset URL 和 replay decision。
2. 新增 copied image asset cleanup：遍历 replayed text 与 replayed `m29_direct_image`，用 `classify_region_relation(text, image)` 判断 `contained_by` 或 `near_equal`。
3. 将 text page bbox 映射到 copied asset local bbox，并用 copied asset 局部 outer ring 采样填充。
4. 在 report summary 中记录 `copiedImageAssetTextErasedCount`。
5. 增加 `backend/tests/test_m29_direct_replay.py` 回归测试。

## Acceptance

- editable text contained by copied image asset 时，copied image asset 对应局部像素被清理。
- preserve raster text contained by image asset 时，copied image asset 不被清理，fallback 不被清理。
- text outside copied image asset 时，copied image asset 不被清理。
- source PNG 不变。
- raw M29 asset 不变。
- 现有 M29 Direct Replay 行为不回归。

## Validation

```bash
cd backend
uv run pytest tests/test_m29_direct_replay.py tests/test_region_relation_kernel.py -q
uv run pytest tests/test_source_ui_physical_graph.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

- ADR 0071 是本阶段的 ownership 决策来源，不新增 ADR。
- 本阶段故意不判断“商品图 / banner / 搜索框”。它只执行通用像素归属：如果 editable text 已经 replay，它对应的 foreground 不应继续留在 copied media asset 里。
- 高纹理/艺术字是否应该进入 `preserve_in_parent_raster` 属于 M29.2 source ownership upstream 决策；本阶段只尊重已经给出的 replay decision。
