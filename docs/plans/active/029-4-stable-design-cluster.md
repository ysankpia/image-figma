# M29.4 Stable Design Cluster

## Summary
把 M29.3.1 的只读 pairwise relation report 继续向前收口，产出“稳定设计簇”报表，而不是组件化、语义分类或可见 DSL 变化。输入只吃 `M29.3.1 region_relation_graph_report.json`，输出只写 `m29_4/stable_design_cluster_report.json` 和 stage timing，不改 `/dsl`、不改 Figma 可见输出、不新增 route、不接模型。

这一步的目标是把“关系图里哪些局部子图足够稳定、足够重复、足够可审计”先固定下来，作为后续 M29.5 Replay Engine V2 和更晚的 component candidate isomorphism 的证据层。

## Key Changes
- 新增后端只读报表模块 `backend/app/stable_design_cluster.py`，提供纯函数式入口，消费 M29.3.1 report，不回读 OCR、不重跑 M29、不碰原始 PNG。
- 新增 stage key `m29_4_stable_design_cluster`，产物落到 `backend/storage/m30_1_uploads/{taskId}/m29_4/stable_design_cluster_report.json`。
- cluster v1 只做结构性聚合，不做 UI semantic detector：
  - 只基于 relation graph 的 containment、alignment、near-equal、repetition、boundary separation 等结构证据聚类。
  - cluster 只保留结构字段：`id`、`bbox`、`memberNodeIds`、`edgeIds`、`clusterPattern`、`stabilityScore`、`repeatabilityScore`、`reasons`、`risks`。
  - 可以带弱结构 role hint，但只能是 `row_like`、`column_like`、`repeated_item_like`、`background_anchor_like`、`media_text_group_like` 这类结构提示，不能出现 SearchBar、Card、TabBar 之类的 UI 真值命名。
- 聚类规则保持保守、可重复、可解释：
  - 优先形成局部稳定子图，不追求全局最大团。
  - 只接受足够稳定的候选；低置信或结构冲突的候选进入 report 的 skipped/warnings。
  - 对重叠或嵌套 cluster 做确定性裁决，避免同一批节点无限重复出簇。
- pipeline 中把 M29.4 作为 M29.3.1 之后的非阻断诊断阶段接入；如果 cluster 生成失败，只记 warning，不阻断 M29 direct replay 或后续主链路。
- 不新增 overlay、不改 asset、不改 DSL schema、不做 Auto Layout、不做 Component/Instance、不做 role hint 晋升。

## Test Plan
- 新增 `backend/tests/test_stable_design_cluster.py`，覆盖：
  - 空图、单节点、纯 disjoint 图。
  - 简单 containment 链、alignment 链、重复局部子图。
  - 横向与纵向同构但方向不同的 cluster 不能合并。
  - 嵌套 cluster 在结构签名不同的时候应保留，重复成员高度重叠时应去重。
  - invalid bbox / malformed edge 被跳过并计入 warning。
  - 报表内容稳定排序、确定性输出、不会修改输入的 M29.3.1 report。
- 更新 `backend/tests/test_m30_upload_pipeline.py`，确认上传完成后会写出 M29.4 报表和 stage timing，且不会影响现有 M29.3.1 / M29 direct / M30 产物。

## Assumptions
- M29.4 先做成纯报表阶段，不做 overlay、不做 route、不做可见节点。
- 结构性弱 role hint 允许存在，但只能作为后续阶段的证据，不是 truth source。
- 默认阈值选择保守策略，宁可少报 cluster，也不要把不稳定结构误合并成组件雏形。
- 本阶段不引入新依赖、不接 ONNX、不接 SAM、不接外部模型。
- 组件化和模板/slots/instances 仍然留给 M29.5 之后，不在 M29.4 展开。
