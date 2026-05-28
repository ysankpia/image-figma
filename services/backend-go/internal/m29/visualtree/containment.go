package visualtree

import (
	"sort"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/contract"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/evidence"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/m29/relation"
)

const containmentTolerance = 3

func applyContainmentTree(root *Node, relations []relation.Relation, tokens map[string]evidence.Token) ContainmentReport {
	bodyBefore := len(root.Children)
	oldParentByID := map[string]string{}
	flattenParentRefs(root, "", oldParentByID)

	nodes := flattenDetachedChildren(root)
	nodeByID := map[string]*Node{}
	for i := range nodes {
		nodes[i].Children = nil
		nodes[i].Meta.ParentReason = ""
		nodeByID[nodes[i].ID] = &nodes[i]
	}

	rels := relationIndex(relations)
	parentByID := chooseContainmentParents(root, nodes, tokens, rels)
	childrenByParent := map[string][]string{}
	for _, node := range nodes {
		parentID := parentByID[node.ID]
		if parentID == "" {
			parentID = root.ID
		}
		childrenByParent[parentID] = append(childrenByParent[parentID], node.ID)
	}
	for parentID := range childrenByParent {
		sort.SliceStable(childrenByParent[parentID], func(i, j int) bool {
			return lessNode(*nodeByID[childrenByParent[parentID][i]], *nodeByID[childrenByParent[parentID][j]])
		})
	}

	var decisions []ContainmentDecision
	for _, node := range nodes {
		oldParentID := oldParentByID[node.ID]
		newParentID := parentByID[node.ID]
		if newParentID == "" {
			newParentID = root.ID
		}
		if oldParentID == newParentID {
			continue
		}
		parent := nodeForParent(root, nodeByID, newParentID)
		relationIDs := structuralRelationIDs(newParentID, node.ID, rels)
		reason := "bbox_containment"
		if len(relationIDs) > 0 {
			reason = "relation_contains"
		}
		decisions = append(decisions, ContainmentDecision{
			NodeID:        node.ID,
			OldParentID:   oldParentID,
			NewParentID:   newParentID,
			NewParentKind: parentKind(parent),
			Reason:        reason,
			BBoxCoverage:  round4(bboxCoverage(parent.BBox, node.BBox)),
			RelationIDs:   relationIDs,
			Decision:      "allow",
		})
	}
	sort.SliceStable(decisions, func(i, j int) bool {
		if decisions[i].NewParentID != decisions[j].NewParentID {
			return decisions[i].NewParentID < decisions[j].NewParentID
		}
		return decisions[i].NodeID < decisions[j].NodeID
	})

	root.Children = buildContainmentChildren(root.ID, childrenByParent, nodeByID, rels, tokens)
	finalizeNodeTypes(root, tokens)
	refreshTreeLayouts(root)

	report := ContainmentReport{
		BodyChildCountBefore: bodyBefore,
		BodyChildCountAfter:  len(root.Children),
		CandidateCount:       len(decisions),
		AppliedCount:         len(decisions),
		Decisions:            decisions,
	}
	for _, decision := range decisions {
		if len(decision.RelationIDs) > 0 {
			report.RelationParentCount++
		} else {
			report.ContainmentOnlyParentCount++
		}
	}
	return report
}

func chooseContainmentParents(root *Node, nodes []Node, tokens map[string]evidence.Token, rels indexedRelations) map[string]string {
	parentByID := map[string]string{}
	for _, node := range nodes {
		parentID := root.ID
		parentArea := area(root.BBox) + 1
		for i := range nodes {
			candidate := nodes[i]
			if candidate.ID == node.ID {
				continue
			}
			if !canNodeContain(candidate, tokens) {
				continue
			}
			candidateArea := area(candidate.BBox)
			if candidateArea <= area(node.BBox) || candidateArea >= parentArea {
				continue
			}
			if !hasStructuralRelation(candidate.ID, node.ID, rels) && !bboxContains(candidate.BBox, node.BBox, containmentTolerance) {
				continue
			}
			parentID = candidate.ID
			parentArea = candidateArea
		}
		parentByID[node.ID] = parentID
	}
	return parentByID
}

func buildContainmentChildren(
	parentID string,
	childrenByParent map[string][]string,
	nodeByID map[string]*Node,
	rels indexedRelations,
	tokens map[string]evidence.Token,
) []Node {
	children := make([]Node, 0, len(childrenByParent[parentID]))
	for _, childID := range childrenByParent[parentID] {
		source := nodeByID[childID]
		if source == nil {
			continue
		}
		child := *source
		child.Children = buildContainmentChildren(child.ID, childrenByParent, nodeByID, rels, tokens)
		child.SourceRefs.RelationIDs = mergeStrings(child.SourceRefs.RelationIDs, structuralRelationIDs(parentID, child.ID, rels))
		if parentID != "body_0001" {
			child.Meta.ParentReason = parentReason(parentID, child.ID, rels)
		}
		children = append(children, child)
	}
	return children
}

func parentReason(parentID string, childID string, rels indexedRelations) string {
	if hasStructuralRelation(parentID, childID, rels) {
		return "relation_contains"
	}
	return "bbox_containment"
}

func hasStructuralRelation(parentID string, childID string, rels indexedRelations) bool {
	return len(structuralRelationIDs(parentID, childID, rels)) > 0
}

