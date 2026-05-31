package segment

import (
	"fmt"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

type Result struct {
	Sections  []contract.Node
	Decisions []contract.Decision
}

type Options struct {
	MinSectionEvidence int
}

func Build(bounds geometry.Rect, evidence []contract.Evidence, options Options) Result {
	items := foregroundEvidence(bounds, evidence)
	if len(items) == 0 {
		return Result{}
	}
	if options.MinSectionEvidence <= 0 {
		options.MinSectionEvidence = 2
	}
	anchors := anchorEvidence(items)
	if len(anchors) == 0 {
		anchors = items
	}
	clusters := splitVertical(bounds, anchors, options.MinSectionEvidence)
	clusters = expandClustersWithCoveredEvidence(clusters, items)
	sections := make([]contract.Node, 0, len(clusters))
	decisions := make([]contract.Decision, 0, len(clusters))
	for i, cluster := range clusters {
		box := evidenceUnion(cluster)
		if box.Empty() {
			continue
		}
		id := fmt.Sprintf("section_%04d", i+1)
		sourceRefs := sectionSourceRefs(cluster)
		sections = append(sections, contract.Node{
			ID:   id,
			Type: contract.NodeSection,
			Name: fmt.Sprintf("Section %04d", i+1),
			BBox: box,
			Layout: contract.Layout{
				Mode: contract.LayoutAbsolute,
			},
			SourceRefs:     sourceRefs,
			Confidence:     sectionConfidence(cluster),
			FallbackPolicy: "absolute_group_until_row_column_clustering",
			Meta: map[string]string{
				"evidenceCount": fmt.Sprintf("%d", len(cluster)),
			},
		})
		decisions = append(decisions, contract.Decision{
			ID:         fmt.Sprintf("decision_section_%04d", i+1),
			State:      contract.DecisionSplit,
			NodeID:     id,
			Reason:     "top_level_vertical_gap_segmentation",
			SourceRefs: sourceRefs,
			Score:      sectionConfidence(cluster),
		})
	}
	return Result{Sections: sections, Decisions: decisions}
}

func foregroundEvidence(bounds geometry.Rect, evidence []contract.Evidence) []contract.Evidence {
	out := make([]contract.Evidence, 0, len(evidence))
	minArea := max(8, bounds.Area()/200000)
	for _, item := range evidence {
		if item.BBox.Area() < minArea {
			continue
		}
		if item.RoleHint == "texture_fragment" {
			continue
		}
		box := geometry.Clamp(item.BBox, bounds)
		if box.Empty() {
			continue
		}
		item.BBox = box
		out = append(out, item)
	}
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i].BBox, out[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func anchorEvidence(items []contract.Evidence) []contract.Evidence {
	out := make([]contract.Evidence, 0, len(items))
	for _, item := range items {
		if item.RoleHint == "text" || item.RoleHint == "icon" || item.RoleHint == "line" {
			out = append(out, item)
		}
	}
	return out
}

func expandClustersWithCoveredEvidence(clusters [][]contract.Evidence, items []contract.Evidence) [][]contract.Evidence {
	if len(clusters) <= 1 {
		return clusters
	}
	out := make([][]contract.Evidence, len(clusters))
	seen := make([]map[string]bool, len(clusters))
	boxes := make([]geometry.Rect, len(clusters))
	for i, cluster := range clusters {
		out[i] = append([]contract.Evidence(nil), cluster...)
		seen[i] = map[string]bool{}
		for _, item := range cluster {
			seen[i][item.ID] = true
		}
		boxes[i] = evidenceUnion(cluster)
	}
	for _, item := range items {
		if item.RoleHint == "text" || item.RoleHint == "icon" || item.RoleHint == "line" {
			continue
		}
		best := -1
		bestOverlap := 0
		for i, box := range boxes {
			overlap := item.BBox.Intersect(box).Area()
			if overlap > bestOverlap {
				bestOverlap = overlap
				best = i
			}
		}
		if best < 0 || bestOverlap == 0 || seen[best][item.ID] {
			continue
		}
		out[best] = append(out[best], item)
		seen[best][item.ID] = true
		boxes[best] = boxes[best].Union(item.BBox)
	}
	for _, cluster := range out {
		sort.SliceStable(cluster, func(i, j int) bool {
			a, b := cluster[i].BBox, cluster[j].BBox
			if a.Y != b.Y {
				return a.Y < b.Y
			}
			if a.X != b.X {
				return a.X < b.X
			}
			return cluster[i].ID < cluster[j].ID
		})
	}
	return out
}

func splitVertical(bounds geometry.Rect, items []contract.Evidence, minSectionEvidence int) [][]contract.Evidence {
	if len(items) <= minSectionEvidence {
		return [][]contract.Evidence{items}
	}
	heights := make([]int, 0, len(items))
	for _, item := range items {
		if item.BBox.Height > 0 {
			heights = append(heights, item.BBox.Height)
		}
	}
	unit := median(heights)
	if unit <= 0 {
		unit = max(12, bounds.Height/80)
	}
	gapThreshold := max(12, unit*3/2)
	var clusters [][]contract.Evidence
	current := []contract.Evidence{items[0]}
	currentBottom := items[0].BBox.Bottom()
	for _, item := range items[1:] {
		gap := item.BBox.Y - currentBottom
		if gap >= gapThreshold && len(current) >= minSectionEvidence && remainingCount(items, item.ID) >= minSectionEvidence {
			clusters = append(clusters, current)
			current = []contract.Evidence{item}
			currentBottom = item.BBox.Bottom()
			continue
		}
		current = append(current, item)
		if item.BBox.Bottom() > currentBottom {
			currentBottom = item.BBox.Bottom()
		}
	}
	clusters = append(clusters, current)
	return mergeSmallClusters(clusters, minSectionEvidence)
}

func remainingCount(items []contract.Evidence, startID string) int {
	for i, item := range items {
		if item.ID == startID {
			return len(items) - i
		}
	}
	return 0
}

func mergeSmallClusters(clusters [][]contract.Evidence, minSectionEvidence int) [][]contract.Evidence {
	if len(clusters) <= 1 {
		return clusters
	}
	out := make([][]contract.Evidence, 0, len(clusters))
	for _, cluster := range clusters {
		if len(cluster) >= minSectionEvidence || len(out) == 0 {
			out = append(out, cluster)
			continue
		}
		last := out[len(out)-1]
		last = append(last, cluster...)
		out[len(out)-1] = last
	}
	return out
}

func evidenceUnion(items []contract.Evidence) geometry.Rect {
	var out geometry.Rect
	for _, item := range items {
		out = out.Union(item.BBox)
	}
	return out
}

func sectionSourceRefs(items []contract.Evidence) []contract.SourceRef {
	seen := map[string]bool{}
	refs := make([]contract.SourceRef, 0, len(items))
	for _, item := range items {
		key := item.ID
		if seen[key] {
			continue
		}
		seen[key] = true
		refs = append(refs, contract.SourceRef{
			Kind: "layout_evidence",
			ID:   item.ID,
			Role: "section_member",
		})
	}
	return refs
}

func sectionConfidence(items []contract.Evidence) float64 {
	if len(items) == 0 {
		return 0
	}
	sum := 0.0
	for _, item := range items {
		sum += item.Confidence
	}
	return sum / float64(len(items))
}

func median(values []int) int {
	if len(values) == 0 {
		return 0
	}
	sorted := append([]int(nil), values...)
	sort.Ints(sorted)
	return sorted[len(sorted)/2]
}

func max(a int, b int) int {
	if a > b {
		return a
	}
	return b
}
