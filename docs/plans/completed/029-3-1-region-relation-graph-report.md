# M29.3.1 Region Relation Graph Report

- 状态：completed
- 创建日期：2026-05-23
- 负责人：未指定

## Goal

把 M29.2 source physical graph 的 source objects 转成只读关系图报表：

```text
M29.2 sourceObjects
-> pairwise relation(A, B)
-> region_relation_graph_report.json
```

本阶段只固定关系语言和可审计输入，不做 cluster、component、role hint 或 DSL/Figma 输出变更。

## Scope

包含：

- 新增 `M2931RegionRelationGraphReport`。
- 输入只消费 M29.2 `sourceObjects`。
- 使用 M29.3.0 `classify_region_relation(...)` 生成全量 pairwise edges。
- 节点只保留 `id`、`bbox`、`pixelOwner`、`replayDecision`、`confidence`，并原样保留 `visualKind` 作为证据字段。
- edge 保留 `primarySetRelation`、`secondaryGeometryRelations` 和 metrics。
- 上传管线写入 `m29_3/region_relation_graph_report.json`，stage key 为 `m29_3_relation_graph_report`。
- 阶段失败只记录 optional stage failure，不阻断 M29 direct 或主线 M30。

不包含：

- 不新增 route。
- 不做 overlay。
- 不做 ownership 修改。
- 不做 clustering、componentization、Auto Layout、Figma Component/Instance。
- 不把 `visualKind` 改名或解释成 UI 语义真值。

## Acceptance

- 空图、单节点、两节点、多节点都能生成稳定 report。
- invalid bbox 被跳过并计入 summary，不导致整个阶段失败。
- summary 包含 node/edge 数、primary/secondary relation counts、invalid bbox skip count 和 warning count。
- summary guard 字段保持：

```text
dslChanged=false
assetChanged=false
createdVisibleNodeCount=0
```

- 上传任务完成后存在：

```text
storage/m30_1_uploads/{taskId}/m29_3/region_relation_graph_report.json
```

## Validation

```bash
cd backend
uv run pytest tests/test_region_relation_graph_report.py -q
uv run pytest tests/test_m30_upload_pipeline.py tests/test_region_relation_kernel.py tests/test_m29_direct_replay.py -q
cd ..
git diff --check
git status --short --branch
```

## Notes

- ADR 0070 是本阶段的架构决策来源，不新增 ADR。
- M29.3.1 的输出是 M29.4 stable design cluster 的输入，不是 DSL replay truth。
