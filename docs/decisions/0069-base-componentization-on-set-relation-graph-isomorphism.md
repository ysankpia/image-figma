# ADR: Base Componentization On Set-Relation Graph Isomorphism

- 状态：accepted
- 日期：2026-05-23

## Context

M29 pixel topology discussion clarified that componentization must not be treated as a late deduplication pass.

The wrong abstraction is:

```text
find duplicated pixels
-> delete duplicates
-> call the rest components
```

That is not componentization. It destroys instance differences and can merge unrelated objects just because their pixels or bboxes look similar.

The correct source layer is the M29 set-relation graph:

```text
Primitive = pixel set
Relation = set relation + geometry relation + appearance relation
Cluster = local stable relation subgraph
Component candidate = repeated near-isomorphic cluster graph
Component = template + slots + instances + overrides
```

## Decision

Future componentization must be based on relation-graph similarity, not UI class names and not raw pixel deduplication.

The minimum componentization model is:

```text
component template:
  stable internal relation graph
  ordered slots
  layout constraints inferred from repeated instances

component instance:
  reference to template
  bbox / transform
  slot overrides
  text/image/style differences
```

Two clusters can become instances of the same component only when their internal relation graphs are near-isomorphic:

```text
same or compatible child owner types
similar containment graph
similar relative positions
similar alignment pattern
similar directed flow relations
similar repeated spacing
compatible aspect ratios and sizes
slot-to-slot matching can be established
instance differences can be represented as overrides
```

This means componentization is not:

```text
same pixels
same text
same business role
same UI label
```

Componentization is:

```text
same structure
different content
explicit slots
controlled overrides
```

## Set And Geometry Relation Base

High-school set relations are sufficient as the first layer of internal object relations:

```text
disjoint
overlaps
contains
contained_by
near_equal
```

UI structure also requires geometric and appearance relations on top of those sets:

```text
near
above / below / left_of / right_of
aligned_left / aligned_center_x / aligned_right
aligned_top / aligned_center_y / aligned_bottom
same_size
same_aspect_ratio
same_gap_sequence
similar_color
similar_texture
covering / protected_by
```

These are still generic relations. They do not require naming a SearchBar, ProductCard, BottomNav, Banner, or any app-specific component.

Directed geometry relations are mandatory for component matching. A horizontal `icon left_of text` cluster and a vertical `icon above text` cluster can have the same child types and the same undirected adjacency, but they are not the same component structure for layout replay.

Near-isomorphism must therefore preserve directed spatial attributes:

```text
left_of / right_of / above / below
aligned_center_y / aligned_center_x
aligned_left / aligned_top / aligned_right / aligned_bottom
flow_axis = horizontal | vertical | mixed
```

## Consequences

M29.3 should be treated as a generic set-relation graph stage, not a UI object graph with named component detectors.

M29.4 should find stable clusters from that graph:

```text
objects strongly related by containment, adjacency, alignment, repeated rhythm, and shared parent background
```

Only after M29.4 can a later component stage compare clusters for near-isomorphism and extract:

```text
template
slots
instances
overrides
```

Role hints are allowed only after the graph evidence exists. A repeated icon+text edge cluster can later receive a weak `roleHint`, but the truth source remains the relation graph and ownership decisions.

## Boundaries

- Do not implement componentization as raw deduplication.
- Do not infer components from fixed UI class names.
- Do not merge clusters unless slot matching is explainable.
- Do not drop instance differences; preserve them as overrides.
- Do not let model output directly define component templates.
- Do not run componentization before pixel ownership and relation graph are stable.

## Follow-Up Path

The ordering remains:

```text
M29.3.0 Region Relation Kernel
-> M29.2.1 Pixel Ownership Consistency
-> M29.3.1 Generic Set-Relation Graph Report
-> M29.4 Stable Design Cluster
-> component candidate isomorphism / slot alignment
-> component template and instance replay
```

This keeps componentization grounded in the same first-principles pipeline as M29: pixels become sets, sets become relations, relations become clusters, repeated near-isomorphic clusters become components.
