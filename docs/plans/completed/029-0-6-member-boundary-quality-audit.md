# M29.0.6 Member Boundary Quality Audit

- 状态：completed
- 创建日期：2026-05-19
- 负责人：Codex

## Goal

M29.0.6 是 M29+ 的 audit-only 归因层。它消费 M29.0.5 refined objects 和 M29.0.4/M29.0.3/M29.0.2 lookup refs，解释 unresolved、weak text-noise dominance、source/member duplicate 和 visual asset duplicate 的来源。

它不减少 unresolved，不修 M29.0.5，不修 M29.0.4，不新增 bbox，不新增 formal visual asset，不删除或合并 duplicate asset，不进入 DSL/Figma/Renderer。

## Contract

主分析全集：

```text
M29.0.5 objects
M29.0.5 unresolvedMembers
M29.0.5 visualAssets
M29.0.5 shapeCandidates
M29.0.5 textMembers
```

lookup only：

```text
M29.0.4 objects/evidenceNodes
M29.0.3 VisualEvidenceItem
M29.0.2 textBoxes
M29.1 group_nodes optional
```

输出 schema：

```text
M2906MemberBoundaryQualityAuditDocument v0.1
```

核心产物：

```text
BoundaryQualityFinding
DuplicateSourceFinding
DuplicateAssetFinding
SuccessBaselineSummary
SuggestedUpstreamLayer
```

summary 必须同时给 raw count 和 dedup count，避免重复消费放大误导。perceptual duplicate 只能是 candidate/uncertain；exact pixel duplicate 才能是 fact。

## Run

单图：

```bash
cd backend
uv run python scripts/run_m29_0_6_member_boundary_quality_audit.py \
  --input "/path/to/source.png" \
  --m29-output storage/m29_batch_smoke_20260518_221638/image_01
```

批量：

```bash
cd backend
uv run python scripts/run_m29_0_6_member_boundary_quality_audit.py \
  --batch-root storage/m29_batch_smoke_20260518_221638 \
  --input-root "/Users/luhui/Downloads/m29"
```

输出：

```text
m29_0_6/member_boundary_quality_audit.json
m29_0_6/member_boundary_quality_audit.md
m29_0_6/unresolved_reason_summary.json
m29_0_6/duplicate_source_audit.json
m29_0_6/duplicate_asset_audit.json
m29_0_6/success_baseline_summary.json
m29_0_6/preview_member_boundary_quality.png
m29_0_6/overlays/
m29_0_6/assets/
m29_0_6_batch_summary.json
m29_0_6_batch_summary.csv
```

## Validation

```bash
cd backend && uv run pytest tests/test_member_boundary_quality_audit.py -q
cd backend && uv run pytest tests/test_visual_primitive_graph.py tests/test_symbol_fragment_grouping.py tests/test_text_masked_media_audit.py tests/test_visual_evidence_normalization.py tests/test_visual_object_candidate_audit.py tests/test_text_aware_visual_object_refinement.py tests/test_member_boundary_quality_audit.py -q
cd backend && uv run pytest
pnpm run check
git diff --check
```

真实图 smoke：

```bash
cd backend
uv run python scripts/run_m29_0_6_member_boundary_quality_audit.py \
  --batch-root storage/m29_batch_smoke_20260518_221638 \
  --input-root "/Users/luhui/Downloads/m29" \
  --overwrite
```

验收重点不是 unresolved 下降，而是 unresolved 和 duplicate 的 raw/dedup 归因、weak text-noise dominance、duplicate source/member topology、duplicate asset facts/candidates 和 success baseline 是否可审计。