func structuralRelationIDs(parentID string, childID string, rels indexedRelations) []string {
	return relationIDs(rels.find(parentID, childID, "contains", "inside_surface", "foreground_inside_background"))
}

func finalizeNodeTypes(node *Node, tokens map[string]evidence.Token) {
	if token, ok := singleSourceToken(*node, tokens); ok {
		node.Type = nodeTypeForToken(token, len(node.Children) > 0)
		node.Name = node.Type + " / " + node.ID
		if token.TokenType == "raster_region_token" && node.Type == "Layer" {
			node.Style.BackgroundRef = token.ID
			node.SourceRefs.BackgroundIDs = []string{token.ID}
		}
		if token.TokenType == "raster_region_token" && node.Type == "Image" {
			node.Style.BackgroundRef = ""
			node.SourceRefs.BackgroundIDs = nil
		}
		if node.Type == "Text" {
			node.Content.Text = token.Content.Text
		}
	}
	for i := range node.Children {
		finalizeNodeTypes(&node.Children[i], tokens)
	}
}

func singleSourceToken(node Node, tokens map[string]evidence.Token) (evidence.Token, bool) {
	if len(node.SourceRefs.TokenIDs) != 1 {
		return evidence.Token{}, false
	}
	token, ok := tokens[node.SourceRefs.TokenIDs[0]]
	return token, ok
}

func flattenDetachedChildren(root *Node) []Node {
	var out []Node
	var walk func(Node)
	walk = func(node Node) {
		for _, child := range node.Children {
			out = append(out, child)
			walk(child)
		}
	}
	walk(*root)
	return out
}

func flattenParentRefs(node *Node, parentID string, parentByID map[string]string) {
	parentByID[node.ID] = parentID
	for i := range node.Children {
		flattenParentRefs(&node.Children[i], node.ID, parentByID)
	}
}

func canNodeContain(node Node, tokens map[string]evidence.Token) bool {
	if node.Type == "Body" {
		return true
	}
	if node.Type == "Layer" {
		return true
	}
	if token, ok := singleSourceToken(node, tokens); ok {
		return canContain(token)
	}
	return false
}

func bboxContains(parent, child contract.BBox, tolerance int) bool {
	return parent.X-tolerance <= child.X &&
		parent.Y-tolerance <= child.Y &&
		parent.X+parent.Width+tolerance >= child.X+child.Width &&
		parent.Y+parent.Height+tolerance >= child.Y+child.Height
}

func nodeForParent(root *Node, nodeByID map[string]*Node, parentID string) Node {
	if parentID == root.ID || parentID == "" {
		return *root
	}
	if node := nodeByID[parentID]; node != nil {
		return *node
	}
	return *root
}

func parentKind(node Node) string {
	if node.Type == "Body" {
		return "body"
	}
	if node.Meta.Synthetic {
		return "synthetic_" + node.Meta.GroupKind
	}
	return "layer"
}

type indexedRelations struct {
	byPair map[string][]relation.Relation
}

func relationIndex(relations []relation.Relation) indexedRelations {
	byPair := map[string][]relation.Relation{}
	for _, rel := range relations {
		byPair[pairKey(rel.FromID, rel.ToID)] = append(byPair[pairKey(rel.FromID, rel.ToID)], rel)
		byPair[pairKey(rel.ToID, rel.FromID)] = append(byPair[pairKey(rel.ToID, rel.FromID)], rel)
	}
	return indexedRelations{byPair: byPair}
}

func (idx indexedRelations) find(a string, b string, types ...string) []relation.Relation {
	want := map[string]bool{}
	for _, t := range types {
		want[t] = true
	}
	var out []relation.Relation
	for _, rel := range idx.byPair[pairKey(a, b)] {
		if want[rel.RelationType] {
			out = append(out, rel)
		}
	}
	return out
}

func pairKey(a string, b string) string {
	return a + "\x00" + b
}

func relationIDs(relations []relation.Relation) []string {
	ids := map[string]bool{}
	for _, rel := range relations {
		ids[rel.ID] = true
	}
	return sortedKeys(ids)
}

func bboxCoverage(parent, child contract.BBox) float64 {
	childArea := area(child)
	if childArea == 0 {
		return 0
	}
	return float64(intersection(parent, child)) / float64(childArea)
}

func intersection(a, b contract.BBox) int {
	x1 := max(a.X, b.X)
	y1 := max(a.Y, b.Y)
	x2 := min(a.X+a.Width, b.X+b.Width)
	y2 := min(a.Y+a.Height, b.Y+b.Height)
	return area(contract.BBox{X: x1, Y: y1, Width: x2 - x1, Height: y2 - y1})
}

func mergeStrings(a []string, b []string) []string {
	seen := map[string]bool{}
	for _, value := range a {
		seen[value] = true
	}
	for _, value := range b {
		seen[value] = true
	}
	return sortedKeys(seen)
}

func refreshTreeLayouts(node *Node) {
	refreshChildLayouts(node)
	for i := range node.Children {
		refreshTreeLayouts(&node.Children[i])
	}
}

func round4(value float64) float64 {
	if value < 0 {
		value = 0
	}
	return float64(int(value*10000+0.5)) / 10000
}
