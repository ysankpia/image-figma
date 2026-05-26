# 05 M29.4 Weak Structure

## Source Truth

M29.4 consumes M29.3 relation graph nodes and edges:

```text
m29_3/region_relation_graph_report.json
```

Primary package:

```text
backend/app/stable_design_cluster/
```

Runtime entrypoint:

```text
backend/app/stable_design_cluster/pipeline.py:17
```

First-principles role:

```text
M29.4 groups existing relation edges into weak structural evidence.
It is not a component detector.
It is not a materializer.
It cannot create source objects or decide cleanup.
```

## Input Artifacts

```text
M2931RegionRelationGraphReport.nodes
M2931RegionRelationGraphReport.edges
```

Pipeline flow:

```text
normalize nodes
normalize edges
group edges by motif
build connected-component candidates
build/dedupe clusters
write stable_design_cluster_report.json
```

Code evidence:

```text
backend/app/stable_design_cluster/pipeline.py:27-34
```

## Output Artifacts

Primary output:

```text
m29_4/stable_design_cluster_report.json
```

Cluster fields:

```text
id
bbox
memberNodeIds
edgeIds
clusterPattern
roleHint
stabilityScore
repeatabilityScore
reasons
risks
```

Report-only validation:

```text
dslChanged = false
assetChanged = false
createdVisibleNodeCount = 0
componentChanged = false
roleHintsAreWeakStructuralEvidence = true
```

Code evidence:

```text
backend/app/stable_design_cluster/pipeline.py:41-77
backend/app/stable_design_cluster/validation.py
```

## Decision Authority

### This layer can decide

M29.4 can decide:

```text
clusterPattern:
  containment_anchor_subgraph
  directed_row_subgraph
  directed_column_subgraph
  repeated_size_subgraph
  stable_local_relation_subgraph

weak roleHint:
  background_anchor_like
  row_like
  column_like
  repeated_item_like

stabilityScore
repeatabilityScore
cluster membership
```

### This layer must not decide

M29.4 must not decide:

```text
source ownership
visible replay
cleanup targets
component creation
Auto Layout
button/tab/action-row materialization
internal source promotion
transparent asset use
```

This is explicitly encoded in validation and docs.

## Main Formulas And Gates

### Motif classification

M29.4 classifies relation edges into motifs:

```text
same size + near -> repeated_size_subgraph / repeated_item_like
contains or contained_by -> containment_anchor_subgraph / background_anchor_like
horizontal direction + vertical alignment -> directed_row_subgraph / row_like
vertical direction + horizontal alignment -> directed_column_subgraph / column_like
near_equal / overlaps / near -> stable_local_relation_subgraph
media-text overlap/near -> containment_anchor_subgraph / background_anchor_like
```

Code evidence:

```text
backend/app/stable_design_cluster/motifs.py:8-51
```

Important negative rule:

```text
media + text pair is background_anchor_like,
not media_text_group_like.
```

Code evidence:

```text
backend/app/stable_design_cluster/motifs.py:47-56
backend/tests/test_stable_design_cluster.py::test_m294_media_text_pair_remains_background_anchor_not_media_text_component
```

### Connected components

For each motif, M29.4 builds graph connected components over relation edges:

```text
same motif edges -> union-find connected components -> motif candidates
```

Code evidence:

```text
backend/app/stable_design_cluster/candidates.py:6-28
backend/app/stable_design_cluster/candidates.py:31-68
```

This is generic graph math. It does not key on text, brand, color, coordinates, or one screenshot.

### Cluster acceptance

M29.4 accepts a cluster when:

```text
member count >= 2
member count <= max_cluster_members
has internal structural edges
stabilityScore >= min_stability_score
```

Code evidence:

```text
backend/app/stable_design_cluster/clusters.py:28-59
backend/app/stable_design_cluster/types.py:43-49
```

Defaults:

```text
max_cluster_members = 12
min_stability_score = 0.55
duplicate_bbox_iou_threshold = 0.92
duplicate_member_overlap_threshold = 0.85
```

### Stability score

M29.4 scores clusters using edge density, member confidence, primary relation signal, and repeatability:

```text
edgeDensity = internalEdges / possibleEdges
confidenceScore = average(member confidence)
primarySignal = non-disjoint internal edge ratio
repeatabilityScore = owner repeat + size repeat + repeated edge ratio
```

