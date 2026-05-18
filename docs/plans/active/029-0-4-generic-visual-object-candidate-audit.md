# M29.0.4 Generic Visual Object Candidate Audit

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Goal

M29.0.4 是 M29+ 的通用对象候选审计层。它消费 M29.0.3 已标准化 visual evidence 和 M29.0.2 text boxes，生成 generic `VisualObjectCandidate`、`VisualObjectSetCandidate` 和 edge audit，用来解释已看见的 visible evidence 是否能形成稳定、可审计的视觉对象候选。

M29.0.4 不是 `NavigationItemComposition`，不识别 bottom nav、toolbar、shortcut、purchase tool 或 category tile，不接新 detector，不回写 M29/M29.1/M29.0.2/M29.0.3，不进入上传主链路，不改 DSL/Figma。

## Candidate Universe

硬合同：

```text
candidate universe = M29.0.3 VisualEvidenceItem + M29.0.2 textBoxes
```

M29 nodes、M29 blocked evidence、M29.1 group_nodes 和 M29.0.2 mediaEvidence 只能作为 source expansion / validation / debug lookup，不能直接新增候选。

## Implementation

新增：

```text
backend/app/visual_object_candidate_audit.py
backend/scripts/run_m29_0_4_visual_object_candidate_audit.py
backend/tests/test_visual_object_candidate_audit.py
```

输出到 M29 output 下的 `m29_0_4/`：

```text
visual_object_candidates.json
visual_object_candidates.md
edge_audit.json
preview_visual_objects.png
assets/visual_objects/*.png
assets/uncertain_objects/*.png
assets/split_candidates/*.png
assets/rejected_objects/*.png
overlays/16_visual_object_candidates.png
overlays/17_visual_object_edges.png
overlays/18_split_candidates.png
overlays/19_visual_object_sets.png
```

## Contract

Document schema：

```text
M2904GenericVisualObjectCandidateAuditDocument v0.1
```

核心结构：

```text
VisualObjectEvidenceNode
VisualObjectEvidenceEdge
VisualObjectCandidate
VisualObjectMember
VisualObjectSetCandidate
EdgeAuditItem
```

object kinds：

```text
single_visual
compound_visual
visual_text_pair
text_cluster
split_candidate
uncertain_compound
```

set kinds：

```text
repeated_visual_set
aligned_row_set
aligned_grid_set
```

M29.0.4 是 audit-first，不以 accepted 数量为目标。`text_noise` 不改上游判定，只能作为 `weak_visual_text_noise` evidence node 和 `weak_visual` member 使用，并带 `text_overlap` / `icon_like_text_noise` risk。wide source bbox 只能生成 `split_candidate` / `split_needed`，不能从内部裁 accepted child object。

## Run

```bash
cd backend
uv run python scripts/run_m29_0_4_visual_object_candidate_audit.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --m29-output storage/m29_visual_primitive_graph_audit_20260518_160831
```

## Validation

```bash
cd backend && uv run pytest tests/test_visual_object_candidate_audit.py -q
cd backend && uv run pytest tests/test_visual_primitive_graph.py tests/test_symbol_fragment_grouping.py tests/test_text_masked_media_audit.py tests/test_visual_evidence_normalization.py tests/test_visual_object_candidate_audit.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```

真实图 smoke 是 diagnostic。验收重点不是 accepted 数量，而是 visual/text evidence 是否进入 object candidate graph，split/uncertain/rejected 是否可见，edge audit 是否解释得通，以及没有 UI 模式专用合同词或新 detector 偷渡。

## Verification Evidence

2026-05-18 本阶段验证：

```text
cd backend && uv run pytest tests/test_visual_object_candidate_audit.py -q
=> 9 passed

cd backend && uv run pytest tests/test_visual_primitive_graph.py tests/test_symbol_fragment_grouping.py tests/test_text_masked_media_audit.py tests/test_visual_evidence_normalization.py tests/test_visual_object_candidate_audit.py -q
=> 46 passed

cd backend && uv run pytest
=> 238 passed

pnpm run check
=> passed

git diff --check
=> passed
```

真实图 smoke：

```text
uv run python scripts/run_m29_0_4_visual_object_candidate_audit.py --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" --m29-output storage/m29_visual_primitive_graph_audit_20260518_160831 --overwrite
=> nodes=630 edges=16608 objects=351 sets=26
```

smoke 产物位于 `backend/storage/m29_visual_primitive_graph_audit_20260518_160831/m29_0_4/`，只作为本地诊断证据，不提交。
