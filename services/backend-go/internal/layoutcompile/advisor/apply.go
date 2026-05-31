package advisor

import (
	"fmt"
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func Apply(doc contract.Document, validation Validation) contract.Document {
	if len(validation.AcceptedGroups) == 0 {
		return doc
	}
	acceptedIDs := acceptedEvidenceIDs(validation.AcceptedGroups)
	var removed []contract.Node
	doc.Root = removeAcceptedLeaves(doc.Root, acceptedIDs, &removed)
	leavesByEvidence := mapLeavesByEvidence(removed)
	for i, group := range validation.AcceptedGroups {
		children := childrenForGroup(group.EvidenceIDs, leavesByEvidence)
		if len(children) < 2 {
			continue
		}
		row := advisorRow(i+1, group, children)
		insertAdvisorRow(&doc.Root, row)
		doc.Decisions = append(doc.Decisions, contract.Decision{
			ID:         fmt.Sprintf("decision_layout_advisor_%04d", i+1),
			State:      contract.DecisionGroup,
			NodeID:     row.ID,
			Reason:     "layout_advisor_group_accepted",
			SourceRefs: row.SourceRefs,
			Score:      group.Confidence,
		})
	}
	return doc
}

func acceptedEvidenceIDs(groups []AcceptedGroup) map[string]bool {
	out := map[string]bool{}
	for _, group := range groups {
		for _, id := range group.EvidenceIDs {
			out[id] = true
		}
	}
	return out
}

func removeAcceptedLeaves(node contract.Node, accepted map[string]bool, removed *[]contract.Node) contract.Node {
	children := make([]contract.Node, 0, len(node.Children))
	for _, child := range node.Children {
		if leafNode(child) {
			if flowLeaf(child) && nodeHasAcceptedEvidence(child, accepted) {
				*removed = append(*removed, child)
				continue
			}
			children = append(children, child)
			continue
		}
		next := removeAcceptedLeaves(child, accepted, removed)
		if emptyStructuralRow(next) {
			continue
		}
		if overlayOnlyRow(next) {
			children = append(children, next.Children...)
			continue
		}
		children = append(children, next)
	}
	node.Children = children
	return node
}

func nodeHasAcceptedEvidence(node contract.Node, accepted map[string]bool) bool {
	for _, ref := range node.SourceRefs {
		if ref.Kind == "layout_evidence" && accepted[ref.ID] {
			return true
		}
	}
	return false
}

func emptyStructuralRow(node contract.Node) bool {
	return node.Type == contract.NodeRow && len(node.Children) == 0
}

func overlayOnlyRow(node contract.Node) bool {
	if node.Type != contract.NodeRow || len(node.Children) == 0 {
		return false
	}
	for _, child := range node.Children {
		if flowLeaf(child) {
			return false
		}
	}
	return true
}

func mapLeavesByEvidence(nodes []contract.Node) map[string][]contract.Node {
	out := map[string][]contract.Node{}
	for _, node := range nodes {
		for _, ref := range node.SourceRefs {
			if ref.Kind != "layout_evidence" || ref.ID == "" {
				continue
			}
			out[ref.ID] = append(out[ref.ID], node)
		}
	}
	for id := range out {
		sortNodesByBox(out[id])
	}
	return out
}

func childrenForGroup(ids []string, leaves map[string][]contract.Node) []contract.Node {
	var children []contract.Node
	seen := map[string]bool{}
	for _, id := range ids {
		for _, node := range leaves[id] {
			if seen[node.ID] {
				continue
			}
			seen[node.ID] = true
			children = append(children, node)
		}
	}
	sortNodesByBox(children)
	return children
}

func advisorRow(seq int, group AcceptedGroup, children []contract.Node) contract.Node {
	box := group.BBox
	if box.Empty() {
		box = nodeUnion(children)
	}
	refs := make([]contract.SourceRef, 0, len(group.EvidenceIDs))
	for _, id := range group.EvidenceIDs {
		refs = append(refs, contract.SourceRef{
			Kind: "layout_evidence",
			ID:   id,
			Role: "layout_advisor_row_member",
		})
	}
	return contract.Node{
		ID:   fmt.Sprintf("advisor_row_%04d", seq),
		Type: contract.NodeRow,
		Name: fmt.Sprintf("Advisor Row %04d", seq),
		BBox: box,
		Layout: contract.Layout{
			Mode:  contract.LayoutRow,
			Gap:   max(0, group.ExpectedGap),
			Align: "center",
		},
		Children:       children,
		SourceRefs:     refs,
		Confidence:     group.Confidence,
		FallbackPolicy: "layout_advisor_validated_row",
		Meta: map[string]string{
			"advisorGroupId": group.GroupID,
			"fitRatio":       fmt.Sprintf("%.3f", group.FitRatio),
			"requiredWidth":  fmt.Sprintf("%d", group.RequiredWidth),
			"ySpread":        fmt.Sprintf("%d", group.YSpread),
			"medianHeight":   fmt.Sprintf("%d", group.MedianHeight),
		},
	}
}

func insertAdvisorRow(parent *contract.Node, row contract.Node) {
	best := -1
	bestArea := 0
	for i := range parent.Children {
		child := parent.Children[i]
		if child.Type == contract.NodeRow || !structuralNode(child.Type) {
			continue
		}
		if containerScore(child.BBox, row.BBox) <= 0 {
			continue
		}
		area := child.BBox.Area()
		if best < 0 || area < bestArea {
			best = i
			bestArea = area
		}
	}
	if best >= 0 {
		insertAdvisorRow(&parent.Children[best], row)
		return
	}
	parent.Children = append(parent.Children, row)
	sort.SliceStable(parent.Children, func(i, j int) bool {
		a, b := parent.Children[i].BBox, parent.Children[j].BBox
		if a.Y != b.Y {
			return a.Y < b.Y
		}
		if a.X != b.X {
			return a.X < b.X
		}
		return parent.Children[i].ID < parent.Children[j].ID
	})
}

func nodeUnion(nodes []contract.Node) geometry.Rect {
	var box geometry.Rect
	for _, node := range nodes {
		box = box.Union(node.BBox)
	}
	return box
}

func containerScore(container geometry.Rect, child geometry.Rect) float64 {
	ioa := geometry.IoA(child, container)
	if centerInside(container, child) {
		return 2 + ioa
	}
	if ioa >= 0.50 {
		return ioa
	}
	return 0
}

func centerInside(container geometry.Rect, child geometry.Rect) bool {
	if container.Empty() || child.Empty() {
		return false
	}
	cx := child.X + child.Width/2
	cy := child.Y + child.Height/2
	return cx >= container.X && cx <= container.Right() && cy >= container.Y && cy <= container.Bottom()
}

func structuralNode(value contract.NodeType) bool {
	switch value {
	case contract.NodePage, contract.NodeSection, contract.NodeColumn, contract.NodeGroup, contract.NodeOverlay:
		return true
	default:
		return false
	}
}

func leafNode(node contract.Node) bool {
	switch node.Type {
	case contract.NodePage, contract.NodeSection, contract.NodeRow, contract.NodeColumn, contract.NodeGroup, contract.NodeOverlay:
		return false
	default:
		return true
	}
}
