# M29.0.5 Text-Aware Visual Object Refinement

- 状态：completed
- 创建日期：2026-05-18
- 负责人：Codex

## Goal

M29.0.5 是 M29+ 的对象内部图文分层 refinement 层。它只消费 M29.0.4 已有 `VisualObjectCandidate` 和成员证据，把每个 object 拆成 combined audit crop、formal visual assets、shape candidates、text members、unresolved members 和 split-needed audit。

它不新增 detector、不重新扫描整图、不创建新 object、不调用 OCR provider、不接 DSL/Figma、不回写 M29/M29.1/M29.0.2/M29.0.3/M29.0.4。

## Contract

硬合同：

```text
refinement universe = M29.0.4 VisualObjectCandidate
member universe = VisualObjectCandidate.members
lookup refs = M29.0.4 evidenceNodes + M29.0.3 items + M29.0.2 textBoxes
```

每个 M29.0.4 object 恰好生成一个 `RefinedVisualObject`。M29.0.5 不能绕过 M29.0.4 直接从 M29.0.3 item 或 M29.0.2 textBox 创建 object。

Document schema：

```text
M2905TextAwareVisualObjectRefinementDocument v0.1
```

核心结构：

```text
RefinedVisualObject
RefinedVisualAsset
ShapeCandidate
RefinedTextMember
UnresolvedMember
TextVisualSeparationAuditItem
```

`combined_objects` 只用于审计，`combinedAssetUse=audit_only`。正式 `visualAssets` 只包含 `assetUse=image_asset/icon_asset`，并且 crop 必须来自原始 source PNG。`ShapeCandidate` 不表示已 vectorized。高 text overlap 的 image/icon-like visual member 进入 unresolved；高 text overlap 的 shape-like member 仍可进入 ShapeCandidate，但必须带 `contains_text/text_overlay_shape` risk。

## Run

```bash
cd backend
uv run python scripts/run_m29_0_5_text_aware_visual_object_refinement.py \
  --input "/Users/luhui/Downloads/m28/ChatGPT Image 2026年5月17日 14_47_13 (2).png" \
  --m29-output storage/m29_visual_primitive_graph_audit_20260518_160831
```

输出：

```text
m29_0_5/refined_visual_objects.json
m29_0_5/text_visual_separation_audit.json
m29_0_5/refined_visual_objects.md
m29_0_5/preview_text_aware_refinement.png
m29_0_5/assets/combined_objects/
m29_0_5/assets/visual_assets/
m29_0_5/assets/shape_candidates/
m29_0_5/assets/text_member_previews/
m29_0_5/assets/unresolved_objects/
m29_0_5/assets/split_candidates/
m29_0_5/overlays/
```

## Validation

```bash
cd backend && uv run pytest tests/test_text_aware_visual_object_refinement.py -q
cd backend && uv run pytest tests/test_visual_primitive_graph.py tests/test_symbol_fragment_grouping.py tests/test_text_masked_media_audit.py tests/test_visual_evidence_normalization.py tests/test_visual_object_candidate_audit.py tests/test_text_aware_visual_object_refinement.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```

真实图 smoke 是 diagnostic。验收重点不是 separated 数量，而是：safe visual member 是否进入 formal visual asset，文字是否进入 text member，shape-like 是否进入 shape candidate，图字纠缠是否进入 unresolved，split/wide 是否进入 split_needed。
