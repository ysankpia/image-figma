package cluster

import (
	"fmt"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

type Options struct {
	MinRowEvidence int
}

func BuildRows(section contract.Node, evidence []contract.Evidence, options Options) (contract.Node, []contract.Decision) {
	if options.MinRowEvidence <= 0 {
		options.MinRowEvidence = 2
	}
	members := sectionEvidence(section, evidence)
	anchors := rowAnchors(members)
	if len(anchors) == 0 {
		return section, nil
	}
	rows := clusterRows(section.BBox, anchors, options.MinRowEvidence)
	rows = expandRowsWithCoveredEvidence(section.BBox, rows, members)
	if len(rows) == 0 {
		return section, nil
	}
	out := section
	out.Layout.Mode = contract.LayoutColumn
	out.Children = make([]contract.Node, 0, len(rows))
	decisions := make([]contract.Decision, 0, len(rows))
	for i, row := range rows {
		box := evidenceUnion(row)
		if box.Empty() {
			continue
		}
		id := fmt.Sprintf("%s_row_%04d", section.ID, i+1)
		refs := rowSourceRefs(row)
		out.Children = append(out.Children, contract.Node{
			ID:             id,
			Type:           contract.NodeRow,
			Name:           fmt.Sprintf("%s Row %04d", section.Name, i+1),
			BBox:           box,
			Layout:         rowLayout(box, row),
			SourceRefs:     refs,
			Confidence:     averageConfidence(row),
			FallbackPolicy: "row_layout_with_absolute_overlay_fallback",
			Meta: map[string]string{
				"evidenceCount": fmt.Sprintf("%d", len(row)),
				"gapVariance":   fmt.Sprintf("%d", gapVariance(row)),
			},
		})
		decisions = append(decisions, contract.Decision{
			ID:         fmt.Sprintf("decision_%s_row_%04d", section.ID, i+1),
			State:      contract.DecisionGroup,
			NodeID:     id,
			Reason:     "section_anchor_row_clustering",
			SourceRefs: refs,
			Score:      averageConfidence(row),
		})
	}
	return out, decisions
}

func rowLayout(rowBox geometry.Rect, items []contract.Evidence) contract.Layout {
	layoutItems := rowLayoutItems(items)
	return contract.Layout{
		Mode: contract.LayoutRow,
		Gap:  medianPositiveGaps(layoutItems),
		Padding: contract.Insets{
			Top:    max(0, minTop(layoutItems)-rowBox.Y),
			Right:  max(0, rowBox.Right()-maxRight(layoutItems)),
			Bottom: max(0, rowBox.Bottom()-maxBottom(layoutItems)),
			Left:   max(0, minLeft(layoutItems)-rowBox.X),
		},
		Align: "center",
	}
}

func rowLayoutItems(items []contract.Evidence) []contract.Evidence {
	out := make([]contract.Evidence, 0, len(items))
	for _, item := range items {
		if item.RoleHint == "text" || item.RoleHint == "icon" {
			out = append(out, item)
		}
	}
	if len(out) == 0 {
		for _, item := range items {
			if item.RoleHint == "image" {
				out = append(out, item)
			}
		}
	}
	if len(out) == 0 {
		out = append(out, items...)
	}
	sort.SliceStable(out, func(i, j int) bool {
		a, b := out[i].BBox, out[j].BBox
		if a.X != b.X {
			return a.X < b.X
		}
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		return out[i].ID < out[j].ID
	})
	return out
}

func medianPositiveGaps(items []contract.Evidence) int {
	gaps := positiveGaps(items)
	if len(gaps) == 0 {
		return 0
	}
	return median(gaps)
}

func gapVariance(items []contract.Evidence) int {
	gaps := positiveGaps(rowLayoutItems(items))
	if len(gaps) <= 1 {
		return 0
	}
	mean := 0
	for _, gap := range gaps {
		mean += gap
	}
	mean /= len(gaps)
	total := 0
	for _, gap := range gaps {
		delta := gap - mean
		total += delta * delta
	}
	return total / len(gaps)
}

func positiveGaps(items []contract.Evidence) []int {
	gaps := make([]int, 0, len(items)-1)
	for i := 1; i < len(items); i++ {
		gap := items[i].BBox.X - items[i-1].BBox.Right()
		if gap > 0 {
			gaps = append(gaps, gap)
		}
	}
	return gaps
}

func minLeft(items []contract.Evidence) int {
	if len(items) == 0 {
		return 0
	}
	out := items[0].BBox.X
	for _, item := range items[1:] {
		if item.BBox.X < out {
			out = item.BBox.X
		}
	}
	return out
}

func minTop(items []contract.Evidence) int {
	if len(items) == 0 {
		return 0
	}
	out := items[0].BBox.Y
	for _, item := range items[1:] {
		if item.BBox.Y < out {
			out = item.BBox.Y
		}
	}
	return out
}

func maxRight(items []contract.Evidence) int {
	out := 0
	for _, item := range items {
		if item.BBox.Right() > out {
			out = item.BBox.Right()
		}
	}
	return out
}

func maxBottom(items []contract.Evidence) int {
	out := 0
	for _, item := range items {
		if item.BBox.Bottom() > out {
			out = item.BBox.Bottom()
		}
	}
	return out
}

func sectionEvidence(section contract.Node, evidence []contract.Evidence) []contract.Evidence {
	out := make([]contract.Evidence, 0)
	for _, item := range evidence {
		if centerInside(section.BBox, item.BBox) || geometry.IoA(item.BBox, section.BBox) >= 0.50 {
			out = append(out, item)
		}
	}
	sortEvidence(out)
	return out
}

func rowAnchors(items []contract.Evidence) []contract.Evidence {
	out := make([]contract.Evidence, 0, len(items))
	for _, item := range items {
		if item.RoleHint == "text" || item.RoleHint == "icon" || item.RoleHint == "line" {
			out = append(out, item)
		}
	}
	sortEvidence(out)
	return out
}

func clusterRows(sectionBox geometry.Rect, anchors []contract.Evidence, minRowEvidence int) [][]contract.Evidence {
	if len(anchors) <= 1 {
		return [][]contract.Evidence{anchors}
	}
	heights := make([]int, 0, len(anchors))
	for _, item := range anchors {
		heights = append(heights, item.BBox.Height)
	}
	unit := median(heights)
	if unit <= 0 {
		unit = max(10, sectionBox.Height/30)
	}
	centerTolerance := max(6, unit*2/3)
	rows := [][]contract.Evidence{}
	rowCenters := []int{}
	for _, item := range anchors {
		center := item.BBox.Y + item.BBox.Height/2
		best := -1
		bestDelta := 0
		for i, rowCenter := range rowCenters {
			delta := abs(center - rowCenter)
			if delta <= centerTolerance && (best < 0 || delta < bestDelta) {
				best = i
				bestDelta = delta
			}
		}
		if best < 0 {
			rows = append(rows, []contract.Evidence{item})
			rowCenters = append(rowCenters, center)
			continue
		}
		rows[best] = append(rows[best], item)
		rowCenters[best] = averageCenterY(rows[best])
	}
	rows = mergeSparseRows(rows, minRowEvidence, centerTolerance)
	for _, row := range rows {
		sortEvidence(row)
	}
	sort.SliceStable(rows, func(i, j int) bool {
		return evidenceUnion(rows[i]).Y < evidenceUnion(rows[j]).Y
	})
	return rows
}

func mergeSparseRows(rows [][]contract.Evidence, minRowEvidence int, tolerance int) [][]contract.Evidence {
	if len(rows) <= 1 {
		return rows
	}
	sort.SliceStable(rows, func(i, j int) bool {
		return evidenceUnion(rows[i]).Y < evidenceUnion(rows[j]).Y
	})
	out := make([][]contract.Evidence, 0, len(rows))
	for _, row := range rows {
		if len(row) >= minRowEvidence || len(out) == 0 {
			out = append(out, row)
			continue
		}
		last := out[len(out)-1]
		if evidenceUnion(row).Y-evidenceUnion(last).Bottom() <= max(tolerance, 12) {
			last = append(last, row...)
			out[len(out)-1] = last
			continue
		}
		out = append(out, row)
	}
	return out
}

func expandRowsWithCoveredEvidence(sectionBox geometry.Rect, rows [][]contract.Evidence, items []contract.Evidence) [][]contract.Evidence {
	if len(rows) == 0 {
		return rows
	}
	out := make([][]contract.Evidence, len(rows))
	seen := make([]map[string]bool, len(rows))
	boxes := make([]geometry.Rect, len(rows))
	for i, row := range rows {
		out[i] = append([]contract.Evidence(nil), row...)
		seen[i] = map[string]bool{}
		for _, item := range row {
			seen[i][item.ID] = true
		}
		boxes[i] = evidenceUnion(row)
	}
	for _, item := range items {
		if item.RoleHint == "text" || item.RoleHint == "icon" || item.RoleHint == "line" {
			continue
		}
		if !centerInside(sectionBox, item.BBox) && geometry.IoA(item.BBox, sectionBox) < 0.50 {
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
		nextBox := boxes[best].Union(item.BBox)
		if geometry.IoA(nextBox, sectionBox) < 1 {
			continue
		}
		out[best] = append(out[best], item)
		seen[best][item.ID] = true
		boxes[best] = boxes[best].Union(item.BBox)
	}
	for _, row := range out {
		sortEvidence(row)
	}
	return out
}

func centerInside(container geometry.Rect, child geometry.Rect) bool {
	if container.Empty() || child.Empty() {
		return false
	}
	cx := child.X + child.Width/2
	cy := child.Y + child.Height/2
	return cx >= container.X && cx <= container.Right() && cy >= container.Y && cy <= container.Bottom()
}

func rowSourceRefs(items []contract.Evidence) []contract.SourceRef {
	seen := map[string]bool{}
	refs := make([]contract.SourceRef, 0, len(items))
	for _, item := range items {
		if seen[item.ID] {
			continue
		}
		seen[item.ID] = true
		refs = append(refs, contract.SourceRef{
			Kind: "layout_evidence",
			ID:   item.ID,
			Role: "row_member",
		})
	}
	return refs
}

func sortEvidence(items []contract.Evidence) {
	sort.SliceStable(items, func(i, j int) bool {
		a, b := items[i].BBox, items[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return items[i].ID < items[j].ID
	})
}

func evidenceUnion(items []contract.Evidence) geometry.Rect {
	var out geometry.Rect
	for _, item := range items {
		out = out.Union(item.BBox)
	}
	return out
}

func averageConfidence(items []contract.Evidence) float64 {
	if len(items) == 0 {
		return 0
	}
	total := 0.0
	for _, item := range items {
		total += item.Confidence
	}
	return total / float64(len(items))
}

func averageCenterY(items []contract.Evidence) int {
	if len(items) == 0 {
		return 0
	}
	total := 0
	for _, item := range items {
		total += item.BBox.Y + item.BBox.Height/2
	}
	return total / len(items)
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

func abs(value int) int {
	if value < 0 {
		return -value
	}
	return value
}
