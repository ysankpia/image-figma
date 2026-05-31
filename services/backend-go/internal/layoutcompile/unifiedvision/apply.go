package unifiedvision

import (
	"fmt"
	"sort"
	"strings"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

func Apply(doc contract.Document, validation Validation) contract.Document {
	if len(validation.AcceptedStyles) > 0 {
		doc.Root = applyTextStyles(doc.Root, validation.AcceptedStyles)
	}
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
		node := unifiedGroupNode(i+1, group, children)
		insertUnifiedGroup(&doc.Root, node)
		doc.Decisions = append(doc.Decisions, contract.Decision{
			ID:         fmt.Sprintf("decision_unified_vision_%04d", i+1),
			State:      contract.DecisionGroup,
			NodeID:     node.ID,
			Reason:     "unified_vision_group_accepted",
			SourceRefs: node.SourceRefs,
			Score:      group.Confidence,
		})
	}
	return doc
}

func applyTextStyles(node contract.Node, styles map[string]ElementStyle) contract.Node {
	if node.Type == contract.NodeText {
		for _, ref := range node.SourceRefs {
			if ref.Kind != "layout_evidence" {
				continue
			}
			style, ok := styles[ref.ID]
			if !ok {
				continue
			}
			if validHexColor(style.Color) {
				node.Style.Fill = style.Color
			}
			if node.Meta == nil {
				node.Meta = map[string]string{}
			}
			if style.FontSize > 0 {
				node.Meta["fontSize"] = fmt.Sprintf("%.0f", style.FontSize)
			}
			if value := fontWeightString(style.FontWeight); value != "" {
				node.Meta["fontWeight"] = value
			}
			node.Meta["styleSource"] = "unified_vision"
		}
	}
	for i := range node.Children {
		node.Children[i] = applyTextStyles(node.Children[i], styles)
	}
	return node
}

func fontWeightString(value any) string {
	switch v := value.(type) {
	case string:
		return strings.TrimSpace(v)
	case float64:
		return fmt.Sprintf("%.0f", v)
	case int:
		return fmt.Sprintf("%d", v)
	default:
		return ""
	}
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
		sortNodes(out[id])
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
	sortNodes(children)
	return children
}

func unifiedGroupNode(seq int, group AcceptedGroup, children []contract.Node) contract.Node {
	box := group.BBox
	if box.Empty() {
		box = unionNodes(children)
	}
	nodeType := contract.NodeRow
	layoutMode := contract.LayoutRow
	namePrefix := "Unified Row"
	if group.Direction == "vertical" {
		nodeType = contract.NodeColumn
		layoutMode = contract.LayoutColumn
		namePrefix = "Unified Column"
	}
	return contract.Node{
		ID:   fmt.Sprintf("unified_group_%04d", seq),
		Type: nodeType,
		Name: fmt.Sprintf("%s %04d", namePrefix, seq),
		BBox: box,
		Layout: contract.Layout{
			Mode:  layoutMode,
			Gap:   maxInt(0, group.Gap),
			Align: "center",
		},
		Children:       children,
		SourceRefs:     sourceRefs(group.EvidenceIDs, "unified_vision_group_member"),
		Confidence:     group.Confidence,
		FallbackPolicy: "unified_vision_validated_flat_group",
		Meta: map[string]string{
			"unifiedVisionGroupId": group.GroupID,
			"unifiedVisionBatchId": group.BatchID,
			"fitRatio":             fmt.Sprintf("%.3f", group.FitRatio),
			"requiredSize":         fmt.Sprintf("%d", group.RequiredSize),
			"crossSpread":          fmt.Sprintf("%d", group.CrossSpread),
			"medianCross":          fmt.Sprintf("%d", group.MedianCross),
			"gapVariance":          fmt.Sprintf("%d", group.GapVariance),
			"maxGap":               fmt.Sprintf("%d", group.MaxGap),
		},
	}
}

func insertUnifiedGroup(parent *contract.Node, node contract.Node) {
	best := -1
	bestArea := 0
	for i := range parent.Children {
		child := parent.Children[i]
		if child.Type == contract.NodeRow || child.Type == contract.NodeColumn || !structuralNode(child.Type) {
			continue
		}
		if containerScore(child.BBox, node.BBox) <= 0 {
			continue
		}
		area := child.BBox.Area()
		if best < 0 || area < bestArea {
			best = i
			bestArea = area
		}
	}
	if best >= 0 {
		insertUnifiedGroup(&parent.Children[best], node)
		return
	}
	parent.Children = append(parent.Children, node)
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

func structuralNode(value contract.NodeType) bool {
	switch value {
	case contract.NodePage, contract.NodeSection, contract.NodeGroup, contract.NodeOverlay:
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