Pattern-specific formulas:

```text
repeated_size_subgraph:
  0.62 + repeatability * 0.22 + edgeDensity * 0.08 + confidence * 0.08

containment_anchor_subgraph:
  0.68 + primarySignal * 0.15 + confidence * 0.12 + edgeDensity * 0.05

row/column:
  0.58 + edgeDensity * 0.12 + confidence * 0.16 + primarySignal * 0.08

local:
  0.80 + confidence * 0.08 + primarySignal * 0.06 + edgeDensity * 0.06
```

Code evidence:

```text
backend/app/stable_design_cluster/scoring.py:8-27
```

## Information Loss

### Loss 1: Weak structure cannot introduce missing children

If an action row has four labels but only three icons made it into M29.2 after promotion:

```text
M29.4 can cluster the existing objects,
but cannot invent the fourth icon.
```

The missing object owner remains upstream M29.6/transparent/evidence/promotion.

### Loss 2: Role hints are intentionally weak

M29.4 does not output:

```text
button
tab_item
action_row_item
search_field
table_cell_marker
selected_state
```

It only outputs:

```text
row_like
column_like
repeated_item_like
background_anchor_like
```

This avoids premature semantic materialization, but it also means Codia-like structure needs a later evidence contract or candidate report to translate weak motifs into controlled structure.

### Loss 3: Media-text pair deliberately avoids a strong component role

The test explicitly ensures media/text pair does not become `media_text_group_like`. This avoids false components, but it also leaves media-contained controls without a direct group proof at M29.4.

## Known Failure Symptoms Mapped To This Layer

### Four action labels, only three icons

M29.4 may still create row/repeated clusters from existing members. It cannot repair the missing fourth icon because it has no source object for that icon.

### Google button text exists but icon/background not draggable

M29.4 can only see whatever M29.2/promotion provided. If the icon/background was never promoted, M29.4 cannot create it.

### Bottom tab indicator is diagnostic-only

If the selected indicator is not a visible source object, it cannot become a cluster member except as diagnostic evidence. M29.4 does not have a selected-state marker role.

## Tests / Guards

Direct tests:

```text
backend/tests/test_stable_design_cluster.py
```

Important guards:

```text
test_m294_empty_report_is_read_only
test_m294_containment_chain_becomes_stable_background_anchor_cluster
test_m294_row_and_column_clusters_keep_directionality
test_m294_repeated_local_subgraph_scores_repeatability
test_m294_media_text_pair_remains_background_anchor_not_media_text_component
```

Contract matrix:

```text
M29-CR-022..025
```

## Findings

### P2: M29.4 is correctly report-only, but too weak to prove Codia-like controls

Evidence:

```text
backend/app/stable_design_cluster/pipeline.py:62-70
backend/app/stable_design_cluster/validation.py
backend/app/stable_design_cluster/motifs.py:59-66
```

Judgment:

```text
This is the right safety boundary. But Codia-like output needs a later contract that can use weak clusters plus source evidence to propose real control/action-row/tab structures.
```

Recommended next action:

```text
Do not make M29.4 create groups/components. Let hierarchy/sibling/layout/evidence layers consume it, with repair-cost gates.
```

### P2: Media-text grouping is explicitly downgraded

Evidence:

```text
backend/app/stable_design_cluster/motifs.py:47-56
backend/tests/test_stable_design_cluster.py::test_m294_media_text_pair_remains_background_anchor_not_media_text_component
```

Judgment:

```text
This avoids a common false-positive. But it also means button-like media with text still needs a separate internal control/background path.
```

Recommended next action:

```text
Audit M29.6 and later reports for internal control/background evidence, not just icon evidence.
```

### P2: Stability scoring is generic but threshold-heavy

Evidence:

```text
backend/app/stable_design_cluster/scoring.py:8-39
backend/app/stable_design_cluster/types.py:43-49
```

Judgment:

```text
These are not sample-specific rules. They are broad graph heuristics. They still belong in the heuristic ledger because they shape whether repeated rows/groups are visible to later stages.
```

Recommended next action:

```text
Record scoring formulas in the specialization ledger with tests and known non-goals.
```

## Recommended Next Action

Continue to M29.5 replay plan:

```text
Verify the only source of visible replay and cleanup authorization, especially for promoted internal icons and copied image asset cleanup.
```
