# M29.3.0 Region Relation Kernel

- 状态：completed
- 创建日期：2026-05-23
- 负责人：未指定

## Goal

实现一个无状态、纯 bbox 几何的 region relation kernel，为后续 M29.2.1 pixel ownership solver 提供统一关系语言。

核心合同：

```text
relation(A, B) -> {
  primarySetRelation,
  secondaryGeometryRelations,
  metrics
}
```

## Scope

包含：

- 新增纯函数 kernel，不依赖 OCR、M29 document、pipeline、DSL、Figma 或 storage。
- 支持 primary set relation：`near_equal`、`contains`、`contained_by`、`overlaps`、`disjoint`。
- 支持 secondary geometry relations：`near`、方向、对齐、尺寸相似。
- 增加 thin-aware、capped near threshold，避免 1px 细线阈值塌缩和长线无限吸附。
- 增加单元测试覆盖基础几何、细线、方向、对齐、尺寸相似和无效 bbox。

不包含：

- 不接入 `source_ui_physical_graph.py`。
- 不改变 M29 Direct DSL 输出。
- 不生成 relation graph report 或 overlay。
- 不做 ownership、cluster、component、Auto Layout。
- 不清理 `card_background` / `control_background` 等既有实现命名。

## Steps

1. 新增 `backend/app/region_relation_kernel.py`，实现 `classify_region_relation(left_bbox, right_bbox, options=None)`。
2. 返回 `M29RegionRelation`，包含 `primarySetRelation`、`secondaryGeometryRelations` 和 metrics。
3. 新增 `backend/tests/test_region_relation_kernel.py`，覆盖计划中的关系场景。
4. 更新 `docs/index.md`，加入本计划入口。

## Acceptance

- `classify_region_relation` 对无效 bbox 抛 `ValueError`。
- primary relation 判定顺序稳定：`near_equal` -> `contains/contained_by` -> `overlaps` -> `disjoint`。
- close row item 能返回 `disjoint` + `near` + `left_of` + `aligned_center_y`。
- vertical item 能返回 `above/below`，不被误当成横向 flow。
- 细 separator 6px 外仍可 near，25px 外不 near。
- 长条不会因为长边产生过远 near。
- 本阶段不改变现有 upload pipeline 或 M29.2/M29 Direct 输出。

## Validation

```bash
cd backend
uv run pytest tests/test_region_relation_kernel.py -q
uv run pytest tests/test_source_ui_physical_graph.py tests/test_m29_direct_replay.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

- ADR 0070 是本阶段的架构决策来源，不新增 ADR。
- M29.2.1 后续必须消费这个 kernel，不能再临时实现另一套 `contained_by / near / aligned` 判断。
- Source region 最小数据结构、M29.3.1 relation graph report、M29.4 stable design cluster 都留给后续阶段。
