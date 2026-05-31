package advisor

import (
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func BuildInput(doc contract.Document) Input {
	input := Input{
		Version:     InputVersion,
		GeneratedAt: timestamp(),
		SourceImage: doc.SourceImage,
		Evidence:    evidenceItems(doc.Evidence),
		Rows:        rowDiagnostics(doc.Root),
		Instructions: AdvisorInstructions{
			Task: "Propose layout grouping relationships for existing evidence only.",
			Must: []string{
				"Use only evidence IDs from this input.",
				"Group elements by layout relationship, not by visual similarity alone.",
				"Keep OCR text unchanged; text is reference only.",
				"Prefer small credible horizontal rows over mega-rows.",
			},
			MustNot: []string{
				"Do not output HTML, CSS, Figma nodes, SVG, images, or coordinates.",
				"Do not invent evidence IDs, text, bboxes, assets, colors, or page content.",
				"Do not use sample names, brands, visible text, or fixed coordinates as rules.",
			},
			OutputShape: `{"version":"layout_advisor_result.v1","groups":[{"id":"group_1","type":"row","direction":"horizontal","evidenceIds":["..."],"expectedGap":12,"confidence":0.8,"reason":"short reason"}],"fallbackEvidenceIds":[],"warnings":[]}`,
		},
	}
	for _, row := range input.Rows {
		if row.Reason != "" {
			input.BadRows = append(input.BadRows, row)
		}
	}
	return input
}

func evidenceItems(items []contract.Evidence) []EvidenceItem {
	out := make([]EvidenceItem, 0, len(items))
	for _, item := range items {
		out = append(out, EvidenceItem{
			ID:         item.ID,
			Kind:       item.Kind,
			RoleHint:   item.RoleHint,
			BBox:       item.BBox,
			Text:       strings.TrimSpace(item.Meta["text"]),
			Source:     item.Source,
			Confidence: item.Confidence,
			SourceRefs: append([]contract.SourceRef(nil), item.SourceRefs...),
		})
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

func rowDiagnostics(root contract.Node) []RowDiagnostic {
	var rows []RowDiagnostic
	var walk func(contract.Node)
	walk = func(node contract.Node) {
		if node.Type == contract.NodeRow {
			rows = append(rows, inspectRow(node))
		}
		for _, child := range node.Children {
			walk(child)
		}
	}
	walk(root)
	sort.SliceStable(rows, func(i, j int) bool {
		a, b := rows[i].BBox, rows[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return rows[i].ID < rows[j].ID
	})
	return rows
}

func inspectRow(node contract.Node) RowDiagnostic {
	flow, overlays := splitRowChildren(node.Children)
	row := RowDiagnostic{
		ID:              node.ID,
		BBox:            node.BBox,
		FlowEvidence:    evidenceIDs(flow),
		OverlayEvidence: evidenceIDs(overlays),
		FlowCount:       len(flow),
		OverlayCount:    len(overlays),
		Gap:             node.Layout.Gap,
		GapVariance:     intMeta(node, "gapVariance"),
		RequiredWidth:   requiredWidth(flow, node.Layout.Gap, node.Layout.Padding),
		YSpread:         ySpread(flow),
		MedianHeight:    medianHeight(flow),
		SourceRefs:      append([]contract.SourceRef(nil), node.SourceRefs...),
	}
	if node.BBox.Width > 0 {
		row.FitRatio = float64(row.RequiredWidth) / float64(node.BBox.Width)
	}
	switch {
	case row.FlowCount == 0:
		row.Reason = "zero_flow_children"
	case row.FlowCount == 1:
		row.Reason = "single_flow_child"
	case row.FitRatio > 1.01:
		row.Reason = "row_required_width_overflow"
	case row.GapVariance > highGapVarianceThreshold(row.Gap):
		row.Reason = "gap_variance_high"
	case row.MedianHeight > 0 && row.YSpread > row.MedianHeight*2:
		row.Reason = "flow_y_spread_high"
	case row.OverlayCount > row.FlowCount*2 && row.OverlayCount >= 3:
		row.Reason = "overlay_dominates_row"
	}
	return row
}

func splitRowChildren(children []contract.Node) ([]contract.Node, []contract.Node) {
	flow := make([]contract.Node, 0, len(children))
	overlays := make([]contract.Node, 0, len(children))
	for _, child := range children {
		if flowLeaf(child) {
			flow = append(flow, child)
			continue
		}
		overlays = append(overlays, child)
	}
	sortNodesByBox(flow)
	sortNodesByBox(overlays)
	return flow, overlays
}

func flowLeaf(node contract.Node) bool {
	if node.Meta["zLayer"] == "text_eraser" {
		return false
	}
	switch node.Type {
	case contract.NodeText, contract.NodeIcon, contract.NodeImage:
		return true
	default:
		return false
	}
}

func evidenceIDs(nodes []contract.Node) []string {
	seen := map[string]bool{}
	var out []string
	for _, node := range nodes {
		for _, ref := range node.SourceRefs {
			if ref.Kind == "layout_evidence" && ref.ID != "" && !seen[ref.ID] {
				seen[ref.ID] = true
				out = append(out, ref.ID)
			}
		}
	}
	sort.Strings(out)
	return out
}

func requiredWidth(nodes []contract.Node, gap int, padding contract.Insets) int {
	if len(nodes) == 0 {
		return padding.Left + padding.Right
	}
	total := padding.Left + padding.Right
	for _, node := range nodes {
		total += node.BBox.Width
	}
	if gap > 0 {
		total += gap * (len(nodes) - 1)
	}
	return total
}

func ySpread(nodes []contract.Node) int {
	if len(nodes) <= 1 {
		return 0
	}
	minY := nodes[0].BBox.Y
	maxY := nodes[0].BBox.Y
	for _, node := range nodes[1:] {
		if node.BBox.Y < minY {
			minY = node.BBox.Y
		}
		if node.BBox.Y > maxY {
			maxY = node.BBox.Y
		}
	}
	return maxY - minY
}

func medianHeight(nodes []contract.Node) int {
	heights := make([]int, 0, len(nodes))
	for _, node := range nodes {
		if node.BBox.Height > 0 {
			heights = append(heights, node.BBox.Height)
		}
	}
	return median(heights)
}

func sortNodesByBox(nodes []contract.Node) {
	sort.SliceStable(nodes, func(i, j int) bool {
		a, b := nodes[i].BBox, nodes[j].BBox
		if a.X != b.X {
			return a.X < b.X
		}
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		return nodes[i].ID < nodes[j].ID
	})
}

func intMeta(node contract.Node, key string) int {
	if node.Meta == nil {
		return 0
	}
	value := strings.TrimSpace(node.Meta[key])
	out := 0
	for _, r := range value {
		if r < '0' || r > '9' {
			return 0
		}
		out = out*10 + int(r-'0')
	}
	return out
}

func highGapVarianceThreshold(gap int) int {
	basis := max(24, gap)
	return basis * basis / 5
}

func unionBoxes(items []EvidenceItem) geometry.Rect {
	var box geometry.Rect
	for _, item := range items {
		box = box.Union(item.BBox)
	}
	return box
}
