# M30.4 Preserve Isolated Text Nodes in Candidate Audit

- 状态：completed
- 创建日期：2026-05-20
- 负责人：Antigravity

## Goal

解决主链路上传过程中，孤立或由于配对冲突导致聚类被跳过的文本节点（如 "美妆"、"探店"、"氛围感拉满～"）被 M29.0.4 过滤丢弃的问题。确保所有 OCR 成功识别且未被合并的文本节点能安全作为单节点 text_cluster 候选保留，并最终在 DSL/Figma 中呈现。

## Scope

包含：
- 在 `backend/app/visual_object_candidate_audit.py` 的 `build_object_candidates` 兜底循环中，增加对 `node.node_kind == "text"` 的 fallback 处理。
- 保留未被使用的文本节点为单节点 `text_cluster` 候选对象，并将 decision 标记为 `"rejected"`（使其仅作为文本载体，不作为视觉对象）。
- 在 `backend/tests/` 中为 `build_object_candidates` 添加单元测试，回归防护该问题。

不包含：
- 不修改 `visual_text_pair` 算法或 `build_text_clusters` 聚类本身的算法逻辑，以防对其他还原效果造成破坏。
- 不影响现有的 Figma Renderer 布尔减算或 conservative text cover 逻辑。

## Steps

1. 修改 `backend/app/visual_object_candidate_audit.py` 中的 `build_object_candidates`，在末尾 the fallback 节点处理循环中添加对 `node.node_kind == "text"` 的处理，将其生成为 `text_cluster` 类型的对象。
2. 编写/更新单元测试，针对 `build_object_candidates` 提供测试用例：输入包含未被使用的 `text` 节点，断言输出中包含它。
3. 运行测试，确保整个处理管线和 M29.0.4-M30 主链校验通过。

## Acceptance

- 运行测试套件全部通过：`pytest backend/tests/`。
- 上传 task `task_9a96ac511404` 重新运行后，M29.0.5 导出的 `refined_visual_objects.json` 中包含 "美妆"、"探店"、"氛围感拉满～" 对应的 text members，且最终的 DSL 中包含这些文本。

## Validation

### Automated Tests
```bash
pytest backend/tests/test_visual_object_candidate_audit.py
```
- 新增的回归测试 `test_isolated_text_box_is_preserved_as_rejected_text_cluster` 顺利运行并通过。

### Manual Verification
- 端到端清理数据库并重跑 `task_9a96ac511404` 识别管线，输出的 `m30_materialized_dsl.json` 中已成功找回原先缺失的 "探店"、"美妆"、"氛围感拉满～" 等共 5 处孤立文本节点，位置与字号还原符合原图视觉效果。
