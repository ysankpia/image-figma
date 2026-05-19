# Bug: Text Nodes Missing from DSL/Figma Due to Omission in M29.0.4 Fallback Nodes

- 状态：resolved
- 创建日期：2026-05-20
- 解决日期：2026-05-20
- 影响范围：M29.0.4 Object Candidate Audit & Upstream Upload Pipeline

## Summary

在 PNG 上传识别主链路中，部分被 OCR 成功识别到的文字（例如 Tab 栏中的 "美妆"、"探店" 或是文字段落 "氛围感拉满～"）在最终生成的 DSL 和 Figma 还原中完全缺失（没有蓝色标注框，也没有文本节点）。

## Reproduction

在处理 `task_9a96ac511404` (或任何包含类似单字/孤立文本的图像) 时：
1. 百度 OCR 成功检测到 "美妆"、"探店"、"氛围感拉满～"；
2. 在 M29.0.4 之前的证据提取阶段，生成了对应的 `evidence_0054` ("美妆"), `evidence_0056` ("探店"), `evidence_0074` ("氛围感拉满～") 文本证据节点；
3. 执行 M29.0.4 `visual_object_candidate_audit.py` 后，在输出的 `visual_object_candidates.json` 中，没有包含这些证据节点的 Object 存在；
4. 导致 M29.0.5 `refined_visual_objects.json` 中缺失对应的 refined text members，最终 DSL 丢失该文本。

## Root Cause

在 M29.0.4 候选对象构建逻辑 `build_object_candidates` 中：
1. 文本节点参与的第一阶段是配对：如果文本节点与视觉背景节点较近，会形成 `visual_text_pair`（例如 "推荐" 与背景白卡配对），该文本节点被标记为 `used_nodes`。
2. 文本节点参与的第二阶段是聚类：剩余的文本节点被 `build_text_clusters` 聚类。然而聚类算法是将相近的文本节点**贪婪地两两配对**。例如 `evidence_052`("推荐") 与 `evidence_054`("美妆") 形成了聚类。
3. 聚类过滤逻辑：
   ```python
   for cluster_nodes, cluster_edges in text_clusters:
       if any(node.id in used_nodes for node in cluster_nodes):
           continue
       objects.append(...)
   ```
   因为 "推荐" (`evidence_052`) 在第一阶段已经因为 `visual_text_pair` 被加入到 `used_nodes` 中，导致整个 `推荐-美妆` 聚类被 `continue` 跳过，从而 "美妆" 成为一个孤立的、没有被任何对象引用的文本节点。
4. 孤立节点兜底逻辑：
   在构建对象的最后，会遍历所有未被使用的 `used_nodes` 节点，将其作为单节点 fallback 对象加入 `objects`。但是该循环仅处理了 `node.node_kind == "visual"`、`"wide_visual_source"` 和 `"noise"/"weak_visual_text_noise"`，**完全遗漏了 `node.node_kind == "text"`**。
   导致所有未配对成功的文本节点在 M29.0.4 阶段被完全丢弃。

## Fix

在 `backend/app/visual_object_candidate_audit.py` 的 `build_object_candidates` 兜底循环中，增加对 `node.node_kind == "text"` 的处理：
```python
        elif node.node_kind == "text":
            objects.append(make_object(pixels, output_dir, f"voc_{len(objects) + 1:04d}", "text_cluster", "rejected", [node], [], options))
            used_nodes.add(node.id)
```
这样未被使用的文本节点会被包装为 `text_cluster` (决策为 `rejected` 以避免成为 visual 干扰) 予以保留，并在 M29.0.5 阶段由 `refine_objects` 顺利提取为 `textMembers`，从而最终进入 DSL。

## Regression Guard

编写单元测试 `test_isolated_text_box_is_preserved_as_rejected_text_cluster` 在 `backend/tests/test_visual_object_candidate_audit.py` 中。向其中输入包含未被使用的 `text` node，验证输出的 `objects` 中必然包含该 text node 作为 `text_cluster` 类型的对象并以 `rejected` 作为决策。

## Validation Evidence

1. **单元测试验证**：
   运行 `pytest backend/tests/test_visual_object_candidate_audit.py`，测试点全部成功通过（包含 regression test）。
2. **端到端流程验证**：
   清理并重跑 `task_9a96ac511404` 识别管线，在最终输出的 `m30_materialized_dsl.json` 中成功找回如下文本节点：
   - `m30_text_0030` ("探店")
   - `m30_text_0038` ("美妆")
   - `m30_text_0039` ("探店")
   - `m30_text_0044` ("氛围感拉满～")
   - `m30_text_0049` ("美妆")
   原先遗失的孤立文本已全部找回并成功还原在画布对应位置。

## Prevention Notes

在处理节点级联过滤或多阶段消费时，应当在流程末尾对**所有**类型的 Node 种类进行覆盖率审计（Coverage Audit），确保每一类关键 Node 都有对应的 fallback/漏网之鱼处理逻辑，防止由于多级合并失败导致数据无声丢失。
