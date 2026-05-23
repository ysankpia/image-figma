# ADR: Define M29 Region Relation Before Clustering

- 状态：accepted
- 日期：2026-05-23

## Context

ADR 0068 defines M29 as a pixel topology and ownership graph. ADR 0069 defines componentization as repeated near-isomorphic relation subgraphs, not raw deduplication.

The next missing contract is smaller and more concrete: before ownership solving, clustering, grouping, or componentization, the system must be able to take two regions and deterministically describe their relation.

This must stay at high-school geometry level first. Do not start from UI labels, design semantics, or component names.

## Decision

M29.3.0 starts by defining a minimal region relation kernel:

```text
relation(A, B) -> {
  primarySetRelation,
  secondaryGeometryRelations
}
```

Input:

```text
A = [x, y, width, height]
B = [x, y, width, height]
```

Output has one primary set relation:

```text
near_equal
contains
contained_by
overlaps
disjoint
```

Output can also include secondary geometry relations:

```text
near
left_of / right_of / above / below
aligned_left / aligned_center_x / aligned_right
aligned_top / aligned_center_y / aligned_bottom
same_width / same_height / same_size
```

The first implementation should use bbox geometry only. Mask-level refinement can be added later, but bbox relation must be stable first.

## Minimal Geometry Definitions

Area:

```text
area(A) = A.width * A.height
```

Intersection:

```text
I = intersection_area(A, B)
```

Containment ratios:

```text
aInB = I / area(A)
bInA = I / area(B)
```

Near equal:

```text
aInB >= 0.90 and bInA >= 0.90
```

Contained by:

```text
aInB >= 0.95
```

Contains:

```text
bInA >= 0.95
```

Overlaps:

```text
I > 0
and not near_equal
and not contains
and not contained_by
```

Near secondary relation:

```text
distance(A, B) <= near_threshold(A, B)
```

Disjoint:

```text
primarySetRelation = disjoint
when I == 0 and not near_equal
```

The near threshold must be relative, not a hardcoded sample-specific pixel number. It must also avoid two opposite failures:

```text
thin regions must not collapse the threshold to a 1px short edge
long separators must not create an unbounded attraction distance
thresholds must be covered by thin horizontal and thin vertical examples
```

The exact formula belongs in the M29.3.0 implementation plan and tests, not in this ADR. The ADR fixes the invariant: near is a secondary geometry relation and its threshold must be relative, thin-aware, and capped.

## Required Evaluation Order

Primary set relation order is part of the contract:

```text
1. near_equal
2. contained_by / contains
3. overlaps
4. disjoint
```

`near_equal` must be evaluated before containment because near-equal regions are mutually high-containment and usually represent the same evidence from different sources, such as OCR bbox and M29 bbox.

Secondary geometry relations are evaluated after the primary set relation. A pair can be:

```text
primarySetRelation = disjoint
secondaryGeometryRelations = ["near", "left_of", "aligned_center_y"]
```

or:

```text
primarySetRelation = contained_by
secondaryGeometryRelations = ["aligned_center_x"]
```

## Definition Of Done

The relation contract is defined when these properties hold:

```text
input is explicit: two bbox regions
output is explicit: one primary set relation and zero or more secondary geometry relations
threshold requirements are explicit
primary evaluation order is explicit
basic examples are stable
```

Basic examples:

```text
two separated rectangles -> disjoint
text bbox inside image bbox -> contained_by
OCR bbox and M29 text bbox almost same -> near_equal
text and icon close in one row -> primary disjoint, secondary near + aligned_center_y
two rectangles partially cover each other -> overlaps
```

## Consequences

M29.3.0 should first provide a generic relation kernel before ownership solving or clustering:

```text
two regions
-> relation(A, B)
```

M29.3.1 can then produce a generic region relation table/report:

```text
source regions
-> pairwise relation(A, B)
-> relation graph
-> later clustering
```

M29.3 must not start with:

```text
SearchBar
ProductCard
BottomNav
Banner
```

Those labels can only appear later as weak role hints after relation evidence exists.

## Boundaries

- Do not implement ownership, cluster logic, or component logic before the base relation kernel is defined and tested.
- Do not use business UI names as relation kinds.
- Do not use fixed screenshot coordinates or fixed sample text.
- Do not treat relation graph output as DSL replay truth by itself.
- Do not run componentization from this stage. This stage only defines the relation language needed by ownership, later clustering, and component matching.
